import gymnasium as gym
from gymnasium import spaces
import numpy as np
import json
import os
from gym_env import FrcEnv
from ml_utils import get_observation

class SpecializedFrcEnv(FrcEnv):
    """
    A specialized environment for training Station Workers (Janitors, Lobbers).
    Allows for 'Target Zones' where the robot is rewarded for proximity and stay.
    """
    def __init__(self, render_mode=None, config_path="config.json", ml_config_path="ml_config.json", mode="janitor"):
        super(SpecializedFrcEnv, self).__init__(render_mode, config_path, ml_config_path)
        self.mode = mode # 'janitor' or 'lobber'
        self.model_time = None # New: for watch script overlay
        self.disable_recycling = True # Lab Mode: No Hub Ejection
        
        # Define the center of the target zone
        # Janitor: Alliance Zone (e.g., at the alliance wall)
        # Lobber: Neutral Zone (e.g., center of neutral area)
        if self.mode == "janitor":
            self.target_x = self.sim_config['field']['width_inches'] * 0.1 # Near wall
            self.target_y = self.sim_config['field']['length_inches'] * 0.5
        else: # lobber
            self.target_x = self.sim_config['field']['width_inches'] * 0.5 # Near center (neutral)
            self.target_y = self.sim_config['field']['length_inches'] * 0.5
        
        self.disable_outposts = True
        # Specialized "Scoring Lab" settings
        self.match_duration = 20 # Turbo matches (20s)

    def _get_can_score(self, alliance):
        # Lobbers are for passing, not scoring. Disabling scoring forces stashing rewards.
        if self.mode == "lobber":
            return False
        return super()._get_can_score(alliance)

    def _get_obs(self):
        # We pass target_x and target_y as the new 'Strategic' features to replace redundant ones
        return get_observation(
            self.controlled_robot, 
            self.field, 
            self.pieces, 
            self.sim_config, 
            self.game_time, 
            self.match_duration, 
            can_score=self._get_can_score(self.controlled_robot.alliance),
            can_pass=(self.mode == "lobber"),
            target_x=self.target_x,
            target_y=self.target_y
        )

    def reset(self, seed=None, options=None):
        # 1. Standard Reset
        obs, info = super().reset(seed=seed, options=options)
        self.match_duration = 20.0 # Force override again after super.reset
        
        # 2. Lab Isolation: Remove other robots
        # (FrcEnv.reset adds a Red 1 and potentially opponents)
        self.robots = [self.controlled_robot]
        
        # FIX: Spawn robot in its assigned zone!
        # Don't let it start at the wall and have to drive 100 inches.
        # Add small random noise so it doesn't overfit to an exact pixel.
        self.controlled_robot.x = self.target_x + np.random.uniform(-10, 10)
        self.controlled_robot.y = self.target_y + np.random.uniform(-10, 10)
        self.controlled_robot.angle = 0 if self.mode == "lobber" else 180 # Face the pile/goal
        
        # 3. Lab Fuel: Clear standard scatter and spawn concentrated piles
        from game_piece import Fuel
        self.pieces.fuels = [] # Wipe the field
        
        field_w = self.sim_config['field']['width_inches']
        field_h = self.sim_config['field']['length_inches']
        divider_x = self.sim_config['field']['divider_x']
        
        if self.mode == "janitor":
            # Janitor: Piles in the Alliance Zone (X: 0 to divider_x)
            num_balls = np.random.randint(35, 50)
            
            # Generate 1-2 random "Pile Centers"
            # We want them somewhat central in the zone, not hugging the very edge
            num_clusters = np.random.randint(1, 3)
            centers = []
            for _ in range(num_clusters):
                cx = np.random.uniform(40, divider_x - 40)
                cy = np.random.uniform(40, field_h - 40)
                centers.append((cx, cy))
                
            for _ in range(num_balls):
                # 70% chance to be in a pile, 30% chance to be random scatter
                if np.random.random() < 0.7:
                    # Pick a random cluster
                    cx, cy = centers[np.random.randint(0, num_clusters)]
                    # Gaussian scatter (Standard Deviation ~25 inches) gives a nice "Heap" look
                    rx = np.random.normal(cx, 25)
                    ry = np.random.normal(cy, 25)
                else:
                    rx = np.random.uniform(20, divider_x - 10)
                    ry = np.random.uniform(20, field_h - 20)
                
                # Clamp to bounds
                rx = max(10, min(divider_x - 5, rx))
                ry = max(10, min(field_h - 10, ry))
                
                f = Fuel(rx, ry, self.pieces.ppi, "lab")
                f.bounces = 1 
                self.pieces.fuels.append(f)
        else:
            # Lobber: Piles in the Neutral Zone
            num_balls = np.random.randint(35, 50)
            
            num_clusters = np.random.randint(1, 3)
            centers = []
            for _ in range(num_clusters):
                cx = np.random.uniform(divider_x + 40, (field_w - divider_x) - 40)
                cy = np.random.uniform(40, field_h - 40)
                centers.append((cx, cy))

            for _ in range(num_balls):
                if np.random.random() < 0.7:
                    cx, cy = centers[np.random.randint(0, num_clusters)]
                    rx = np.random.normal(cx, 25)
                    ry = np.random.normal(cy, 25)
                else:
                    rx = np.random.uniform(divider_x + 10, (field_w - divider_x) - 10)
                    ry = np.random.uniform(20, field_h - 20)
                
                # Clamp
                rx = max(divider_x + 5, min(field_w - divider_x - 5, rx))
                ry = max(10, min(field_h - 10, ry))

                f = Fuel(rx, ry, self.pieces.ppi, "lab")
                f.bounces = 1
                self.pieces.fuels.append(f)
                
        return self._get_obs(), info

    def step(self, action):
        # Execute the standard step
        obs, reward, terminated, truncated, info = super(SpecializedFrcEnv, self).step(action)
        
        # Add Specialized Station Rewards
        robot = self.controlled_robot
        dist_to_target = np.sqrt((robot.x - self.target_x)**2 + (robot.y - self.target_y)**2)
        field_width = self.sim_config['field']['width_inches']
        
        # 1. Proximity Reward (Small nudge to stay in zone)
        # Max reward of +0.5 per step when at the center, dropping to 0 when far away
        prox_reward = 0.5 * (1.0 - min(1.0, dist_to_target / (field_width * 0.3)))
        reward += prox_reward
        
        # 2. Hard Boundary Penalty (Optional: to really discourage leaving)
        if self.mode == "janitor":
            if robot.x > self.sim_config['field']['divider_x']:
                reward -= 5.0 # Penalty for crossing into neutral zone
        if self.mode == "lobber":
            if (robot.alliance == "red" and robot.x < self.sim_config['field']['divider_x']) or \
               (robot.alliance == "blue" and robot.x > self.sim_config['field']['divider_x']):
                reward -= 5.0 # Penalty for crossing into alliance/scoring zone



        # 3. Completion Bonus (+1000 for clearing the zone)
        # We need to count valid balls remaining
        valid_balls = 0
        divider_x = self.sim_config['field']['divider_x']
        field_w = self.sim_config['field']['width_inches']
        
        for f in self.pieces.fuels:
            if not f.collected:
                if self.mode == "janitor":
                    if f.x < divider_x: valid_balls += 1
                else:
                    if f.x > divider_x and f.x < (field_w - divider_x): valid_balls += 1
        
        # We need to track 'balls_last_step' to trigger only ONCE per clear
        if not hasattr(self, 'last_valid_balls'): self.last_valid_balls = 999
        
        # Progressive Bonus (Vacuum Incentive)
        # 3 left -> +100
        # 2 left -> +200
        # 1 left -> +300
        # 0 left -> +1000
        if valid_balls < self.last_valid_balls:
            if valid_balls == 3: reward += 100.0
            elif valid_balls == 2: reward += 200.0
            elif valid_balls == 1: reward += 300.0
            elif valid_balls == 0: 
                reward += 1000.0
                info['completion_bonus'] = True
            
        self.last_valid_balls = valid_balls

        return obs, reward, terminated, truncated, info

    def render(self):
        # Call base render (which now calls our hook)
        return super().render()

    def _draw_extra_overlays(self):
        if self.render_mode is not None and self.screen is not None:
            import pygame
            ppi = self.sim_config['field']['pixels_per_inch']
            
            # Draw Target Station (Vibrant cyan/yellow pulse)
            color = (0, 255, 255, 100) if self.mode == "lobber" else (255, 255, 0, 100)
            target_surf = pygame.Surface((100, 100), pygame.SRCALPHA)
            pygame.draw.circle(target_surf, color, (50, 50), 40)
            self.screen.blit(target_surf, (int(self.target_x * ppi) - 50, int(self.target_y * ppi) - 50))
            
            # Draw Mode Label & Model Time
            if hasattr(self, 'font'):
                label = self.font.render(f"MODE: {self.mode.upper()}", True, (255, 255, 255))
                self.screen.blit(label, (self.screen.get_width() // 2 - label.get_width() // 2, 50))
                
                # Draw Model Time (Top-Right)
                # Draw Model Time (Top-Right)
                if self.model_time:
                    ts_text = self.font.render(f"Saved: {self.model_time}", True, (255, 255, 0))
                    self.screen.blit(ts_text, (self.screen.get_width() - ts_text.get_width() - 20, 20))
                    
                # Draw Model Steps (Top-Right, below time)
                if hasattr(self, 'model_steps') and self.model_steps:
                    st_text = self.font.render(f"Steps: {self.model_steps}", True, (0, 255, 255))
                    self.screen.blit(st_text, (self.screen.get_width() - st_text.get_width() - 20, 45))
