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
        
        # AI Awareness: Global Densities
        self.grid_counts = {} # (gx, gy) -> fuel count
        
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
            
    def update(self, robots, game_time, config):
        dt = 1/60 
        dump_time = config['field'].get('outpost_dump_time', 30.0)
        if game_time > dump_time and not self.outpost_released:
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

        # Clear/Rebuild Grid for this frame
        self.grid = {}
        for gx in range(self.grid_size[0]):
            for gy in range(self.grid_size[1]):
                self.grid[(gx, gy)] = []
        self.grid_counts = {k: 0 for k in self.grid.keys()}

        for fuel in self.fuels:
            if not fuel.collected:
                # Assign to Grid Cell
                gx = min(self.grid_size[0] - 1, max(0, int(fuel.x / self.cell_w)))
                gy = min(self.grid_size[1] - 1, max(0, int(fuel.y / self.cell_h)))
                self.grid[(gx, gy)].append(fuel)
                self.grid_counts[(gx, gy)] += 1

                if fuel.immune_timer > 0:
                    fuel.immune_timer -= dt
                
                if fuel.bounces == 0 and fuel.airborne_timer > 0:
                    fuel.airborne_timer -= dt
                    if fuel.airborne_timer <= 0:
                        fuel.bounces = 1 # "Hit the floor"

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
                        fuel.bounces += 1
                    if fuel.x > config['field']['width_inches']-5: 
                        fuel.vel_x = -abs(fuel.vel_x) * self.bounciness
                        fuel.x = config['field']['width_inches']-5
                        fuel.bounces += 1
                    if fuel.y < 5: 
                        fuel.vel_y = abs(fuel.vel_y) * self.bounciness
                        fuel.y = 5
                        fuel.bounces += 1
                    if fuel.y > config['field']['length_inches']-5: 
                        fuel.vel_y = -abs(fuel.vel_y) * self.bounciness
                        fuel.y = config['field']['length_inches']-5
                        fuel.bounces += 1

                # SPATIAL PARTITIONING: Only check local grid cells
                gx_robot = int(robot.x / self.cell_w)
                gy_robot = int(robot.y / self.cell_h)
                
                check_cells = []
                for dx_g in [-1, 0, 1]:
                    for dy_g in [-1, 0, 1]:
                        cell = (gx_robot + dx_g, gy_robot + dy_g)
                        if cell in self.grid:
                            check_cells.append(self.grid[cell])
                
                collection_range = max(robot.length, robot.width)/2 + 5
                range_sq = collection_range**2
                
                for cell_list in check_cells:
                    for fuel in cell_list:
                        if fuel.collected or fuel.immune_timer > 0: continue
                        
                        dx, dy = fuel.x - robot.x, fuel.y - robot.y
                        dist_sq = dx**2 + dy**2
                        
                        if dist_sq < range_sq:
                            dist = dist_sq**0.5 # Needed for local coordinate rotation calculation
                            # Convert to Robot-Local Coordinates
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

                        if collected and robot.holding < robot.capacity and robot.intake_transition_timer <= 0 and not getattr(robot, 'disable_intake', False):
                            fuel.collected = True
                            robot.holding += 1
                            
                            if fuel.bounces == 0:
                                self.penalties.append((robot.alliance, 15))
                                robot.penalty_timer = 2.0
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
                            fuel.bounces += 1
                        
        # Clean up collected fuel
        self.fuels = [f for f in self.fuels if not f.collected]
                        
    def draw(self, screen):
        for fuel in self.fuels:
            fuel.draw(screen, self.ppi)
