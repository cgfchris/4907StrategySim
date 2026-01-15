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
        # Self: [x, y, sin(a), cos(a), holding, alliance(0/1)] - 6
        # Closest Fuel (5): [rel_x, rel_y, bounces, is_immune] - 4 * 5 = 20
        # Grid View (4x4): 16
        # Game State: [time_remaining, phase_active] - 2
        # Strategic: [rel_own_hub_x, rel_own_hub_y, rel_enemy_hub_x, rel_enemy_hub_y] - 4
        # Total: 6 + 20 + 16 + 2 + 4 = 48
        self.observation_space = spaces.Box(low=-1, high=1, shape=(48,), dtype=np.float32)

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

    def _get_can_score(self, alliance):
        # Mirroring main.py state machine (simplified for 1v1 Red training)
        if 0 <= self.game_time < 30: 
            return True # AUTO + TRANSITION
        elif 30 <= self.game_time < 130:
            stage_idx = int((self.game_time - 30) // 25)
            # Default [red, blue, red, blue]
            stage_alliances = ["red", "blue", "red", "blue"]
            return stage_alliances[stage_idx] == alliance
        elif 130 <= self.game_time < 160: 
            return True # ENDGAME
        return False

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
        self.total_scored = 0
        self.last_can_score = True
        self.last_min_dist = 999.0
        self.last_hub_dist = 999.0
        self.last_robot_x = self.controlled_robot.x
        self.ep_rewards = {
            'rew_score': 0.0,
            'rew_pickup': 0.0,
            'rew_proximity': 0.0,
            'rew_hub_proximity': 0.0,
            'rew_stashing': 0.0,
            'rew_time': 0.0,
            'rew_steer': 0.0,
            'rew_dump': 0.0
        }
        
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
        passed_this_step = 0
        dist_traveled = 0
        last_pos = (self.controlled_robot.x, self.controlled_robot.y)
        
        for _ in range(self.frames_per_step):
            # Match Phase Scoring Check
            if self.ml_config['env_params'].get('enforce_phases', True):
                can_score_red = self._get_can_score("red")
                can_score_blue = self._get_can_score("blue")
            else:
                can_score_red = True
                can_score_blue = True
            
            # Update controlled robot
            dummy_keys = [False] * 512
            dummy_ctrl = {'up':0,'down':0,'left':0,'right':0,'rotate_l':0,'rotate_r':0,'shoot_key':0,'pass_key':0,'dump_key':0}
            
            # Check for score and dump
            # Check for score, dump, and pass
            res = self.controlled_robot.update(self.dt, dummy_keys, dummy_ctrl, self.field, self.game_time, self.robots, self.pieces, can_score_red, ai_inputs)
            if isinstance(res, dict):
                scored_this_step += res['scored']
                self.total_scored += res['scored']
                dumped_this_step += res['dumped']
                passed_this_step += res['passed']
                if res['scored'] > 0:
                    self.pieces.recycle_fuel(self.controlled_robot, self.sim_config['field'])
            
            # Update other robots (using heuristic AI)
            for robot in self.robots:
                if robot != self.controlled_robot:
                    can_score_other = can_score_red if robot.alliance == "red" else can_score_blue
                    other_ai_inputs = None
                    if robot in self.robot_ais:
                        other_ai_inputs = self.robot_ais[robot].update(
                            robot, self.field, self.pieces, can_score_other, self.robots, 
                            self.game_time, self.match_duration, self.sim_config
                        )
                    other_res = robot.update(self.dt, dummy_keys, dummy_ctrl, self.field, self.game_time, self.robots, self.pieces, can_score_other, other_ai_inputs)
                    if isinstance(other_res, dict) and other_res.get('scored'):
                        self.pieces.recycle_fuel(robot, self.sim_config['field'])
            
            self.pieces.update(self.robots, self.game_time, self.sim_config)
            
            # Check for penalties (fouls)
            for foul_alliance, amount in self.pieces.penalties:
                if foul_alliance == self.controlled_robot.alliance:
                    fouls_this_step += 1
            
            self.game_time += self.dt
            self.last_can_score = can_score_red
            
            # Track movement for holding reward
            curr_pos = (self.controlled_robot.x, self.controlled_robot.y)
            dist_traveled += ((curr_pos[0]-last_pos[0])**2 + (curr_pos[1]-last_pos[1])**2)**0.5
            last_pos = curr_pos

            if self.game_time >= self.match_duration:
                terminated = True
                break

        # Calculate Reward
        rew_cfg = self.ml_config['reward_shaping']
        
        rew_score = scored_this_step * rew_cfg['score_reward']
        rew_dump = dumped_this_step * rew_cfg.get('dump_penalty', 0)
        
        # Pickup reward: check if holding increased
        current_holding = self.controlled_robot.holding
        # Net change = change in holding + (scores + passes + dumps) 
        # (prevents penalty for losing holding during intentional actions)
        rew_pickup = (current_holding - self.last_holding + scored_this_step + passed_this_step + dumped_this_step) * rew_cfg['pickup_reward']
        self.last_holding = current_holding
        
        # Hub proximity vs Stashing Reward
        rew_hub_proxim = 0.0
        rew_stashing = 0.0
        if current_holding > 0 or scored_this_step > 0 or passed_this_step > 0 or dumped_this_step > 0:
            own_hub = self.field.hubs[0] if self.controlled_robot.alliance == "red" else self.field.hubs[1]
            dist_to_hub = ((own_hub['x'] - self.controlled_robot.x)**2 + (own_hub['y'] - self.controlled_robot.y)**2)**0.5
            
            if self.last_can_score:
                # Delta hub distance
                hub_delta = self.last_hub_dist - dist_to_hub
                if abs(hub_delta) < 50:
                    rew_hub_proxim = hub_delta * rew_cfg.get('hub_proximity_reward_factor', 0)
            else:
                # Goal Line Stashing Reward (1-foot buffer past divider)
                is_red = self.controlled_robot.alliance == "red"
                field_cfg = self.sim_config['field']
                
                # The "Goal Line" is 12 inches inside the alliance zone to clear bumps/trench
                if is_red:
                    goal_line_x = field_cfg['divider_x'] - 12
                    dist_to_line = max(0, self.controlled_robot.x - goal_line_x)
                    last_dist_to_line = max(0, self.last_robot_x - goal_line_x)
                else:
                    goal_line_x = (field_cfg['width_inches'] - field_cfg['divider_x']) + 12
                    dist_to_line = max(0, goal_line_x - self.controlled_robot.x)
                    last_dist_to_line = max(0, goal_line_x - self.last_robot_x)

                progress = last_dist_to_line - dist_to_line
                shuttle_factor = rew_cfg.get('stashing_reward_factor', 0)
                
                # Reward progress carrying fuel + one-time bonus for passing it over the line
                rew_stashing = progress * current_holding * shuttle_factor + (passed_this_step + dumped_this_step) * dist_to_line * shuttle_factor
            
            self.last_robot_x = self.controlled_robot.x
            self.last_hub_dist = dist_to_hub
        else:
            self.last_robot_x = self.controlled_robot.x
            self.last_hub_dist = 999.0
        
        # Proximity reward (encouragement to move toward fuel)
        rew_proxim = 0.0
        if self.controlled_robot.holding < self.controlled_robot.capacity:
            min_dist = 9999
            for fuel in self.pieces.fuels:
                if not fuel.collected:
                    d = ((fuel.x - self.controlled_robot.x)**2 + (fuel.y - self.controlled_robot.y)**2)**0.5
                    if d < min_dist: min_dist = d
            
            if min_dist < 999:
                dist_delta = self.last_min_dist - min_dist
                if abs(dist_delta) < 100:
                    rew_proxim = dist_delta * rew_cfg['proximity_reward_factor']
            self.last_min_dist = min_dist
        else:
            self.last_min_dist = 999.0

        rew_time = rew_cfg.get('time_penalty_per_step', 0)
        rew_steer = abs(action[2]) * rew_cfg.get('steering_penalty_factor', 0)

        step_reward = rew_score + rew_dump + rew_pickup + rew_hub_proxim + rew_stashing + rew_proxim + rew_time + rew_steer
        
        # Accumulate for breakdown
        self.ep_rewards['rew_score'] += rew_score
        self.ep_rewards['rew_pickup'] += rew_pickup
        self.ep_rewards['rew_proximity'] += rew_proxim
        self.ep_rewards['rew_hub_proximity'] += rew_hub_proxim
        self.ep_rewards['rew_stashing'] += rew_stashing
        self.ep_rewards['rew_time'] += rew_time
        self.ep_rewards['rew_steer'] += rew_steer
        self.ep_rewards['rew_dump'] += rew_dump
        
        self.total_reward += step_reward
        
        info = { 'scored': self.total_scored }
        if terminated or truncated:
            # At the end of episode, pass the full breakdown
            info.update(self.ep_rewards)
            
        return self._get_obs(), step_reward, terminated, truncated, info

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
