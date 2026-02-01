import pygame
import math
import random

class Robot:
    def __init__(self, x, y, config, alliance="red"):
        self.x = x
        self.y = y
        self.angle = 0  
        self.width = config.get('width', 27)
        self.length = config.get('length', 27)
        
        self.max_speed = config['max_speed']
        self.acceleration = config['acceleration']
        self.rotation_speed = config['rotation_speed']
        
        self.vel_x_robot = 0 
        self.vel_y_robot = 0 
        self.field_vel_x = 0
        self.field_vel_y = 0
        self.rot_velocity = 0
        
        self.capacity = config['capacity']
        self.holding = 0
        self.launch_accuracy = config.get('launch_accuracy', 0.95)
        self.shoot_rate = config.get('shoot_rate', 5.0)
        self.min_shoot_dist = config.get('min_shoot_dist', 0)
        self.max_shoot_dist = config.get('max_shoot_dist', 160)
        
        self.auto_shoot_max_speed = config.get('auto_shoot_max_speed', 60)
        self.auto_shoot_accel = config.get('auto_shoot_accel', 100)
        
        self.last_shot_time = 0
        self.auto_shoot_enabled = config.get('auto_shoot_enabled', True)
        self.auto_pass_enabled = config.get('auto_pass_enabled', False)
        
        # New Params
        self.drivetrain = config.get('drivetrain', 'swerve') # 'swerve' or 'tank'
        self.intake_type = config.get('intake_type', 'dual') # 'dual' or 'single'
        self.intake_success_rate = config.get('intake_success_rate', 1.0)
        self.can_pass = config.get('can_pass', True)
        
        # Alliance
        self.alliance = alliance 
        
        self.intake_deploy_side = "front"
        self.intake_transition_timer = 0
        self.intake_transition_time = 0.5
        
        self.color = (180, 50, 50) if alliance == "red" else (50, 50, 180)
        self.penalty_timer = 0
        self.ai_update_rate = config.get('ai_update_rate', 30)
        self.ai_tick_timer = random.uniform(0, 1.0/self.ai_update_rate) # Desync robots
        self.last_ai_inputs = None
        self.is_field_oriented = config.get('is_field_oriented', False)
        self.is_ai = config.get('is_ai', False)
        
        # Autonomous Routine State
        self.auto_routine = config.get('auto_routine', [])
        self.auto_step_idx = 0
        self.auto_step_timer = 0
        self.pass_target_x = None
        self.pass_target_y = None
        
    def check_shoot_range(self, field):
        target_hub = field.hubs[0] if self.alliance == "red" else field.hubs[1]
        dist = ((self.x - target_hub['x'])**2 + (self.y - target_hub['y'])**2)**0.5
        return self.min_shoot_dist <= dist <= self.max_shoot_dist

    def launch(self, current_time, field):
        in_correct_zone = False
        if self.alliance == "red" and self.x <= field.divider_x:
            in_correct_zone = True
        elif self.alliance == "blue" and self.x >= (field.width_in - field.divider_x):
            in_correct_zone = True
            
        if not in_correct_zone:
            return False

        if self.holding > 0 and (current_time - self.last_shot_time) >= (1.0 / self.shoot_rate):
            self.holding -= 1
            self.last_shot_time = current_time
            return random.random() < self.launch_accuracy
        return False

    def auto_pass(self, current_time, field, pieces):
        in_neutral = field.divider_x < self.x < (field.width_in - field.divider_x)
        if not in_neutral or self.holding == 0 or not self.can_pass:
            return 0

        if (current_time - self.last_shot_time) >= (1.0 / self.shoot_rate):
            is_red = self.alliance == "red"
            
            # Use custom pass targets if set (by auto routine)
            if self.pass_target_x is not None and self.pass_target_y is not None:
                target_x, target_y = self.pass_target_x, self.pass_target_y
            else:
                target_x = 60 if is_red else field.width_in - 60
                target_y = self.y 
            
            dx = target_x - self.x
            dy = target_y - self.y
            dist = (dx**2 + dy**2)**0.5
            
            dt = 1/60.0
            friction = pieces.friction
            needed_mag = (dist * (1.0 - friction)) / dt
            
            hub_x = field.divider_x if is_red else field.width_in - field.divider_x
            hub_y = field.length_in / 2
            is_blocked = False
            if (is_red and self.x > hub_x) or (not is_red and self.x < hub_x):
                if abs(self.y - hub_y) < 60:
                    is_blocked = True
            
            self.holding -= 1
            self.last_shot_time = current_time
            pieces.pass_fuel(self.x, self.y, target_x, target_y, is_blocked, needed_mag)
            return 1
        return 0

    def dump(self, current_time, pieces):
        # Empty the whole hopper!
        if self.holding > 0:
            num_dumped = self.holding
            self.holding = 0
            self.last_shot_time = current_time
            return num_dumped
        return 0
        
    def should_update_ai(self, dt):
        self.ai_tick_timer += dt
        if self.ai_update_rate > 0 and self.ai_tick_timer >= (1.0 / self.ai_update_rate):
            self.ai_tick_timer = 0
            return True
        return False
        
    def update(self, dt, keys, controls, field, current_time, robots, pieces=None, can_score=True, ai_inputs=None):
        self.angle %= 360 # Normalize angle
        
        # 0. Initial State & Speed Limits
        current_max_speed = self.max_speed
        current_accel = self.acceleration
        in_range = self.check_shoot_range(field)
        limiting_speed = False
        if self.auto_shoot_enabled and in_range and self.holding > 0 and can_score:
            current_max_speed = self.auto_shoot_max_speed
            current_accel = self.auto_shoot_accel
            limiting_speed = True

        num_dumped = 0
        target_field_vx = None
        target_field_vy = None
        
        # 1. Scripted Autonomous Routine (0-20s Priority)
        if current_time < 20 and self.auto_routine and self.auto_step_idx < len(self.auto_routine):
            step = self.auto_routine[self.auto_step_idx]
            auto_inputs = {'x': 0, 'y': 0, 'rot': 0, 'shoot_state': False, 'pass_state': False, 'dump_state': False, 'disable_intake': False}
            
            # Step Initialization
            if self.auto_step_timer <= 0 and "t" in step:
                self.auto_step_timer = step['t']
            
            # A. Completion Check
            advance = False
            
            # B. Movement: Destination (Target X, Y)
            dist = None
            if "target_x" in step and "target_y" in step:
                tx, ty = step['target_x'], step['target_y']
                dx, dy = tx - self.x, ty - self.y
                dist = (dx**2 + dy**2)**0.5
                
                if dist > 5:
                    # Target Field-Oriented Velocity
                    target_field_vx = (dx / dist) * current_max_speed
                    target_field_vy = (dy / dist) * current_max_speed
            
            # C. Rotation (Angle P-Loop or Power)
            angle_err = None
            if "rot" in step:
                val = step['rot']
                if "target_x" in step or abs(val) > 1.1:
                    # Angle Control: Shortest path to target heading
                    target_angle = float(val) % 360
                    # Standard shortest-path wrap math
                    angle_err = (target_angle - self.angle + 180) % 360 - 180
                    
                    # P-loop with small deadband and saturation
                    if abs(angle_err) < 0.5:
                        auto_inputs['rot'] = 0
                    else:
                        auto_inputs['rot'] = max(-1.0, min(1.0, angle_err / 30.0)) # Snappier P=30
                else:
                    # Raw Power Control (-1.0 to 1.0)
                    auto_inputs['rot'] = val

            # Check Arrival Completion (if both target and rot are present, wait for both)
            if dist is not None and dist <= 5:
                # If we are close on position, check if we need to wait for rotation
                if angle_err is None or abs(angle_err) < 2.0:
                    advance = True

            # D. Movement: Timed Joystick (x, y)
            if "x" in step: auto_inputs['x'] = step['x']
            if "y" in step: auto_inputs['y'] = step['y']
            
            # D. Actions (States)
            if "shoot_state" in step: auto_inputs['shoot_state'] = step['shoot_state']
            if "pass_state" in step: auto_inputs['pass_state'] = step['pass_state']
            if "intake_state" in step: auto_inputs['disable_intake'] = not step['intake_state']
            if "dump_state" in step: auto_inputs['dump_state'] = step['dump_state']
            
            # Custom Targets
            if "pass_target_x" in step: self.pass_target_x = step['pass_target_x']
            if "pass_target_y" in step: self.pass_target_y = step['pass_target_y']
            
            # E. Timer Progress
            if "t" in step:
                self.auto_step_timer -= dt
                if self.auto_step_timer <= 0:
                    advance = True
            
            if advance:
                self.auto_step_idx += 1
                self.auto_step_timer = 0
                if self.auto_step_idx >= len(self.auto_routine):
                    print(f"DEBUG {self.alliance}: Routine FINISHED - Stopping All Inputs")
                    self.last_ai_inputs = None 
                    auto_inputs = None 
                
            # Override AI/Manual inputs during Auto Period
            ai_inputs = auto_inputs
        elif current_time >= 20 and self.auto_routine and self.auto_step_idx < 1000:
            # First frame after auto ends: Clear any latched state
            self.last_ai_inputs = None
            self.auto_step_idx = 9999 # Sentinel to prevent repeated clearing

        if ai_inputs:
            # ONLY Latch if this is a high-level AI (to support throttled AI ticks)
            # Autonomous routines run every frame and handle their own state.
            if self.is_ai:
                self.last_ai_inputs = ai_inputs
        else:
            # If no fresh inputs, check the latch
            ai_inputs = self.last_ai_inputs
        
        target_vel_x_robot = 0
        target_vel_y_robot = 0

        # Movement Input
        if ai_inputs:
            # AI uses normalized -1.0 to 1.0 inputs. Sanitize for robustness.
            try:
                def sanitize(val):
                    v = float(val)
                    return v if math.isfinite(v) else 0.0
                
                # If we don't have a direct field target from autonomous yet, use the inputs
                if target_field_vx is None:
                    if self.drivetrain == "swerve":
                        # Map inputs to field or robot space based on orientation setting
                        vx = sanitize(ai_inputs.get('x', 0)) * current_max_speed
                        vy = sanitize(ai_inputs.get('y', 0)) * current_max_speed
                        
                        if self.is_field_oriented:
                            target_field_vx, target_field_vy = vx, vy
                        else:
                            target_vel_x_robot, target_vel_y_robot = vx, vy
                    else:
                        # Tank: Y is forward/back
                        target_vel_y_robot = sanitize(ai_inputs.get('y', 0)) * current_max_speed
            except (TypeError, ValueError):
                pass 
        else:
            # Human (Keyboard)
            if self.drivetrain == "swerve":
                vx, vy = 0, 0
                if keys[controls['up']]: vy = -current_max_speed
                if keys[controls['down']]: vy = current_max_speed
                if keys[controls['left']]: vx = -current_max_speed
                if keys[controls['right']]: vx = current_max_speed
                
                if self.is_field_oriented:
                    # Human Field Oriented -> Set directly to field targets
                    target_field_vx, target_field_vy = vx, vy
                else:
                    target_vel_x_robot = vx
                    target_vel_y_robot = vy
            else:
                if keys[controls['up']]: target_vel_y_robot = -current_max_speed
                if keys[controls['down']]: target_vel_y_robot = current_max_speed

        # Normalize Movement (only for Swerve)
        if self.drivetrain == "swerve" and target_vel_x_robot != 0 and target_vel_y_robot != 0:
            mag = (target_vel_x_robot**2 + target_vel_y_robot**2)**0.5
            target_vel_x_robot = (target_vel_x_robot / mag) * current_max_speed
            target_vel_y_robot = (target_vel_y_robot / mag) * current_max_speed

        # Rotation calculation
        target_rot_vel = 0
        if ai_inputs:
            target_rot_vel = ai_inputs.get('rot', 0) * self.rotation_speed
        elif self.last_ai_inputs:
             target_rot_vel = self.last_ai_inputs.get('rot', 0) * self.rotation_speed
        else:
            if keys[controls['rotate_l']]: target_rot_vel = -self.rotation_speed
            elif keys[controls['rotate_r']]: target_rot_vel = self.rotation_speed
            
        prev_angle = self.angle
        self.rot_velocity = target_rot_vel 
        self.angle = (self.angle + self.rot_velocity * dt) % 360 # Step and normalize
        mid_angle = (prev_angle + self.angle) / 2.0
        # Check for wrap-around during midpoint calculation
        if abs(self.angle - prev_angle) > 180:
            mid_angle = (mid_angle + 180) % 360
            
        rad_mid = math.radians(mid_angle)
        cos_mid, sin_mid = math.cos(rad_mid), math.sin(rad_mid)

        # Velocity Smoothing
        if self.drivetrain == "swerve":
            # 1. Ensure we have field-oriented targets. If not, convert from robot targets.
            if target_field_vx is None:
                target_field_vx = (cos_mid * -target_vel_y_robot) + (-sin_mid * target_vel_x_robot)
                target_field_vy = (sin_mid * -target_vel_y_robot) + (cos_mid * target_vel_x_robot)
            
            # 2. Smooth in field space
            for axis, target in [('x', target_field_vx), ('y', target_field_vy)]:
                attr = f'field_vel_{axis}'
                curr = getattr(self, attr)
                if curr < target:
                    setattr(self, attr, min(target, curr + current_accel * dt))
                elif curr > target:
                    setattr(self, attr, max(target, curr - current_accel * dt))
            
            field_vel_x = self.field_vel_x
            field_vel_y = self.field_vel_y
            
            # 3. Update robot-relative velocities (for HID/HUD)
            self.vel_x_robot = (cos_mid * field_vel_y) + (-sin_mid * field_vel_x)
            self.vel_y_robot = -(cos_mid * field_vel_x) - (sin_mid * field_vel_y)
        else:
            # Tank: Smooth in ROBOT space (only y)
            for axis, target in [('y', target_vel_y_robot)]:
                attr = f'vel_{axis}_robot'
                curr = getattr(self, attr)
                if curr < target:
                    setattr(self, attr, min(target, curr + current_accel * dt))
                elif curr > target:
                    setattr(self, attr, max(target, curr - current_accel * dt))
            
            field_vel_x = cos_mid * -self.vel_y_robot
            field_vel_y = sin_mid * -self.vel_y_robot

        # Actions (State Management)
        if ai_inputs:
            # Persistent Toggles
            if 'shoot_state' in ai_inputs:
                self.auto_shoot_enabled = ai_inputs['shoot_state']
            if 'pass_state' in ai_inputs:
                self.auto_pass_enabled = ai_inputs['pass_state']
            
            # Pulse Actions (Dump)
            if ai_inputs.get('dump_state'):
                if pieces:
                    num_dumped = self.dump(current_time, pieces)
                    for _ in range(num_dumped):
                        pieces.spawn_dump(self.x, self.y)
            
            # Intake Disable Control
            self.disable_intake = ai_inputs.get('disable_intake', False)

        # Execution of Actions
        scored = False
        if limiting_speed or (not ai_inputs and keys[controls['shoot_key']]):
            if self.launch(current_time, field):
                scored = True
        
        passed_count = 0
        if (self.auto_pass_enabled or (not ai_inputs and keys[controls['pass_key']])) and self.holding > 0 and pieces:
            passed_count = self.auto_pass(current_time, field, pieces)

        # Collision with Dividers
        speed_factor = 1.0
        is_on_divider = False
        divider_xs = [field.divider_x, field.width_in - field.divider_x]
        for dx in divider_xs:
            if abs(self.x - dx) < 10:
                is_on_divider = True
                break
        
        if is_on_divider:
            if (field.bump1_y[0] < self.y < field.bump1_y[1]) or (field.bump2_y[0] < self.y < field.bump2_y[1]):
                speed_factor = 0.4
            
        new_x = self.x + field_vel_x * dt * speed_factor
        new_y = self.y + field_vel_y * dt * speed_factor
        
        def check_collision(nx, ny):
            # Dynamic AABB calculation (scales to account for rotation)
            rad = math.radians(self.angle)
            c, s = abs(math.cos(rad)), abs(math.sin(rad))
            eff_w = self.length * c + self.width * s
            eff_h = self.length * s + self.width * c
            
            if not (math.isfinite(nx) and math.isfinite(ny)):
                return True
                
            try:
                rect = pygame.Rect(int(nx - eff_w/2), int(ny - eff_h/2), int(eff_w), int(eff_h))
            except (TypeError, ValueError):
                return True 
            
            for wall in field.colliders:
                if rect.colliderect(wall): return True
            for hub in field.hubs:
                dx, dy = nx - hub['x'], ny - hub['y']
                dist_sq = dx**2 + dy**2
                thresh = (hub['r'] + min(self.width, self.length)/2 - 1)
                if dist_sq < thresh**2: return True
            for other in robots:
                if other == self: continue
                # Broad-phase AABB test
                if abs(nx - other.x) > (self.length + other.length)/2 + 2: continue
                if abs(ny - other.y) > (self.width + other.width)/2 + 2: continue
                
                # Ensure other robot coordinates are also valid
                if not (math.isfinite(other.x) and math.isfinite(other.y)):
                    continue
                
                try:
                    other_rect = pygame.Rect(int(other.x - other.length/2), int(other.y - other.width/2), int(other.length), int(other.width))
                    if rect.colliderect(other_rect): return True
                except (TypeError, ValueError):
                    continue
            return False

        # Independent Axis Movement (Sliding)
        # Try X
        if not check_collision(self.x + field_vel_x * dt * speed_factor, self.y):
            self.x += field_vel_x * dt * speed_factor
        else:
            self.vel_x_robot = 0
            
        # Try Y
        if not check_collision(self.x, self.y + field_vel_y * dt * speed_factor):
            self.y += field_vel_y * dt * speed_factor
        else:
            self.vel_y_robot = 0
            
        # Intake Side Determination
        if abs(self.vel_y_robot) > 10:
            new_side = "front" if self.vel_y_robot < 0 else "back"
            if self.intake_type == "single":
                new_side = "front" # Always front for single intake
                
            if new_side != self.intake_deploy_side:
                self.intake_deploy_side = new_side
                self.intake_transition_timer = self.intake_transition_time
        
        if self.intake_transition_timer > 0:
            self.intake_transition_timer -= dt
        
        if self.penalty_timer > 0:
            self.penalty_timer -= dt
            
        if num_dumped > 0:
            return {'scored': 0, 'dumped': num_dumped, 'passed': 0}
        return {'scored': 1 if scored else 0, 'dumped': 0, 'passed': passed_count}

    def draw(self, screen, ppi, font):
        w, h = self.length * ppi, self.width * ppi
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, self.color, (0, 0, w, h), border_radius=3)
        pygame.draw.rect(surf, (200, 200, 200), (0, 0, w, h), 2, border_radius=3) 
        
        if self.penalty_timer > 0:
            # Draw a bright red outline and text
            pygame.draw.rect(surf, (255, 0, 0), (0, 0, w, h), 4, border_radius=3)
            foul_text = font.render("MAJOR FOUL", True, (255, 0, 0))
            # Draw above robot - need to draw on main screen though
            # Let's draw it on the surf for now, but it might be too small
            # Actually, let's just make the robot flash bright red
            if int(self.penalty_timer * 10) % 2 == 0:
                pygame.draw.rect(surf, (255, 255, 255), (0, 0, w, h), border_radius=3)
        
        # Draw Intake(s)
        if self.intake_transition_timer <= 0:
            color = (0, 255, 0)
            if self.intake_type == "dual":
                if self.intake_deploy_side == "front":
                    pygame.draw.rect(surf, color, (w-5, 0, 5, h))
                else:
                    pygame.draw.rect(surf, color, (0, 0, 5, h))
            else:
                # Single Intake (Front ONLY)
                pygame.draw.rect(surf, color, (w-5, 0, 5, h))
        
        if self.auto_pass_enabled:
            pygame.draw.circle(surf, (255, 100, 255), (w//2, h-5), 3)

        pygame.draw.rect(surf, (255, 255, 255), (w-10, h/2-5, 10, 10))
        fuel_text = font.render(str(self.holding), True, (255, 255, 255))
        surf.blit(fuel_text, (w/2 - fuel_text.get_width()/2, h/2 - fuel_text.get_height()/2))
        
        # If Tank drive, maybe add some small visual clue like tracks
        if self.drivetrain == "tank":
            pygame.draw.rect(surf, (0, 0, 0, 100), (0, 0, w, 5))
            pygame.draw.rect(surf, (0, 0, 0, 100), (0, h-5, w, 5))

        rotated_surf = pygame.transform.rotate(surf, -self.angle)
        rect = rotated_surf.get_rect(center=(self.x * ppi, self.y * ppi))
        screen.blit(rotated_surf, rect)
