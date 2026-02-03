import pygame
import math

class RobotCamera:
    def __init__(self, width=400, height=250):
        self.width = width
        self.height = height
        self.surface = pygame.Surface((width, height))
        self.font = pygame.font.SysFont("Arial", 20, bold=True)
        
        # Camera Settings (Physical Mounting)
        self.cam_height = 15.0 # inches off ground
        self.cam_tilt = math.radians(10.0) # Angle downward
        
        # Default FOV (will be overridden by robot config)
        self.fov_h = math.radians(70.0)
        self.fov_v = math.radians(40.0)
        self.focal_len = (width / 2) / math.tan(self.fov_h / 2)
        
        self.enabled = False
        self.target_robot_idx = 0
        
    def project_raw(self, rel_x, rel_y, obj_z=0):
        """Project coordinates without FOV clipping for large structures."""
        if rel_y <= 1.0: # Minimum distance to avoid division by zero/weird distorts
            return None, None, 0
            
        angle_h = math.atan2(rel_x, rel_y)
        u = (self.width / 2) + math.tan(angle_h) * self.focal_len
        
        cam_height_offset = (self.cam_height - obj_z)
        angle_to_obj = math.atan2(cam_height_offset, rel_y)
        v = (self.height / 2) + math.tan(angle_to_obj - self.cam_tilt) * self.focal_len
        
        scale = self.focal_len / rel_y
        return int(u), int(v), scale

    def project(self, rel_x, rel_y, obj_z=0):
        u, v, scale = self.project_raw(rel_x, rel_y, obj_z)
        if u is None: return None, None, 0
        
        # FOV Clipping for standard objects
        if abs(math.atan2(rel_x, rel_y)) > self.fov_h / 2: return None, None, 0
        
        cam_y_offset = (self.cam_height - obj_z)
        if abs(math.atan2(cam_y_offset, rel_y) - self.cam_tilt) > self.fov_v / 2: return None, None, 0
            
        return u, v, scale

    def render(self, field, pieces, robots, active_robot):
        self.surface.fill((20, 20, 25)) # Dark void
        
        if not active_robot:
            return self.surface
            
        # 0. Sync Configuration
        self.fov_h = math.radians(active_robot.cam_fov_h)
        self.fov_v = math.radians(active_robot.cam_fov_v)
        # Recalculate focal length to match horizontal FOV
        self.focal_len = (self.width / 2) / math.tan(self.fov_h / 2)

        # 1. Background / Horizon
        # The horizon (D=infinity) is where angle_rel_to_axis = -cam_tilt
        horizon_angle = -self.cam_tilt
        horizon_v = int((self.height / 2) + math.tan(horizon_angle) * self.focal_len)
        
        pygame.draw.rect(self.surface, (40, 40, 50), (0, horizon_v, self.width, self.height - horizon_v))
        pygame.draw.line(self.surface, (100, 100, 120), (0, horizon_v), (self.width, horizon_v), 2)
        
        # Get robot state
        rx, ry = active_robot.x, active_robot.y
        ra_rad = math.radians(active_robot.angle)
        cos_a, sin_a = math.cos(ra_rad), math.sin(ra_rad)
        
        def to_robot_frame(field_x, field_y):
            dx = field_x - rx
            dy = field_y - ry
            # Forward (Depth) = dx * cos(a) + dy * sin(a)
            # Right (Lateral) = -dx * sin(a) + dy * cos(a)
            rel_y = (cos_a * dx) + (sin_a * dy)
            rel_x = (-sin_a * dx) + (cos_a * dy)
            return rel_x, rel_y

        draw_list = []
        visible_pieces = 0
        
        # Hubs (Hexagonal Funnels - treated as infinite height occluders)
        for h_idx, hub in enumerate(field.hubs):
            # Calculate 6 vertices
            vertices = []
            for i in range(6):
                ang = math.radians(i * 60)
                vx = hub['x'] + math.cos(ang) * hub['r']
                vy = hub['y'] + math.sin(ang) * hub['r']
                vertices.append(to_robot_frame(vx, vy))
                
            for i in range(6):
                v1 = vertices[i]
                v2 = vertices[(i + 1) % 6]
                
                # Only draw if face is somewhat in front of us
                if v1[1] < 2 and v2[1] < 2: continue
                
                avg_y = (v1[1] + v2[1]) / 2
                
                # Project bottom points
                u1_b, v1_b, _ = self.project_raw(v1[0], v1[1], 0)
                u2_b, v2_b, _ = self.project_raw(v2[0], v2[1], 0)
                
                # Project top points (Infinite high)
                u1_t, v1_t, _ = self.project_raw(v1[0], v1[1], 200) # 200" is plenty high
                u2_t, v2_t, _ = self.project_raw(v2[0], v2[1], 200)
                
                if u1_b is not None and u2_b is not None:
                    # Clip to screen sides loosely
                    if min(u1_b, u2_b) < self.width and max(u1_b, u2_b) > 0:
                        pts = [(u1_b, v1_b), (u2_b, v2_b), (u2_t, v2_t), (u1_t, v1_t)]
                        draw_list.append(('hub', avg_y, (30, 30, 40), pts))

        # Bumps (Sloped Ramps: 6.5" high peak, 44.4" total width)
        xs = [field.divider_x, field.width_in - field.divider_x]
        ramp_x_half = 22.2 # 44.4 / 2
        for x in xs:
            for b_y_range in [field.bump1_y, field.bump2_y]:
                y1, y2 = b_y_range
                avg_y_world = (y1 + y2) / 2
                
                # We draw two faces per bump: Red-facing ramp and Blue-facing ramp
                # Vertices in Robot Frame
                peak_v1 = to_robot_frame(x, y1)
                peak_v2 = to_robot_frame(x, y2)
                red_side_v1 = to_robot_frame(x - ramp_x_half, y1)
                red_side_v2 = to_robot_frame(x - ramp_x_half, y2)
                blue_side_v1 = to_robot_frame(x + ramp_x_half, y1)
                blue_side_v2 = to_robot_frame(x + ramp_x_half, y2)
                
                # Project points
                u_p1, v_p1, _ = self.project_raw(peak_v1[0], peak_v1[1], 6.5)
                u_p2, v_p2, _ = self.project_raw(peak_v2[0], peak_v2[1], 6.5)
                u_r1, v_r1, _ = self.project_raw(red_side_v1[0], red_side_v1[1], 0)
                u_r2, v_r2, _ = self.project_raw(red_side_v2[0], red_side_v2[1], 0)
                u_b1, v_b1, _ = self.project_raw(blue_side_v1[0], blue_side_v1[1], 0)
                u_b2, v_b2, _ = self.project_raw(blue_side_v2[0], blue_side_v2[1], 0)
                
                avg_dist = (peak_v1[1] + peak_v2[1]) / 2
                if avg_dist < 5: continue # Clip too close
                
                # Red Side Ramp
                if u_p1 and u_r1 and min(u_p1, u_r1) < self.width and max(u_p1, u_r1) > 0:
                    pts = [(u_r1, v_r1), (u_p1, v_p1), (u_p2, v_p2), (u_r2, v_r2)]
                    draw_list.append(('bump', avg_dist, (80, 80, 80), pts))
                    
                # Blue Side Ramp
                if u_p1 and u_b1 and min(u_p1, u_b1) < self.width and max(u_p1, u_b1) > 0:
                    pts = [(u_p1, v_p1), (u_b1, v_b1), (u_b2, v_b2), (u_p2, v_p2)]
                    draw_list.append(('bump', avg_dist, (90, 90, 90), pts))

        # Balls (Physical Radius = 2.95 inches)
        for p in pieces.fuels:
            rel_x, rel_y = to_robot_frame(p.x, p.y)
            if rel_y > 3: # Slight buffer
                u, v, scale = self.project(rel_x, rel_y)
                if u is not None and 0 <= u <= self.width and 0 <= v <= self.height:
                    draw_list.append(('piece', rel_y, rel_x, p.color, u, v, scale))
                    visible_pieces += 1
                
        # Other Robots (Physical Size ~ 27x27 inches)
        for r in robots:
            if r == active_robot: continue
            rel_x, rel_y = to_robot_frame(r.x, r.y)
            if rel_y > 5:
                u, v, scale = self.project(rel_x, rel_y)
                if u is not None and 0 <= u <= self.width and 0 <= v <= self.height:
                    draw_list.append(('robot', rel_y, rel_x, r.color, u, v, scale))

        # Sort by depth (Far to Near)
        draw_list.sort(key=lambda x: x[1], reverse=True)
        
        for item in draw_list:
            if item[0] == 'piece':
                u, v, scale = item[4], item[5], item[6]
                radius = max(2, int(3.0 * scale))
                pygame.draw.circle(self.surface, item[3], (u, v), radius)
                pygame.draw.circle(self.surface, (255, 255, 255), (u, v), radius, 1)
            elif item[0] == 'robot':
                u, v, scale = item[4], item[5], item[6]
                rw = int(27 * scale)
                rh = int(24 * scale)
                pygame.draw.rect(self.surface, item[3], (u - rw//2, v - rh, rw, rh))
                pygame.draw.rect(self.surface, (0, 0, 0), (u - rw//2, v - rh, rw, rh), 1)
            elif item[0] == 'hub':
                pts = item[3]
                pygame.draw.polygon(self.surface, item[2], pts)
                # Outer glow/border based on depth
                alpha = max(50, min(255, int(500 / item[1])))
                pygame.draw.polygon(self.surface, (100, 100, 120), pts, 1)
            elif item[0] == 'bump':
                pts = item[3]
                pygame.draw.polygon(self.surface, item[2], pts)
                pygame.draw.polygon(self.surface, (50, 50, 50), pts, 1)

        # Crosshair
        pygame.draw.line(self.surface, (0, 255, 0), (self.width//2 - 10, self.height//2), (self.width//2 + 10, self.height//2), 1)
        pygame.draw.line(self.surface, (0, 255, 0), (self.width//2, self.height//2 - 10), (self.width//2, self.height//2 + 10), 1)

        # Vision Info Overlay
        bg_rect = pygame.Rect(10, 10, 130, 30)
        pygame.draw.rect(self.surface, (0, 0, 0, 150), bg_rect, border_radius=5)
        count_text = self.font.render(f"PIECES: {visible_pieces}", True, (50, 255, 50))
        self.surface.blit(count_text, (20, 15))

        return self.surface
