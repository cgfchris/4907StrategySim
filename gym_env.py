import gymnasium as gym
from gymnasium import spaces
import numpy as np
import json
import os
import pygame

# Import simulation components
from robot import Robot
from field import Field
from game_piece import GamePieceManager
from ai import RobotAI

class FrcEnv(gym.Env):
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 60}

    def __init__(self, render_mode=None, config_path="config.json", ml_config_path="ml_config.json"):
        super(FrcEnv, self).__init__()

        # Load configs
        with open(config_path, 'r') as f:
            self.sim_config = json.load(f)
        with open(ml_config_path, 'r') as f:
            self.ml_config = json.load(f)

        self.render_mode = render_mode
        self.fps = 60
        self.dt = 1.0 / self.fps
        self.frames_per_step = self.ml_config['env_params']['frames_per_step']
        
        # Define Action Space: [vx, vy, vrot, shoot_toggle, pass_toggle, dump_toggle]
        # vx, vy, vrot are continuous (-1 to 1)
        # toggles are discrete but we can use a multi-discrete or just treat as continuous and threshold
        # Stable-Baselines3 PPO works well with Box for everything
        self.action_space = spaces.Box(low=-1, high=1, shape=(6,), dtype=np.float32)

        # Observation Space
        # Self: [x, y, angle, holding, alliance(0/1)] - 5
        # Closest Fuel (5): [rel_x, rel_y, bounces, is_immune] - 4 * 5 = 20
        # Grid View (4x4): 16
        # Game State: [time_remaining, phase_active] - 2
        # Strategic: [own_hub_x, own_hub_y, enemy_hub_x, enemy_hub_y] - 4
        # Total: 5 + 20 + 16 + 2 + 4 = 47
        self.observation_space = spaces.Box(low=-1, high=1, shape=(47,), dtype=np.float32)

        self.field = None
        self.pieces = None
        self.robots = []
        self.controlled_robot = None
        self.game_time = 0
        self.match_duration = 160
        self.screen = None
        self.clock = None
        
        # For Reward calculation
        self.last_score = 0
        self.last_holding = 0
        self.total_reward = 0

    def _get_obs(self):
        from ml_utils import get_observation
        return get_observation(
            self.controlled_robot, 
            self.field, 
            self.pieces, 
            self.sim_config, 
            self.game_time, 
            self.match_duration
        )

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        # Re-initialize simulation
        ppi = self.sim_config['field']['pixels_per_inch']
        self.field = Field(self.sim_config['field'])
        self.pieces = GamePieceManager(self.sim_config, ppi)
        self.pieces.spawn_initial(self.sim_config)
        
        self.robots = []
        self.robot_ais = {}
        
        # For now, let's just train 1 robot (Red 1)
        # We can add opponents later for self-play
        r_cfg = self.sim_config['red_alliance'][0]
        self.controlled_robot = Robot(100, self.sim_config['field']['length_inches']/2, r_cfg, "red")
        self.robots.append(self.controlled_robot)
        
        # Add a dummy blue opponent to make it a match
        b_cfg = self.sim_config['blue_alliance'][0]
        blue_bot = Robot(self.sim_config['field']['width_inches'] - 100, self.sim_config['field']['length_inches']/2, b_cfg, "blue")
        self.robots.append(blue_bot)
        self.robot_ais[blue_bot] = RobotAI("blue", b_cfg.get('drivetrain') == "tank")

        self.game_time = 0
        self.last_score = 0
        self.last_holding = 0
        self.total_reward = 0
        
        return self._get_obs(), {}

    def step(self, action):
        reward = 0
        terminated = False
        truncated = False
        
        # Map actions to robot inputs (States, not Toggles)
        ai_inputs = {
            'x': action[0],
            'y': action[1],
            'rot': action[2],
            'shoot_state': action[3] > 0.5,
            'pass_state': action[4] > 0.5,
            'dump_state': action[5] > 0.5
        }

        scored_this_step = 0
        pickups_this_step = 0
        fouls_this_step = 0
        dumped_this_step = 0
        dist_traveled = 0
        last_pos = (self.controlled_robot.x, self.controlled_robot.y)
        
        for _ in range(self.frames_per_step):
            # Update controlled robot
            dummy_keys = [False] * 512
            dummy_ctrl = {'up':0,'down':0,'left':0,'right':0,'rotate_l':0,'rotate_r':0,'shoot_key':0,'pass_key':0,'dump_key':0}
            
            # Check for score and dump
            res = self.controlled_robot.update(self.dt, dummy_keys, dummy_ctrl, self.field, self.game_time, self.robots, self.pieces, True, ai_inputs)
            if isinstance(res, bool) and res:
                scored_this_step += 1
                self.pieces.recycle_fuel(self.controlled_robot, self.sim_config['field'])
            elif isinstance(res, int) and res > 0:
                # Robot.update now returns num_dumped if dump was called
                dumped_this_step += res
            
            # Update other robots (using heuristic AI)
            for robot in self.robots:
                if robot != self.controlled_robot:
                    other_ai_inputs = None
                    if robot in self.robot_ais:
                        other_ai_inputs = self.robot_ais[robot].update(
                            robot, self.field, self.pieces, True, self.robots, 
                            self.game_time, self.match_duration, self.sim_config
                        )
                    robot.update(self.dt, dummy_keys, dummy_ctrl, self.field, self.game_time, self.robots, self.pieces, True, other_ai_inputs)
            
            self.pieces.update(self.robots, self.game_time, self.sim_config)
            
            # Check for penalties (fouls)
            for foul_alliance, amount in self.pieces.penalties:
                if foul_alliance == self.controlled_robot.alliance:
                    fouls_this_step += 1
            
            self.game_time += self.dt
            
            # Track movement for holding reward
            curr_pos = (self.controlled_robot.x, self.controlled_robot.y)
            dist_traveled += ((curr_pos[0]-last_pos[0])**2 + (curr_pos[1]-last_pos[1])**2)**0.5
            last_pos = curr_pos

            if self.game_time >= self.match_duration:
                terminated = True
                break

        # Calculate Reward
        rew_cfg = self.ml_config['reward_shaping']
        reward += scored_this_step * rew_cfg['score_reward']
        # Dump penalty
        reward += dumped_this_step * rew_cfg.get('dump_penalty', 0)
        
        # Pickup reward: check if holding increased
        current_holding = self.controlled_robot.holding
        if current_holding > self.last_holding:
            reward += (current_holding - self.last_holding) * rew_cfg['pickup_reward']
        self.last_holding = current_holding
        
        # Holding reward: reward for moving while holding fuel
        if current_holding > 0:
            reward += dist_traveled * rew_cfg.get('holding_reward_factor', 0)

        # Time penalty
        reward += rew_cfg['time_penalty_per_step']
        
        # Proximity reward (encouragement to move toward fuel)
        if self.controlled_robot.holding < self.controlled_robot.capacity:
            # Find min dist to fuel
            min_dist = 9999
            for fuel in self.pieces.fuels:
                if not fuel.collected:
                    d = ((fuel.x - self.controlled_robot.x)**2 + (fuel.y - self.controlled_robot.y)**2)**0.5
                    if d < min_dist: min_dist = d
            
            # Potential-based reward or just small increment
            # Let's do a simple proximity reward: if we are close, give small bonus
            if min_dist < 50:
                reward += (1.0 / (min_dist + 1.0)) * rew_cfg['proximity_reward_factor']

        self.total_reward += reward
        return self._get_obs(), reward, terminated, truncated, {}

    def render(self):
        if self.render_mode is None:
            return
        
        if self.screen is None:
            pygame.init()
            ppi = self.sim_config['field']['pixels_per_inch']
            w = int(self.sim_config['field']['width_inches'] * ppi)
            h = int(self.sim_config['field']['length_inches'] * ppi)
            if self.render_mode == "human":
                self.screen = pygame.display.set_mode((w, h))
            else:
                self.screen = pygame.Surface((w, h))
            self.clock = pygame.time.Clock()
            self.font = pygame.font.SysFont("Arial", 18)

        # Drawing logic (similar to main.py)
        ppi = self.sim_config['field']['pixels_per_inch']
        self.screen.fill((30, 30, 30))
        self.field.draw(self.screen, ppi)
        self.pieces.draw(self.screen, ppi)
        for robot in self.robots:
            robot.draw(self.screen, ppi, self.font)
            
        # Draw some ML info
        score_text = self.font.render(f"Reward: {self.total_reward:.1f} Time: {self.game_time:.1f}s", True, (255, 255, 255))
        self.screen.blit(score_text, (20, 20))

        if self.render_mode == "human":
            pygame.display.flip()
            # self.clock.tick(self.fps) # Don't limit during training unless human mode is on
        elif self.render_mode == "rgb_array":
            return np.transpose(np.array(pygame.surfarray.pixels3d(self.screen)), axes=(1, 0, 2))

    def close(self):
        if self.screen is not None:
            pygame.quit()
