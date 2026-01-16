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
        self.match_duration = 30 # Turbo matches (30s)

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
        self.match_duration = 30.0 # Force override again after super.reset
        
        # 2. Lab Isolation: Remove other robots
        # (FrcEnv.reset adds a Red 1 and potentially opponents)
        self.robots = [self.controlled_robot]
        
        # 3. Lab Fuel: Clear standard scatter and spawn concentrated piles
        from game_piece import Fuel
        self.pieces.fuels = [] # Wipe the field
        
        field_w = self.sim_config['field']['width_inches']
        field_h = self.sim_config['field']['length_inches']
        divider_x = self.sim_config['field']['divider_x']
        
        if self.mode == "janitor":
            # Piles in the Alliance Zone (X: 0 to divider_x)
            num_balls = np.random.randint(50, 80)
            for _ in range(num_balls):
                rx = np.random.uniform(20, divider_x - 10)
                ry = np.random.uniform(20, field_h - 20)
                f = Fuel(rx, ry, self.pieces.ppi, "lab")
                f.bounces = 1 # Safe to pick up
                self.pieces.fuels.append(f)
        else:
            # Piles in the Neutral Zone (X: divider_x to field_w - divider_x)
            num_balls = np.random.randint(70, 100)
            for _ in range(num_balls):
                # Neutral zone is the middle chunk
                rx = np.random.uniform(divider_x + 10, (field_w - divider_x) - 10)
                ry = np.random.uniform(20, field_h - 20)
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
                reward -= 20.0 # Heavy penalty for crossing into alliance/scoring zone

        return obs, reward, terminated, truncated, info

    def render(self):
        # First call the base render to draw the field/robots
        res = super().render()
        if self.render_mode is not None and self.screen is not None:
            import pygame
            ppi = self.sim_config['field']['pixels_per_inch']
            
            # Draw Target Station (Vibrant cyan/yellow pulse)
            color = (0, 255, 255, 100) if self.mode == "lobber" else (255, 255, 0, 100)
            target_surf = pygame.Surface((100, 100), pygame.SRCALPHA)
            pygame.draw.circle(target_surf, color, (50, 50), 40)
            self.screen.blit(target_surf, (int(self.target_x * ppi) - 50, int(self.target_y * ppi) - 50))
            
            # Draw Mode Label
            if hasattr(self, 'font'):
                label = self.font.render(f"MODE: {self.mode.upper()}", True, (255, 255, 255))
                self.screen.blit(label, (self.screen.get_width() // 2 - label.get_width() // 2, 50))

        return res
