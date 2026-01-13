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
        count = 0
        is_red = self.alliance == "red"
        for fuel in pieces.fuels:
            if not fuel.collected:
                # Check if in alliance zone
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
            if can_score:
                self.state = "SCORE"
            else:
                self.state = "PASS"
        elif robot.holding == 0:
            # If there's plenty of fuel in our zone, we should definitely stay to gather/score
            if alliance_fuel > 5:
                self.state = "GATHER"
            else:
                self.state = "GATHER" # Default
        else:
            # If we have some fuel, decide based on scoring permission OR zone abundance
            if can_score:
                self.state = "SCORE"
            elif alliance_fuel > 10:
                # If zone is packed, maybe we just wait or gather more to score later
                # For now, let's say if we have fuel and zone is full, we should SCORE if we can
                self.state = "SCORE" if can_score else "PASS"
            else:
                self.state = "PASS"

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
                                    if self.get_dist(other.x, other.y, fuel.x, fuel.y) < 20: # Someone is very close
                                        is_targeted = True
                                        break
                            
                            if is_targeted and random.random() < 0.7: continue # 70% chance to look for something else

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

                        dist = self.get_dist(robot.x, robot.y, fuel.x, fuel.y)
                        if dist < min_dist:
                            min_dist = dist
                            nearest_fuel = fuel
            
            if nearest_fuel:
                target_x, target_y = nearest_fuel.x, nearest_fuel.y
                # Face the fuel
                desired_angle = math.degrees(math.atan2(target_y - robot.y, target_x - robot.x))
        
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
        
        elif self.state == "PASS":
            # Target neutral zone center but facing alliance
            is_red = robot.alliance == "red"
            target_x = field.width_in / 2
            target_y = field.length_in / 2
            
            # Face toward alliance zone for passing
            pass_target_x = 0 if is_red else field.width_in
            desired_angle = math.degrees(math.atan2(target_y - robot.y, pass_target_x - robot.x))
            
            if not robot.auto_pass_enabled:
                inputs['pass_toggle'] = True

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
