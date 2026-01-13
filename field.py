import pygame

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

    def draw(self, screen, active_alliance=None):
        ppi = self.ppi
        
        # 1. Base Ground Colors (Full Length)
        # Red
        pygame.draw.rect(screen, self.color_red_ground, (0, 0, self.divider_x * ppi, self.length_in * ppi))
        # Blue
        pygame.draw.rect(screen, self.color_blue_ground, ((self.width_in - self.divider_x) * ppi, 0, self.divider_x * ppi, self.length_in * ppi))
        # Neutral
        pygame.draw.rect(screen, self.color_neutral_ground, (self.divider_x * ppi, 0, (self.width_in - 2*self.divider_x) * ppi, self.length_in * ppi))

        # 2. Trenches (Semi-Transparent Dark Overlay removed per feedback)
        # Top Trench
        # trench_surf = pygame.Surface((self.width_in * ppi, self.upright1_y[0] * ppi), pygame.SRCALPHA)
        # trench_surf.fill((0, 0, 0, 120)) # Dark but translucent
        # screen.blit(trench_surf, (0, 0))
        
        # Bottom Trench
        # trench_h = (self.length_in - self.upright2_y[1]) * ppi
        # trench_surf_bottom = pygame.Surface((self.width_in * ppi, trench_h), pygame.SRCALPHA)
        # trench_surf_bottom.fill((0, 0, 0, 120))
        # screen.blit(trench_surf_bottom, (0, self.upright2_y[1] * ppi))

        # 3. Divider Elements
        xs = [self.divider_x, self.width_in - self.divider_x]
        for x in xs:
            pygame.draw.line(screen, self.color_bump, (x * ppi, self.bump1_y[0] * ppi), (x * ppi, self.bump1_y[1] * ppi), 12)
            pygame.draw.line(screen, self.color_bump, (x * ppi, self.bump2_y[0] * ppi), (x * ppi, self.bump2_y[1] * ppi), 12)
            pygame.draw.rect(screen, self.color_upright, ((x-2.5)*ppi, self.upright1_y[0]*ppi, 5*ppi, self.upright_w*ppi))
            pygame.draw.rect(screen, self.color_upright, ((x-2.5)*ppi, self.upright2_y[0]*ppi, 5*ppi, self.upright_w*ppi))
            pygame.draw.rect(screen, (30, 30, 30), ((x-2.5)*ppi, self.hub_y[0]*ppi, 5*ppi, self.hub_w*ppi))

        # 4. Perimeter
        pygame.draw.rect(screen, self.color_perimeter, (0, 0, int(self.width_in * ppi), int(self.length_in * ppi)), 5)

        # 5. Hub Targets
        for i, hub in enumerate(self.hubs):
            pygame.draw.circle(screen, (20, 20, 20), (int(hub['x'] * ppi), int(hub['y'] * ppi)), int(hub['r'] * ppi))
            
            # Hub "Light up" logic
            border_color = (255, 215, 0) # Gold default
            if active_alliance == "both":
                border_color = (255, 255, 255) # White glow for both
            elif (active_alliance == "red" and i == 0) or (active_alliance == "blue" and i == 1):
                border_color = (100, 255, 100) # Bright green glow for active
            
            # Draw glow
            if border_color != (255, 215, 0):
                for r in range(1, 6):
                    pygame.draw.circle(screen, border_color, (int(hub['x'] * ppi), int(hub['y'] * ppi)), int(hub['r'] * ppi) + r, 1)
            
            pygame.draw.circle(screen, border_color, (int(hub['x'] * ppi), int(hub['y'] * ppi)), int(hub['r'] * ppi), 3)
            
        # 6. Depot Markers (Single per side)
        # Red side
        pygame.draw.rect(screen, (255, 255, 255), (self.depot_dist_from_wall*ppi, self.depot_rect_y*ppi, self.depot_w*ppi, self.depot_h*ppi), 1)
        # Blue side
        pygame.draw.rect(screen, (255, 255, 255), ((self.width_in - self.depot_dist_from_wall - self.depot_w)*ppi, self.depot_rect_y*ppi, self.depot_w*ppi, self.depot_h*ppi), 1)
