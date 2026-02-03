import pygame
import math

class Field:
    def __init__(self, config):
        self.ppi = config['pixels_per_inch']
        self.width_in = config['width_inches']
        self.length_in = config['length_inches']
        self.az_depth = config.get('alliance_zone_depth', 118.25)
        self.divider_x = config.get('divider_x', 181.56)
        
        # Dimensions for segments
        self.hub_w = 47
        self.bump_w = 73
        self.upright_w = 12
        self.trench_w = 50
        
        # Calculate Y ranges for segments (centered)
        center_y = self.length_in / 2
        self.hub_y = (center_y - self.hub_w/2, center_y + self.hub_w/2)
        self.bump1_y = (self.hub_y[0] - self.bump_w, self.hub_y[0])
        self.bump2_y = (self.hub_y[1], self.hub_y[1] + self.bump_w)
        self.upright1_y = (self.bump1_y[0] - self.upright_w, self.bump1_y[0])
        self.upright2_y = (self.bump2_y[1], self.bump2_y[1] + self.upright_w)

        # Depot Location: Single box per side, centered 76" from field center
        # center_y - 76 = 158.845 - 76 = 82.845
        self.depot_y_center = center_y - 76
        self.depot_w, self.depot_h = 27, 42
        self.depot_rect_y = self.depot_y_center - self.depot_h/2
        self.depot_dist_from_wall = 15.5

        # Colors
        self.color_red_ground = (130, 40, 40)
        self.color_blue_ground = (40, 40, 130)
        self.color_neutral_ground = (160, 160, 40)
        self.color_perimeter = (180, 180, 180)
        self.color_trench = (60, 60, 60)
        self.color_bump = (100, 100, 100)
        self.color_upright = (255, 255, 255)
        
        # Hard Stop Colliders
        self.colliders = []
        
        # Perimeter
        self.colliders.append(pygame.Rect(-10, 0, 10, self.length_in))
        self.colliders.append(pygame.Rect(self.width_in, 0, 10, self.length_in))
        self.colliders.append(pygame.Rect(0, -10, self.width_in, 10))
        self.colliders.append(pygame.Rect(0, self.length_in, self.width_in, 10))
        
        # Dividers at X values
        xs = [self.divider_x, self.width_in - self.divider_x]
        for x in xs:
            self.colliders.append(pygame.Rect(x - 2.5, self.hub_y[0], 5, self.hub_w))
            self.colliders.append(pygame.Rect(x - 2.5, self.upright1_y[0], 5, self.upright_w))
            self.colliders.append(pygame.Rect(x - 2.5, self.upright2_y[0], 5, self.upright_w))

        # Hub Targets
        self.hubs = [
            {'x': self.divider_x, 'y': center_y, 'r': 18},
            {'x': self.width_in - self.divider_x, 'y': center_y, 'r': 18}
        ]

        # REBUILT Towers (Climb structure)
        # Specs: 40" from wall, 11.38" from centerline, 34" apart.
        # Steel post: 3.5" (X) x 1.75" (Y). Rungs: 47" long.
        self.tower_wall_dist = 40.0
        self.tower_post_w = 3.5
        self.tower_post_h = 1.75
        self.tower_center_gap = 11.38
        self.tower_post_gap = 34.0
        self.tower_rung_len = 47.0
        
        # Add Tower Colliders (Steel Posts)
        mid_y = self.length_in / 2
        # Red Tower (Bottom half assembly centered at +11.38)
        red_mid = mid_y + self.tower_center_gap
        ry1 = red_mid - (self.tower_post_gap / 2) - self.tower_post_h
        ry2 = red_mid + (self.tower_post_gap / 2)
        for y in [ry1, ry2]:
            self.colliders.append(pygame.Rect(self.tower_wall_dist, y, self.tower_post_w, self.tower_post_h))
            
        # Blue Tower (Top half assembly centered at -11.38)
        blue_mid = mid_y - self.tower_center_gap
        by1 = blue_mid - (self.tower_post_gap / 2) - self.tower_post_h
        by2 = blue_mid + (self.tower_post_gap / 2)
        for y in [by1, by2]:
            self.colliders.append(pygame.Rect(self.width_in - self.tower_wall_dist - self.tower_post_w, y, self.tower_post_w, self.tower_post_h))

    def draw(self, screen, active_alliance=None):
        ppi = self.ppi
        
        # 1. Base Ground Colors (Full Length)
        # Red
        pygame.draw.rect(screen, self.color_red_ground, (0, 0, self.divider_x * ppi, self.length_in * ppi))
        # Blue
        pygame.draw.rect(screen, self.color_blue_ground, ((self.width_in - self.divider_x) * ppi, 0, self.divider_x * ppi, self.length_in * ppi))
        # Neutral
        pygame.draw.rect(screen, self.color_neutral_ground, (self.divider_x * ppi, 0, (self.width_in - 2*self.divider_x) * ppi, self.length_in * ppi))

        # 2. Field Markers (Centerlines)
        mid_x = (self.width_in / 2) * ppi
        mid_y = (self.length_in / 2) * ppi
        dash_len = 15 * ppi
        
        # Horizontal Centerline (Length-wise)
        for x in range(0, int(self.width_in * ppi), int(dash_len * 2)):
            pygame.draw.line(screen, (100, 100, 100), (x, mid_y), (x + dash_len, mid_y), 1)

        # Vertical Midfield Line (Width-wise / Auto Boundary)
        for y in range(0, int(self.length_in * ppi), int(dash_len * 2)):
            pygame.draw.line(screen, (200, 200, 200), (mid_x, y), (mid_x, y + dash_len), 2)

        # 3. Dividers & Bumps
        # Top Trench
        # trench_surf = pygame.Surface((self.width_in * ppi, self.upright1_y[0] * ppi), pygame.SRCALPHA)
        # trench_surf.fill((0, 0, 0, 120)) # Dark but translucent
        # screen.blit(trench_surf, (0, 0))
        
        # Bottom Trench
        # trench_h = (self.length_in - self.upright2_y[1]) * ppi
        # trench_surf_bottom = pygame.Surface((self.width_in * ppi, trench_h), pygame.SRCALPHA)
        # trench_surf_bottom.fill((0, 0, 0, 120))
        # screen.blit(trench_surf_bottom, (0, self.upright2_y[1] * ppi))

        xs = [self.divider_x, self.width_in - self.divider_x]
        ramp_width = 44.4
        for x in xs:
            # Drawing bumps with increased thickness to represent the ramp (48.5")
            pygame.draw.line(screen, self.color_bump, (x * ppi, self.bump1_y[0] * ppi), (x * ppi, self.bump1_y[1] * ppi), int(ramp_width * ppi))
            pygame.draw.line(screen, self.color_bump, (x * ppi, self.bump2_y[0] * ppi), (x * ppi, self.bump2_y[1] * ppi), int(ramp_width * ppi))
            pygame.draw.rect(screen, self.color_upright, ((x-2.5)*ppi, self.upright1_y[0]*ppi, 5*ppi, self.upright_w*ppi))
            pygame.draw.rect(screen, self.color_upright, ((x-2.5)*ppi, self.upright2_y[0]*ppi, 5*ppi, self.upright_w*ppi))
            pygame.draw.rect(screen, (30, 30, 30), ((x-2.5)*ppi, self.hub_y[0]*ppi, 5*ppi, self.hub_w*ppi))

        # 4. Perimeter
        pygame.draw.rect(screen, self.color_perimeter, (0, 0, int(self.width_in * ppi), int(self.length_in * ppi)), 5)

        # 5. Hubs (Hexagonal)
        for i, hub in enumerate(self.hubs):
            points = []
            for j in range(6):
                angle = math.radians(60 * j)
                px = int((hub['x'] + math.cos(angle) * hub['r']) * ppi)
                py = int((hub['y'] + math.sin(angle) * hub['r']) * ppi)
                points.append((px, py))
            
            pygame.draw.polygon(screen, (30, 30, 30), points)
            
            # Hub "Light up" logic
            border_color = (255, 215, 0) # Gold default
            if active_alliance == "both":
                border_color = (255, 255, 255) # White glow for both
            elif (active_alliance == "red" and i == 0) or (active_alliance == "blue" and i == 1):
                border_color = (100, 255, 100) # Bright green glow for active
            
            pygame.draw.polygon(screen, border_color, points, 3)
            
        # 5b. Towers (Endgame Structures)
        mid_y = self.length_in / 2
        
        # Red Tower (Bottom)
        tx = self.tower_wall_dist * ppi
        tw = self.tower_post_w * ppi
        th = self.tower_post_h * ppi
        red_mid = mid_y + self.tower_center_gap
        ry1 = (red_mid - self.tower_post_gap/2 - self.tower_post_h) * ppi
        ry2 = (red_mid + self.tower_post_gap/2) * ppi
        
        for y in [ry1, ry2]:
            # Wall bracing (Shadow/Supporting frame)
            pygame.draw.rect(screen, (60, 60, 60), (0, y + th/4, tx, th/2))
            # Steel Upright
            pygame.draw.rect(screen, (150, 40, 40), (tx, y, tw, th))
            pygame.draw.rect(screen, (200, 50, 50), (tx, y, tw, th), 2) # Highlight
            
        # Rungs (Climbing Bars)
        pygame.draw.line(screen, (180, 180, 180), (tx + tw/2, ry1 + th/2), (tx + tw/2, ry2 + th/2), 5)
            
        # Blue Tower (Top)
        btx = (self.width_in - self.tower_wall_dist - self.tower_post_w) * ppi
        blue_mid = mid_y - self.tower_center_gap
        by1 = (blue_mid - self.tower_post_gap/2 - self.tower_post_h) * ppi
        by2 = (blue_mid + self.tower_post_gap/2) * ppi
        
        for y in [by1, by2]:
            # Wall bracing
            pygame.draw.rect(screen, (60, 60, 60), (btx + tw, y + th/4, self.width_in*ppi - (btx+tw), th/2))
            # Steel Upright
            pygame.draw.rect(screen, (40, 40, 150), (btx, y, tw, th))
            pygame.draw.rect(screen, (50, 50, 200), (btx, y, tw, th), 2)

        # Blue Rungs
        pygame.draw.line(screen, (180, 180, 180), (btx + tw/2, by1 + th/2), (btx + tw/2, by2 + th/2), 5)
            
        # 6. Depot Markers (Single per side)
        # Red side
        pygame.draw.rect(screen, (255, 255, 255), (self.depot_dist_from_wall*ppi, self.depot_rect_y*ppi, self.depot_w*ppi, self.depot_h*ppi), 1)
        # Blue side (Wrong side fixed)
        blue_depot_y = self.length_in - self.depot_rect_y - self.depot_h
        pygame.draw.rect(screen, (255, 255, 255), ((self.width_in - self.depot_dist_from_wall - self.depot_w)*ppi, blue_depot_y*ppi, self.depot_w*ppi, self.depot_h*ppi), 1)
