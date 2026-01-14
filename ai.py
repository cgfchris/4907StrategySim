import math
import time
import random

class RobotAI:
    def __init__(self, alliance="blue", is_tank=True):
        self.alliance = alliance
        self.is_tank = is_tank
        self.last_x = 0
        self.last_y = 0
        self.stuck_timer = 0
        self.recovery_timer = 0
        self.recovery_rot = 0.5
        
    def get_dist(self, x1, y1, x2, y2):
        return ((x1 - x2)**2 + (y1 - y2)**2)**0.5

    def count_alliance_fuel(self, pieces, field):
        # Optimized using grid counts if available
        if hasattr(pieces, 'grid_counts'):
            count = 0
            is_red = self.alliance == "red"
            for (gx, gy), c in pieces.grid_counts.items():
                if c == 0: continue
                # Center of cell
                cx = (gx + 0.5) * pieces.cell_w
                if is_red and cx < field.divider_x:
                    count += c
                elif not is_red and cx > (field.width_in - field.divider_x):
                    count += c
            return count
            
        count = 0
        is_red = self.alliance == "red"
        for fuel in pieces.fuels:
            if not fuel.collected:
                if is_red and fuel.x < field.divider_x:
                    count += 1
                elif not is_red and fuel.x > (field.width_in - field.divider_x):
                    count += 1
        return count

    def update(self, robot, field, pieces, can_score, other_robots=[]):
        # Tracking targets for coordination (simplified)
        targeted_fuels = []
        for other in other_robots:
            if other != robot and other.alliance == robot.alliance:
                # We could ideally store the target in the robot class, 
                # but for now let's just use proximity logic
                pass

        # State Transitions
        alliance_fuel = self.count_alliance_fuel(pieces, field)
        
        if robot.holding >= robot.capacity:
            if can_score: self.state = "SCORE"
            elif robot.can_pass: self.state = "PASS"
            else: self.state = "FERRY_DUMP"
        elif robot.holding == 0:
            self.state = "GATHER"
        else:
            # We have SOME fuel but not full
            if can_score:
                self.state = "SCORE"
            else:
                # Can't score yet.
                if robot.holding > 0.8 * robot.capacity:
                    if robot.can_pass: self.state = "PASS"
                    else: self.state = "FERRY_DUMP"
                else:
                    self.state = "GATHER"

        # Stuck detection
        dist_moved = self.get_dist(robot.x, robot.y, self.last_x, self.last_y)
        self.last_x, self.last_y = robot.x, robot.y
        
        # If we are trying to move but not moving much, increment stuck timer
        if self.recovery_timer > 0:
            self.recovery_timer -= 1/60.0 # Standard dt approx
        else:
            is_trying_to_move = True # Simplified check
                
            if is_trying_to_move and dist_moved < 0.2: # Less than 0.2 inches per frame
                self.stuck_timer += 1/60.0
            else:
                self.stuck_timer = 0

            if self.stuck_timer > 1.2: # Stuck for > 1.2 second
                self.recovery_timer = 0.8 # Recover for 0.8s
                self.stuck_timer = 0
                self.recovery_rot = 1.0 if math.sin(time.time() * 10) > 0 else -1.0 # Pseudo-random

        # Logic per State
        inputs = {'x': 0, 'y': 0, 'rot': 0, 'shoot_toggle': False, 'pass_toggle': False}
        
        target_x, target_y = robot.x, robot.y
        desired_angle = robot.angle

        if self.recovery_timer > 0:
            # Recovery Behavior: Back up and turn
            inputs['y'] = 1.0 # Reverse
            inputs['rot'] = self.recovery_rot
            return inputs

        if self.state == "GATHER":
            # Find nearest fuel
            nearest_fuel = None
            min_dist = 999999
            
            is_red = robot.alliance == "red"
            
            # 1. Prioritize fuel in our own zone if we can score
            if can_score:
                for fuel in pieces.fuels:
                    if not fuel.collected and fuel.immune_timer <= 0:
                        # Coordination: Avoid fuel being chased by teammates
                        is_targeted = False
                        for other in other_robots:
                            if other != robot and other.alliance == robot.alliance:
                                if self.get_dist(other.x, other.y, fuel.x, fuel.y) < 20: 
                                    is_targeted = True
                                    break
                        
                        if is_targeted and random.random() < 0.7: continue

                        # Skip unbounced (risky) fuel
                        if fuel.bounces == 0: continue

                        # Is it in our zone?
                        in_zone = (is_red and fuel.x < field.divider_x) or (not is_red and fuel.x > (field.width_in - field.divider_x))
                        if in_zone:
                            dist = self.get_dist(robot.x, robot.y, fuel.x, fuel.y)
                            if dist < min_dist:
                                min_dist = dist
                                nearest_fuel = fuel
            
            # 2. If no fuel in our zone (or we can't score yet), check neutral zone
            if not nearest_fuel:
                for fuel in pieces.fuels:
                    if not fuel.collected and fuel.immune_timer <= 0:
                        is_targeted = False
                        for other in other_robots:
                            if other != robot and other.alliance == robot.alliance:
                                if self.get_dist(other.x, other.y, fuel.x, fuel.y) < 20:
                                    is_targeted = True
                                    break
                        if is_targeted and random.random() < 0.7: continue

                        # Skip unbounced (risky) fuel
                        if fuel.bounces == 0: continue

                        # Is it in the neutral zone?
                        in_neutral = field.divider_x < fuel.x < (field.width_in - field.divider_x)
                        # OR is it in our own alliance zone?
                        in_our_zone = (is_red and fuel.x < field.divider_x) or (not is_red and fuel.x > (field.width_in - field.divider_x))
                        
                        if in_neutral or in_our_zone:
                            dist = self.get_dist(robot.x, robot.y, fuel.x, fuel.y)
                            if dist < min_dist:
                                min_dist = dist
                                nearest_fuel = fuel
            
            if nearest_fuel:
                target_x, target_y = nearest_fuel.x, nearest_fuel.y
                # Face the fuel
                desired_angle = math.degrees(math.atan2(target_y - robot.y, target_x - robot.x))

            # Disable auto-modes when gathering
            if robot.auto_shoot_enabled: inputs['shoot_toggle'] = True
            if robot.auto_pass_enabled: inputs['pass_toggle'] = True
        
        elif self.state == "SCORE":
            target_hub = field.hubs[0] if robot.alliance == "red" else field.hubs[1]
            target_x, target_y = target_hub['x'], target_hub['y']
            
            dist = self.get_dist(robot.x, robot.y, target_x, target_y)
            if dist < 120: # Stay a bit away from hub to score
                target_x, target_y = robot.x, robot.y # Stop moving
            
            # Face the hub
            desired_angle = math.degrees(math.atan2(target_y - robot.y, target_x - robot.x))
            
            if robot.check_shoot_range(field) and not robot.auto_shoot_enabled:
                inputs['shoot_toggle'] = True
            
            # Disable other modes
            if robot.auto_pass_enabled:
                inputs['pass_toggle'] = True

        elif self.state == "PASS":
            # Target center of field to wait for passing
            target_x = field.width_in / 2
            target_y = field.length_in / 2
            desired_angle = 0 if robot.alliance == "red" else 180
            
            if not robot.auto_pass_enabled:
                inputs['pass_toggle'] = True
            
            # Disable other modes
            if robot.auto_shoot_enabled:
                inputs['shoot_toggle'] = True

        elif self.state == "FERRY_DUMP":
            is_red = robot.alliance == "red"
            # Target a spot deep in alliance zone
            target_x = 80 if is_red else field.width_in - 80
            target_y = field.length_in / 2
            
            # Are we in alliance zone?
            in_zone = (is_red and robot.x < field.divider_x) or (not is_red and robot.x > (field.width_in - field.divider_x))
            
            if in_zone:
                inputs['disable_intake'] = True
                
                dist = self.get_dist(robot.x, robot.y, target_x, target_y)
                if dist < 20: # Close enough to dump spot
                    inputs['dump_toggle'] = True
                
                if robot.holding == 0:
                    self.state = "GATHER"
            
            desired_angle = math.degrees(math.atan2(target_y - robot.y, target_x - robot.x))

        # --- Hub Avoidance Skirting (Applied to ALL states) ---
        danger_radius = 95
        for hub in field.hubs:
            hub_dist = self.get_dist(robot.x, robot.y, hub['x'], hub['y'])
            if hub_dist < danger_radius:
                # 1. Intake Protection:
                # If we are too close and not explicitly targeting a ball (or targeting one too risky)
                targeting_safe_ball = False
                if self.state == "GATHER" and nearest_fuel:
                    if self.get_dist(nearest_fuel.x, nearest_fuel.y, hub['x'], hub['y']) < 40 and nearest_fuel.bounces > 0:
                         targeting_safe_ball = True
                
                if not targeting_safe_ball:
                    inputs['disable_intake'] = True
                
                # 2. Skirting Logic:
                # nudge the target y to move around the hub
                current_target_dist = self.get_dist(target_x, target_y, hub['x'], hub['y'])
                # If target is on the other side of the hub, nudge our path
                if current_target_dist > hub_dist:
                    offset = 75
                    if robot.y < hub['y']: target_y = hub['y'] - offset
                    else: target_y = hub['y'] + offset
                    desired_angle = math.degrees(math.atan2(target_y - robot.y, target_x - robot.x))

        # Steering Logic
        # 1. Rotation
        angle_diff = (desired_angle - robot.angle + 180) % 360 - 180
        if abs(angle_diff) > 5:
            inputs['rot'] = 1.0 if angle_diff > 0 else -1.0
        
        # 2. Translation
        dist = self.get_dist(robot.x, robot.y, target_x, target_y)
        if dist > 5:
            # Logic for movement...
            if not self.is_tank:
                dx = target_x - robot.x
                dy = target_y - robot.y
                rad = math.radians(robot.angle)
                inputs['y'] = -(dx * math.cos(rad) + dy * math.sin(rad)) / dist
                inputs['x'] = (dx * -math.sin(rad) + dy * math.cos(rad)) / dist
            else:
                if abs(angle_diff) < 30:
                    inputs['y'] = -1.0
        else:
            # Not trying to move anymore
            self.stuck_timer = 0

        return inputs
