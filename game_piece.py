import pygame
import random
import math

class Fuel:
    def __init__(self, x, y, ppi, source="scatter"):
        self.x = x
        self.y = y
        self.radius = 2.95 # inches
        self.color = (255, 255, 0) 
        self.collected = False
        self.source = source
        self.vel_x = 0
        self.vel_y = 0
        self.immune_timer = 0 # Brief period where it can't be collected
        
    def draw(self, screen, ppi):
        if not self.collected:
            pygame.draw.circle(screen, self.color, (int(self.x * ppi), int(self.y * ppi)), int(self.radius * ppi))

class GamePieceManager:
    def __init__(self, config, ppi):
        self.ppi = ppi
        self.fuels = []
        self.outpost_released = False
        
        # Physics Params (Tuneable)
        self.bounciness = config.get('physics', {}).get('bounciness', 0.8)
        self.friction = config.get('physics', {}).get('friction', 0.97)
        
        self.spawn_initial(config)
        
    def spawn_initial(self, config):
        field_w = config['field']['width_inches']
        field_h = config['field']['length_inches']
        
        # 1. Depot Fuel (One side, 24 pieces grid)
        center_y = field_h / 2
        depot_y_center = center_y - 76
        depot_w, depot_h = 27, 42
        depot_rect_y = depot_y_center - depot_h/2
        ds_x = 15.5
        
        def spawn_depot_grid(x_start, y_start):
            cols, rows = 4, 6 
            sp_x, sp_y = depot_w/cols, depot_h/rows
            for r in range(rows):
                for c in range(cols):
                    self.fuels.append(Fuel(x_start + c*sp_x + sp_x/2, y_start + r*sp_y + sp_y/2, self.ppi, "depot"))

        spawn_depot_grid(ds_x, depot_rect_y)
        spawn_depot_grid(field_w - ds_x - depot_w, depot_rect_y)
            
        # 2. Concentrated Grid Scatter (150 pieces)
        box_w, box_h = 72, 182
        center_x = field_w / 2
        cols, rows = 10, 15
        spacing_x, spacing_y = box_w/cols, box_h/rows
        start_x, start_y = center_x - box_w/2, center_y - box_h/2
        
        for r in range(rows):
            for c in range(cols):
                self.fuels.append(Fuel(start_x + c*spacing_x + spacing_x/2, start_y + r*spacing_y + spacing_y/2, self.ppi, "scatter"))
            
    def recycle_fuel(self, robot, config):
        field_w = config['width_inches']
        hub_x = 181.56 if robot.x < field_w/2 else field_w - 181.56
        hub_y = config['length_inches'] / 2
        
        new_fuel = Fuel(hub_x, hub_y, self.ppi, "recycled")
        new_fuel.immune_timer = 0.3
        direction = 1 if hub_x < field_w/2 else -1
        angle = random.uniform(-0.6, 0.6) 
        vel = random.uniform(80, 120) * self.bounciness
        new_fuel.vel_x = math.cos(angle) * vel * direction
        new_fuel.vel_y = math.sin(angle) * vel
        self.fuels.append(new_fuel)

    def pass_fuel(self, x, y, tx, ty, blocked, needed_mag=None):
        # Calculate direction
        dx = tx - x
        dy = ty - y
        dist = (dx**2 + dy**2)**0.5
        
        # Offset starting position to be outside robot (approx 20 inches)
        off_x = (dx / dist) * 20
        off_y = (dy / dist) * 20
        
        new_fuel = Fuel(x + off_x, y + off_y, self.ppi, "pass")
        new_fuel.immune_timer = 0.5 
        
        # Velocity magnitude
        if needed_mag is not None:
            base_vel = needed_mag
        else:
            time_to_target = 0.35
            base_vel = dist / time_to_target
        
        if blocked:
            # "High Lob" - significantly more velocity and scatter
            base_vel *= 1.4
            dx += random.uniform(-40, 40)
            dy += random.uniform(-40, 40)
            
        new_fuel.vel_x = (dx / dist) * base_vel
        new_fuel.vel_y = (dy / dist) * base_vel
        self.fuels.append(new_fuel)

    def release_outpost(self, config):
        if not self.outpost_released:
            field_w, field_h = config['width_inches'], config['length_inches']
            # Red outpost: Bottom-Left
            for _ in range(24):
                f = Fuel(10, field_h - 10, self.ppi, "outpost")
                f.immune_timer = 0.5
                angle = random.uniform(0.1, 1.4)
                vel = random.uniform(70, 110) * self.bounciness
                f.vel_x = math.cos(angle) * vel
                f.vel_y = -math.sin(angle) * vel
                self.fuels.append(f)
            # Blue outpost: Top-Right
            for _ in range(24):
                f = Fuel(field_w - 10, 10, self.ppi, "outpost")
                f.immune_timer = 0.5
                angle = random.uniform(3.2, 4.6)
                vel = random.uniform(70, 110) * self.bounciness
                f.vel_x = math.cos(angle) * vel
                f.vel_y = -math.sin(angle) * vel
                self.fuels.append(f)
            self.outpost_released = True
            
    def update(self, robots, game_time, config):
        dt = 1/60 
        if game_time > 30 and not self.outpost_released:
            self.release_outpost(config)

        for fuel in self.fuels:
            if not fuel.collected:
                if fuel.immune_timer > 0:
                    fuel.immune_timer -= dt

                if abs(fuel.vel_x) > 0.1 or abs(fuel.vel_y) > 0.1:
                    fuel.x += fuel.vel_x * dt
                    fuel.y += fuel.vel_y * dt
                    fuel.vel_x *= self.friction
                    fuel.vel_y *= self.friction
                    
                    if abs(fuel.vel_x) < 2: fuel.vel_x = 0
                    if abs(fuel.vel_y) < 2: fuel.vel_y = 0
                    
                    if fuel.x < 5: 
                        fuel.vel_x = abs(fuel.vel_x) * self.bounciness
                        fuel.x = 5
                    if fuel.x > config['width_inches']-5: 
                        fuel.vel_x = -abs(fuel.vel_x) * self.bounciness
                        fuel.x = config['width_inches']-5
                    if fuel.y < 5: 
                        fuel.vel_y = abs(fuel.vel_y) * self.bounciness
                        fuel.y = 5
                    if fuel.y > config['length_inches']-5: 
                        fuel.vel_y = -abs(fuel.vel_y) * self.bounciness
                        fuel.y = config['length_inches']-5

                # Important: skip collection if immune
                if fuel.immune_timer > 0:
                    continue

                for robot in robots:
                    collection_range = max(robot.length, robot.width)/2 + 5
                    dx, dy = fuel.x - robot.x, fuel.y - robot.y
                    dist = (dx**2 + dy**2)**0.5
                    
                    if dist < collection_range:
                        # Convert to Robot-Local Coordinates
                        rad = math.radians(robot.angle)
                        cos_a = math.cos(rad)
                        sin_a = math.sin(rad)
                        
                        # Local X is forward/backward, Local Y is side-to-side
                        local_x = (dx * cos_a + dy * sin_a)
                        local_y = (-dx * sin_a + dy * cos_a)
                        
                        # Collection Hit-Box logic
                        # Intake is at robot.length/2 (front) or -robot.length/2 (back)
                        # We define a 'mouth' that is 5 inches deep
                        collected = False
                        
                        half_l = robot.length / 2
                        half_w = robot.width / 2
                        
                        # Side boundaries: slightly WIDER than robot to feel "sticky"
                        if abs(local_y) < (half_w + 1): 
                            if robot.intake_type == "dual":
                                # Depth check: half_l - 8 (deep inside) < local_x < half_l + 5 (in front of robot)
                                if robot.intake_deploy_side == "front" and (half_l - 8 < local_x < half_l + 5):
                                    collected = True
                                elif robot.intake_deploy_side == "back" and (-half_l - 5 < local_x < -half_l + 8):
                                    collected = True
                            else:
                                # Single Intake: Front ONLY
                                if half_l - 8 < local_x < half_l + 5:
                                    collected = True

                        # Success Rate check
                        if collected and random.random() > robot.intake_success_rate:
                            collected = False

                        if collected and robot.holding < robot.capacity and robot.intake_transition_timer <= 0:
                            fuel.collected = True
                            robot.holding += 1
                            break 
                        
                        # If not collected, check for physical collision (The "Kick")
                        # This triggers if we strike any part of the robot
                        collision_dist = min(half_l, half_w) + 2
                        if dist < collision_dist + 2:
                            overlap = (collision_dist + 2) - dist
                            push_mag = overlap + 1
                            angle_to_fuel = math.atan2(dy, dx)
                            fuel.x += math.cos(angle_to_fuel) * push_mag
                            fuel.y += math.sin(angle_to_fuel) * push_mag
                            
                            robot_vel_mag = (robot.vel_x_robot**2 + robot.vel_y_robot**2)**0.5
                            kick_vel = 50 * self.bounciness + (robot_vel_mag * 0.8)
                            
                            fuel.vel_x = math.cos(angle_to_fuel) * kick_vel
                            fuel.vel_y = math.sin(angle_to_fuel) * kick_vel
                        
    def draw(self, screen):
        for fuel in self.fuels:
            fuel.draw(screen, self.ppi)
