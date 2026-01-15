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
        elif self.mode == "lobber":
            if robot.x < self.sim_config['field']['divider_x']:
                reward -= 5.0 # Penalty for crossing into alliance zone

        return obs, reward, terminated, truncated, info
