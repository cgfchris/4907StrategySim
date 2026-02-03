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
        self.bounces = 0 # Track bounces for Hub Penalty
        self.airborne_timer = 0.5 if source == "recycled" else 0
        
    def draw(self, screen, ppi):
        if not self.collected:
            pygame.draw.circle(screen, self.color, (int(self.x * ppi), int(self.y * ppi)), int(self.radius * ppi))

class GamePieceManager:
    def __init__(self, config, ppi):
        self.ppi = ppi
        self.fuels = []
        self.outpost_released = False
        self.penalties = [] # List of (alliance, amount)
        self.passed_red = 0
        self.passed_blue = 0
        self.dump_queue = []
        
        # Physics Params (Tuneable)
        self.bounciness = config['physics']['bounciness']
        self.friction = config['physics']['friction']
        
        # Performance: Spatial Partitioning
        self.grid_size = config['field'].get('spatial_grid_size', [6, 3])
        self.grid = {} # (gx, gy) -> list of fuel
        self.field_w = config['field']['width_inches']
        self.field_h = config['field']['length_inches']
        self.cell_w = self.field_w / self.grid_size[0]
        self.cell_h = self.field_h / self.grid_size[1]
        self.divider_x = config['field']['divider_x']
        
        # AI Awareness: Global Densities
        self.grid_counts = {} # (gx, gy) -> fuel count
        
    def reset(self, config):
        self.fuels = []
        self.outpost_released = False
        self.penalties = []
        self.dump_queue = []
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
                    f = Fuel(x_start + c*sp_x + sp_x/2, y_start + r*sp_y + sp_y/2, self.ppi, "depot")
                    f.bounces = 1
                    self.fuels.append(f)

        red_depot_y = depot_rect_y
        blue_depot_y = field_h - depot_rect_y - depot_h
        
        spawn_depot_grid(ds_x, red_depot_y)
        spawn_depot_grid(field_w - ds_x - depot_w, blue_depot_y)
            
        # 2. Concentrated Grid Scatter (150 pieces)
        box_w, box_h = 72, 182
        center_x = field_w / 2
        cols, rows = 10, 15
        spacing_x, spacing_y = box_w/cols, box_h/rows
        start_x, start_y = center_x - box_w/2, center_y - box_h/2
        
        for r in range(rows):
            for c in range(cols):
                f = Fuel(start_x + c*spacing_x + spacing_x/2, start_y + r*spacing_y + spacing_y/2, self.ppi, "scatter")
                f.bounces = 1 # Field starts safe
                self.fuels.append(f)
            
    def recycle_fuel(self, robot, config):
        field_w = config['width_inches']
        hub_x = 181.56 if robot.x < field_w/2 else field_w - 181.56
        hub_y = config['length_inches'] / 2
        
        new_fuel = Fuel(hub_x, hub_y, self.ppi, "recycled")
        new_fuel.immune_timer = 0 # Allowed to catch, but penalized!
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
        
        # Teleport Glitch Fix: Check for ENTRY into the target zone
        # Red: Entering from Right -> Left (crosses divider_x)
        # Blue: Entering from Left -> Right (crosses width - divider_x)
        if x > self.divider_x and new_fuel.x <= self.divider_x:
            self.passed_red += 1
        elif x < (self.field_w - self.divider_x) and new_fuel.x >= (self.field_w - self.divider_x):
            self.passed_blue += 1
            
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
        new_fuel.bounces = 1
        self.fuels.append(new_fuel)

    def release_outpost(self, config):
        if not self.outpost_released:
            field_w, field_h = config['field']['width_inches'], config['field']['length_inches']
            # Red outpost: Bottom-Left
            for _ in range(24):
                f = Fuel(10, field_h - 10, self.ppi, "outpost")
                f.immune_timer = 0.5
                angle = random.uniform(0.1, 1.4)
                vel = random.uniform(70, 110) * self.bounciness
                f.vel_x = math.cos(angle) * vel
                f.vel_y = -math.sin(angle) * vel
                f.bounces = 1
                self.fuels.append(f)
            # Blue outpost: Top-Right
            for _ in range(24):
                f = Fuel(config['field']['width_inches'] - 10, 10, self.ppi, "outpost")
                f.immune_timer = 0.5
                angle = random.uniform(3.2, 4.6)
                vel = random.uniform(70, 110) * self.bounciness
                f.vel_x = math.cos(angle) * vel
                f.vel_y = -math.sin(angle) * vel
                f.bounces = 1
                self.fuels.append(f)
            self.outpost_released = True
    
    def spawn_dump(self, x, y):
        self.dump_queue.append((x, y))
            
    def update(self, robots, game_time, config, disable_outposts=False, consume_passed=False):
        dt = 1/60 
        dump_time = config['field'].get('outpost_dump_time', 30.0)
        p_val = config['field'].get('hub_penalty_value', 5)
        
        if not disable_outposts and game_time > dump_time and not self.outpost_released:
            self.release_outpost(config)

        # Handle Dump Queue
        while self.dump_queue:
            x, y = self.dump_queue.pop(0)
            f = Fuel(x, y, self.ppi, "dump")
            f.immune_timer = 2.0 # Don't re-collect immediately
            # Small random kick
            angle = random.uniform(0, 2 * math.pi)
            vel = random.uniform(20, 40)
            f.vel_x = math.cos(angle) * vel
            f.vel_y = math.sin(angle) * vel
            f.bounces = 1
            self.fuels.append(f)

        self.penalties = [] # Clear penalties each frame (or handle them in main)
        self.passed_red = 0
        self.passed_blue = 0

        # 1. Clear/Rebuild Grid and Update Fuel Physics
        self.grid = {(gx, gy): [] for gx in range(self.grid_size[0]) for gy in range(self.grid_size[1])}
        self.grid_counts = {k: 0 for k in self.grid.keys()}

        for fuel in self.fuels:
            if fuel.collected: continue
            
            # Physics/Timers
            if fuel.immune_timer > 0:
                fuel.immune_timer -= dt
            
            if fuel.bounces == 0 and fuel.airborne_timer > 0:
                fuel.airborne_timer -= dt
                if fuel.airborne_timer <= 0:
                    fuel.bounces = 1 

            if abs(fuel.vel_x) > 0.1 or abs(fuel.vel_y) > 0.1:
                old_x = fuel.x
                fuel.x += fuel.vel_x * dt
                fuel.y += fuel.vel_y * dt
                fuel.vel_x *= self.friction
                fuel.vel_y *= self.friction
                
                # Check for Zone Crossings (Passing)
                divider_x = config['field']['divider_x']
                field_w = config['field']['width_inches']
                
                # Red: Entering from Right (> divider) to Left (< divider)
                if old_x > divider_x and fuel.x <= divider_x:
                    self.passed_red += 1
                    if consume_passed: fuel.collected = True
                # Blue: Entering from Left (< W-div) to Right (> W-div)
                elif old_x < (field_w - divider_x) and fuel.x >= (field_w - divider_x):
                    self.passed_blue += 1
                    if consume_passed: fuel.collected = True

                if abs(fuel.vel_x) < 1.0: fuel.vel_x = 0
                if abs(fuel.vel_y) < 1.0: fuel.vel_y = 0
                
                fw, fh = config['field']['width_inches'], config['field']['length_inches']
                if fuel.x < 5: 
                    fuel.vel_x = abs(fuel.vel_x) * self.bounciness; fuel.x = 5; fuel.bounces += 1
                elif fuel.x > fw - 5: 
                    fuel.vel_x = -abs(fuel.vel_x) * self.bounciness; fuel.x = fw - 5; fuel.bounces += 1
                if fuel.y < 5: 
                    fuel.vel_y = abs(fuel.vel_y) * self.bounciness; fuel.y = 5; fuel.bounces += 1
                elif fuel.y > fh - 5: 
                    fuel.vel_y = -abs(fuel.vel_y) * self.bounciness; fuel.y = fh - 5; fuel.bounces += 1

            # Populate Grid
            gx = min(self.grid_size[0] - 1, max(0, int(fuel.x / self.cell_w)))
            gy = min(self.grid_size[1] - 1, max(0, int(fuel.y / self.cell_h)))
            self.grid[(gx, gy)].append(fuel)
            self.grid_counts[(gx, gy)] += 1

        # 2. Ball-to-Ball Collisions (Spatial Grid)
        for gx in range(self.grid_size[0]):
            for gy in range(self.grid_size[1]):
                cell_fuels = self.grid[(gx, gy)]
                if not cell_fuels: continue
                
                # Check within same cell (triangular loop)
                for i in range(len(cell_fuels)):
                    for j in range(i + 1, len(cell_fuels)):
                        self._resolve_fuel_collision(cell_fuels[i], cell_fuels[j])
                
                # Check specific neighbors to avoid double-counting
                # (Right, Down, Down-Right, Down-Left)
                for nx, ny in [(gx+1, gy), (gx, gy+1), (gx+1, gy+1), (gx+1, gy-1)]:
                    if 0 <= nx < self.grid_size[0] and 0 <= ny < self.grid_size[1]:
                        neighbor_fuels = self.grid[(nx, ny)]
                        for f1 in cell_fuels:
                            for f2 in neighbor_fuels:
                                self._resolve_fuel_collision(f1, f2)

        # 3. Check Robots (Search all fuels for 100% reliability)
        for robot in robots:
            half_l, half_w = robot.length / 2, robot.width / 2
            rad = math.radians(robot.angle)
            cos_a, sin_a = math.cos(rad), math.sin(rad)
            
            # Use distance squared for broad-phase (safe and fast)
            c_range = max(robot.length, robot.width)/2 + 10
            range_sq = c_range**2

            for fuel in self.fuels:
                if fuel.collected or fuel.immune_timer > 0: continue
                
                dx, dy = fuel.x - robot.x, fuel.y - robot.y
                dist_sq = dx**2 + dy**2
                
                if dist_sq < range_sq:
                    # Convert to local
                    local_x = (dx * cos_a + dy * sin_a)
                    local_y = (-dx * sin_a + dy * cos_a)
                    
                    collected = False
                    if abs(local_y) < (half_w + 1): 
                        if robot.intake_type == "dual":
                            if robot.intake_deploy_side == "front" and (half_l - 8 < local_x < half_l + 5):
                                collected = True
                            elif robot.intake_deploy_side == "back" and (-half_l - 5 < local_x < -half_l + 8):
                                collected = True
                        elif half_l - 8 < local_x < half_l + 5: # single
                            collected = True
                    
                    if collected and random.random() > robot.intake_success_rate:
                        collected = False
                        
                    if collected and robot.holding < robot.capacity and robot.intake_transition_timer <= 0 and not getattr(robot, 'disable_intake', False):
                        fuel.collected = True
                        robot.holding += 1
                        
                        if fuel.bounces == 0:
                            v = config.get('hub_penalty_value', 15)
                            self.penalties.append((robot.alliance, v))
                            robot.penalty_timer = 2.0
                        break
                    
                    # Physical collision (Kick)
                    col_dist = min(half_l, half_w) + 2
                    if dist_sq < (col_dist + 3)**2:
                        dist = dist_sq**0.5
                        overlap = (col_dist + 2) - dist
                        if overlap > 0:
                            angle_to_fuel = math.atan2(dy, dx)
                            fuel.x += math.cos(angle_to_fuel) * (overlap + 1)
                            fuel.y += math.sin(angle_to_fuel) * (overlap + 1)
                            
                            r_vel_mag = (robot.vel_x_robot**2 + robot.vel_y_robot**2)**0.5
                            kick_vel = 50 * self.bounciness + (r_vel_mag * 0.8)
                            
                            fuel.vel_x = math.cos(angle_to_fuel) * kick_vel
                            fuel.vel_y = math.sin(angle_to_fuel) * kick_vel
                            fuel.bounces += 1
                        
        self.fuels = [f for f in self.fuels if not f.collected]
                        
    def draw(self, screen):
        for fuel in self.fuels:
            fuel.draw(screen, self.ppi)
            
    def get_grid_counts(self, field, w_cells, h_cells):
        # Flatten grid counts into 1D array
        # grid_counts is {(x,y): count}
        # We need to ensure we return it in a stable order (e.g. row major or similar)
        # Expected shape: w_cells * h_cells
        flat = []
        for y in range(h_cells):
            for x in range(w_cells):
                flat.append(self.grid_counts.get((x,y), 0))
        import numpy as np
        return np.array(flat, dtype=np.float32)

    def _resolve_fuel_collision(self, f1, f2):
        if f1.collected or f2.collected: return
        
        dx, dy = f2.x - f1.x, f2.y - f1.y
        dist_sq = dx**2 + dy**2
        min_dist = f1.radius + f2.radius
        
        if dist_sq < min_dist**2 and dist_sq > 0.001:
            dist = dist_sq**0.5
            
            # 1. Overlap Correction (Repulsion)
            overlap = min_dist - dist
            nx = dx / dist
            ny = dy / dist
            
            f1.x -= nx * (overlap / 2)
            f1.y -= ny * (overlap / 2)
            f2.x += nx * (overlap / 2)
            f2.y += ny * (overlap / 2)
            
            # 2. Elastic Collision (Momentum Swap along Normal)
            # Relative velocity along normal
            rel_vx = f1.vel_x - f2.vel_x
            rel_vy = f1.vel_y - f2.vel_y
            vel_normal = rel_vx * nx + rel_vy * ny
            
            if vel_normal > 0: # Only collide if they are moving toward each other
                impulse = vel_normal * self.bounciness
                f1.vel_x -= impulse * nx
                f1.vel_y -= impulse * ny
                f2.vel_x += impulse * nx
                f2.vel_y += impulse * ny
                
                f1.bounces += 1
                f2.bounces += 1
