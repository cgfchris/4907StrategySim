
import numpy as np
import math

class Navigator:
    def __init__(self, field_config):
        self.field_config = field_config
        self.width = field_config['width_inches']
        self.length = field_config['length_inches']
        self.divider_x = field_config['divider_x']
        
    def get_target_cluster(self, robot, zone_name, sector, pieces_manager, all_robots):
        """
        Finds the best cluster of fuel in the specified zone/sector.
        Scores clusters based on size and distance from TEAMMATES.
        """
        candidates = []
        
        # 1. Filter Fuel by Zone & Sector
        min_x, max_x = 0, self.width
        min_y, max_y = 0, self.length
        
        if zone_name == "alliance":
            max_x = self.divider_x
        elif zone_name == "neutral":
            min_x = self.divider_x
            max_x = self.width - self.divider_x # Assuming symmetric for now, or just neutral zone
            
        if sector == "top":
            min_y = self.length / 2
        elif sector == "bottom":
            max_y = self.length / 2
            
        # Collect valid fuel positions
        valid_fuel = []
        for f in pieces_manager.fuels:
            if not f.collected and min_x <= f.x <= max_x and min_y <= f.y <= max_y:
                valid_fuel.append((f.x, f.y))
                
        if not valid_fuel:
            # Fallback: Go to center of sector
            return (min_x + max_x) / 2, (min_y + max_y) / 2
            
        # 2. Simple Clustering (Grid based for speed)
        # We can just pick the fuel that is furthest from other robots?
        # Or finding the "Center of Mass" of the largest pile.
        # Let's do a quick "Cluster Scoring"
        
        # We will check each fuel piece and count neighbors within 30 inches
        # This is O(N^2), might be slow if N is large. N ~ 50. 50*50 = 2500, fast enough.
        
        best_score = -9999
        best_target = (0, 0)
        
        # Optimization: Just sample every 5th fuel to find centers
        sample_fuel = valid_fuel[::min(len(valid_fuel), 5)] if len(valid_fuel) > 5 else valid_fuel
        
        for fx, fy in sample_fuel:
            # Count neighbors
            count = 0
            for tx, ty in valid_fuel:
                if (fx-tx)**2 + (fy-ty)**2 < 30**2:
                    count += 1
            
            # Penalize proximity to TEAMMATES (excluding self)
            penalty = 0
            for r in all_robots:
                if r == robot: continue
                dist = math.sqrt((fx - r.x)**2 + (fy - r.y)**2)
                # Significant penalty if within 60 inches
                if dist < 60:
                    penalty += (60 - dist) * 2.0 
                    
            score = count * 10 - penalty
            
            if score > best_score:
                best_score = score
                best_target = (fx, fy)
        
        # Clamp Target to avoid walls
        tx = max(20, min(self.width - 20, best_target[0]))
        ty = max(20, min(self.length - 20, best_target[1]))
        
        return tx, ty

    def get_action(self, robot, target_x, target_y):
        """
        Returns (vx, vy, rot) to drive to target.
        """
        dx = target_x - robot.x
        dy = target_y - robot.y
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist < 10:
            return 0, 0, 0 # Arrived
            
        # Normalize
        vx = dx / dist
        vy = dy / dist
        
        # Simple P-Controller
        speed = 1.0
        if dist < 30: speed = dist / 30.0
        
        # Rotation: Face the target? or just face 0?
        # Manager doesn't really care, but facing target helps intake
        # Desired angle
        desired_angle = math.degrees(math.atan2(-dy, dx)) # Pygame Y is flipped? No, simulation is standard Cartesian usually but Pygame is Y-down.
        # Robot angle is standard math?
        # Let's just point towards it.
        # Actually, for Swerve, orientation doesn't matter for movement.
        # But facing it helps intake.
        
        # For now, just drive.
        return vx * speed, vy * speed, 0
