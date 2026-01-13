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
        
        # Alliance
        self.alliance = alliance 
        
        self.intake_deploy_side = "front"
        self.intake_transition_timer = 0
        self.intake_transition_time = 0.5
        
        self.color = (180, 50, 50) if alliance == "red" else (50, 50, 180)
        
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
        if not in_neutral or self.holding == 0:
            return

        if (current_time - self.last_shot_time) >= (1.0 / self.shoot_rate):
            is_red = self.alliance == "red"
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
        
    def update(self, dt, keys, controls, field, current_time, robots, pieces=None, can_score=True, ai_inputs=None):
        target_vel_x_robot = 0
        target_vel_y_robot = 0
        
        current_max_speed = self.max_speed
        current_accel = self.acceleration
        
        # Strategy Actions Check (for speed limits)
        in_range = self.check_shoot_range(field)
        limiting_speed = False
        if self.auto_shoot_enabled and in_range and self.holding > 0 and can_score:
            current_max_speed = self.auto_shoot_max_speed
            current_accel = self.auto_shoot_accel
            limiting_speed = True

        # Movement Input
        if ai_inputs:
            # AI uses normalized -1.0 to 1.0 inputs
            if self.drivetrain == "swerve":
                target_vel_x_robot = ai_inputs.get('x', 0) * current_max_speed
                target_vel_y_robot = ai_inputs.get('y', 0) * current_max_speed
            else:
                # Tank: Y is forward/back
                target_vel_y_robot = ai_inputs.get('y', 0) * current_max_speed
        else:
            # Human (Keyboard)
            if self.drivetrain == "swerve":
                if keys[controls['up']]: target_vel_y_robot = -current_max_speed
                if keys[controls['down']]: target_vel_y_robot = current_max_speed
                if keys[controls['left']]: target_vel_x_robot = -current_max_speed
                if keys[controls['right']]: target_vel_x_robot = current_max_speed
            else:
                if keys[controls['up']]: target_vel_y_robot = -current_max_speed
                if keys[controls['down']]: target_vel_y_robot = current_max_speed

        # Normalize Movement (only for Swerve)
        if self.drivetrain == "swerve" and target_vel_x_robot != 0 and target_vel_y_robot != 0:
            mag = (target_vel_x_robot**2 + target_vel_y_robot**2)**0.5
            target_vel_x_robot = (target_vel_x_robot / mag) * current_max_speed
            target_vel_y_robot = (target_vel_y_robot / mag) * current_max_speed

        # Velocity Smoothing
        for axis, target in [('x', target_vel_x_robot), ('y', target_vel_y_robot)]:
            attr = f'vel_{axis}_robot'
            curr = getattr(self, attr)
            if curr < target:
                setattr(self, attr, min(target, curr + current_accel * dt))
            elif curr > target:
                setattr(self, attr, max(target, curr - current_accel * dt))

        # Rotation
        if ai_inputs:
            self.rot_velocity = ai_inputs.get('rot', 0) * self.rotation_speed
            
            # AI Toggles (optional, usually AI manages state directly)
            if ai_inputs.get('shoot_toggle'): self.auto_shoot_enabled = not self.auto_shoot_enabled
            if ai_inputs.get('pass_toggle'): self.auto_pass_enabled = not self.auto_pass_enabled
        else:
            if keys[controls['rotate_l']]: self.rot_velocity = -self.rotation_speed
            elif keys[controls['rotate_r']]: self.rot_velocity = self.rotation_speed
            else: self.rot_velocity = 0
            
        self.angle += self.rot_velocity * dt
        
        # Field Oriented Velocity Calculation
        rad = math.radians(self.angle)
        cos_a = math.cos(rad)
        sin_a = math.sin(rad)
        
        if self.drivetrain == "swerve":
            field_vel_x = (cos_a * -self.vel_y_robot) + (-sin_a * self.vel_x_robot)
            field_vel_y = (sin_a * -self.vel_y_robot) + (cos_a * self.vel_x_robot)
        else:
            # Tank: Y only move forward/back
            field_vel_x = cos_a * -self.vel_y_robot
            field_vel_y = sin_a * -self.vel_y_robot

        # Actions
        scored = False
        if limiting_speed:
            if self.launch(current_time, field):
                scored = True
        
        if self.auto_pass_enabled and self.holding > 0 and pieces:
            self.auto_pass(current_time, field, pieces)

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
            rect = pygame.Rect(nx - self.length/2, ny - self.width/2, self.length, self.width)
            for wall in field.colliders:
                if rect.colliderect(wall): return True
            for hub in field.hubs:
                dist = ((nx - hub['x'])**2 + (ny - hub['y'])**2)**0.5
                if dist < (hub['r'] + min(self.width, self.length)/2 - 1): return True
            for other in robots:
                if other == self: continue
                other_rect = pygame.Rect(other.x - other.length/2, other.y - other.width/2, other.length, other.width)
                if rect.colliderect(other_rect): return True
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
            
        return scored

    def draw(self, screen, ppi, font):
        w, h = self.length * ppi, self.width * ppi
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(surf, self.color, (0, 0, w, h), border_radius=3)
        pygame.draw.rect(surf, (200, 200, 200), (0, 0, w, h), 2, border_radius=3) 
        
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
