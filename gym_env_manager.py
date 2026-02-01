
import gymnasium as gym
from gymnasium import spaces
import numpy as np
import os
import pygame
from gym_env import FrcEnv
from navigator import Navigator
from stable_baselines3 import PPO

class ManagerFrcEnv(FrcEnv):
    def __init__(self, render_mode=None, config_path="config.json", ml_config_path="ml_config.json"):
        super(ManagerFrcEnv, self).__init__(render_mode, config_path, ml_config_path)
        
        # 1. Action Space (Orders)
        # 3 Robots, 5 Actions each
        # 0: Idle, 1: All_Top, 2: All_Bot, 3: Neu_Top, 4: Neu_Bot
        self.action_space = spaces.MultiDiscrete([5, 5, 5])
        
        # 2. Observation Space (Admiral's View)
        # Global: [Time, ScoreDiff, Stage, CanScore, 
        #          Fuel_Alliance, Fuel_Neutral, Fuel_Source] (7)
        # Robots (3x): [x, y, holding, order, status] (5*3 = 15)
        # Total: 22
        self.observation_space = spaces.Box(low=-np.inf, high=np.inf, shape=(22,), dtype=np.float32)
        
        self.manager_step_rate = 60 # 1 second per decision
        self.navigator = None # Init in reset
        
        # Override match duration for faster training cycles
        mgr_params = self.ml_config.get('manager_training_params', {})
        self.mini_match = mgr_params.get('mini_match', False)
        
        if self.mini_match:
            self.match_duration = 80.0
            print(f"Manager Training: Mini-Match Mode Enabled (Duration: {self.match_duration}s)")
        elif 'match_duration' in mgr_params:
            self.match_duration = mgr_params['match_duration']
            print(f"Manager Training: Match Duration overridden to {self.match_duration}s")
        
        # Load Sub-Models from Config
        mgr = self.ml_config.get('manager_config', {})
        self.janitor_path = mgr.get('janitor_model_path', 'ml_models/janitor_default/best_model.zip')
        self.lobber_path = mgr.get('lobber_model_path', 'ml_models/lobber_default/best_model.zip')
        
        self.janitor_model = self._load_model(self.janitor_path, "Janitor")
        self.lobber_model = self._load_model(self.lobber_path, "Lobber")
        
        self.robot_orders = [0, 0, 0] # Current order for each robot
        self.robot_targets = [(0,0), (0,0), (0,0)]
        self.worker_interval = 6 # Default to optimized
        
    def set_worker_interval(self, interval):
        self.worker_interval = interval
        
    def _load_model(self, path, name):
        if os.path.exists(path):
            print(f"Manager loaded {name}: {path}")
            try:
                return PPO.load(path)
            except:
                print(f"FAILED to load {name} model at {path}")
                return None
        else:
            print(f"WARNING: {name} model not found at {path}")
            return None

    def reset(self, seed=None, options=None):
        # 1. Reset Field & Fuel (via super)
        obs, info = super().reset(seed=seed, options=options)
        
        # 2. Randomize Auto Result for Mini-Match
        if self.mini_match:
            # 50% chance Red won auto -> Red plays in Stage 2 (Winner)
            # 50% chance Red lost auto -> Red plays in Stage 1 (Loser)
            self.red_won_auto = np.random.choice([True, False])
        else:
            self.red_won_auto = True # Default for full match
        
        # 3. CLEAR the default 1v1 robots
        self.robots = []
        self.robot_ais = {}
        
        # 4. Spawn 3 Red Robots (3v0 Match)
        from robot import Robot
        
        l = self.sim_config['field']['length_inches']
        spawn_y = [l/4, l/2, 3*l/4]
        
        # Ensure we have enough configs
        configs = self.sim_config['red_alliance']
        
        for i in range(3):
            cfg = configs[i % len(configs)] # Cycle if fewer configs
            # Spawn near the alliance wall (x=50)
            r = Robot(50, spawn_y[i % len(spawn_y)], cfg, "red")
            self.robots.append(r)
            
        self.controlled_robot = self.robots[0] # Just for camera centering if needed
        
        self.navigator = Navigator(self.sim_config['field'])
        self.robot_orders = [0, 0, 0]
        return self._get_global_obs(), info

    def _get_can_score(self, alliance):
        if not self.mini_match:
            return super()._get_can_score(alliance)

        # Mini-Match Logic (Overrides FrcEnv)
        # 0-10s: Auto (Both/Red)
        # 10-15s: Transition (Both/Red)
        # 15-40s: Stage 1 (Loser)
        # 40-65s: Stage 2 (Winner)
        # 65-80s: Endgame (Both)
        
        if self.game_time < 15: return True
        if self.game_time >= 65: return True
        
        is_red = (alliance == "red")
        
        if self.game_time < 40: # Stage 1 (Loser)
            # If Red Won Auto, Red is Winner. Loser is Blue. So Red Cannot.
            # If Red Lost Auto, Red is Loser. Loser is Red. So Red Can.
            if is_red: return not self.red_won_auto
            else: return self.red_won_auto
            
        if self.game_time < 65: # Stage 2 (Winner)
            if is_red: return self.red_won_auto
            else: return not self.red_won_auto
            
        return False
        
    def _get_global_obs(self):
        # 1. Global Stats
        time_norm = self.game_time / self.match_duration
        score_diff = (self.total_scored - 0) / 100.0 # Placeholder for Blue score
        stage = 0 
        
        if self.mini_match:
            if self.game_time < 15: stage = 0 # Auto + Transition
            elif self.game_time < 40: stage = 1 # Stage 1
            elif self.game_time < 65: stage = 2 # Stage 2
            else: stage = 3 # Endgame
        else:
            if self.game_time < 15: stage = 0 # Auto
            elif self.game_time < 130: stage = 1 # Teleop
            else: stage = 2 # Endgame
        
        can_score = 1.0 if self._get_can_score("red") else 0.0
        
        # 2. Fuel Counts (Grid 11x4)
        fuel_grid = self.pieces.get_grid_counts(self.field, 11, 4)
        
        return np.concatenate([
            np.array([time_norm, score_diff, stage, can_score]),
            fuel_grid.flatten()
        ])
        
    def set_worker_interval(self, interval):
        self.worker_interval = interval
        
    def _load_model(self, path, name):
        if os.path.exists(path):
            print(f"Manager loaded {name}: {path}")
            try:
                return PPO.load(path)
            except:
                print(f"FAILED to load {name} model at {path}")
                return None
        else:
            print(f"WARNING: {name} model not found at {path}")
            return None

    def reset(self, seed=None, options=None):
        # 1. Reset Field & Fuel (via super)
        obs, info = super().reset(seed=seed, options=options)
        
        # 2. Randomize Auto Result for Mini-Match
        if self.mini_match:
            # 50% chance Red won auto -> Red plays in Stage 2 (Winner)
            # 50% chance Red lost auto -> Red plays in Stage 1 (Loser)
            self.red_won_auto = np.random.choice([True, False])
        else:
            self.red_won_auto = True # Default for full match
        
        # 3. CLEAR the default 1v1 robots
        self.robots = []
        self.robot_ais = {}
        
        # 4. Spawn 3 Red Robots (3v0 Match)
        from robot import Robot
        
        l = self.sim_config['field']['length_inches']
        spawn_y = [l/4, l/2, 3*l/4]
        
        # Ensure we have enough configs
        configs = self.sim_config['red_alliance']
        
        for i in range(3):
            cfg = configs[i % len(configs)] # Cycle if fewer configs
            # Spawn near the alliance wall (x=50)
            r = Robot(50, spawn_y[i % len(spawn_y)], cfg, "red")
            self.robots.append(r)
            
        self.controlled_robot = self.robots[0] # Just for camera centering if needed
        
        self.navigator = Navigator(self.sim_config['field'])
        self.robot_orders = [0, 0, 0]
        self.robot_location_status = [False, False, False]
        return self._get_global_obs(), info

    def _get_can_score(self, alliance):
        if not self.mini_match:
            return super()._get_can_score(alliance)

        # Mini-Match Logic (Overrides FrcEnv)
        # 0-10s: Auto (Both/Red)
        # 10-15s: Transition (Both/Red) - USER CORRECTION
        # 15-40s: Stage 1 (Loser)
        # 40-65s: Stage 2 (Winner)
        
        if self.game_time < 15: return True
        if self.game_time >= 65: return True # Endgame (Both Score)
        
        is_red = (alliance == "red")
        
        if self.game_time < 40: # Stage 1 (Loser)
            # If Red Won Auto, Red is Winner. Loser is Blue. So Red Cannot.
            # If Red Lost Auto, Red is Loser. Loser is Red. So Red Can.
            if is_red: return not self.red_won_auto
            else: return self.red_won_auto
            
        if self.game_time < 65: # Stage 2 (Winner)
            if is_red: return self.red_won_auto
            else: return not self.red_won_auto
            
        return False
        
    def _get_global_obs(self):
        # 1. Global Stats
        time_norm = self.game_time / self.match_duration
        score_diff = (self.total_scored - 0) / 100.0 # Placeholder for Blue score
        stage = 0 
        
        if self.mini_match:
            if self.game_time < 15: stage = 0 # Auto + Transition
            elif self.game_time < 40: stage = 1 # Stage 1
            elif self.game_time < 65: stage = 2 # Stage 2
        else:
            if self.game_time < 15: stage = 0 # Auto
            elif self.game_time < 130: stage = 1 # Teleop
            else: stage = 2 # Endgame
        
        can_score = 1.0 if self._get_can_score("red") else 0.0
        
        # Fuel Counts (Grid Approximation)
        f_alliance = 0
        f_neutral = 0
        div_x = self.sim_config['field']['divider_x']
        for f in self.pieces.fuels:
            if not f.collected:
                if f.x < div_x: f_alliance += 1
                elif f.x < (self.sim_config['field']['width_inches'] - div_x): f_neutral += 1
        
        global_obs = [time_norm, score_diff, stage, can_score, f_alliance/50.0, f_neutral/50.0, 0.0]
        
        # 2. Robot Stats
        for i, r in enumerate(self.robots):
            if i >= 3: break # Only track first 3
            
            # Status: 0=Idle, 1=Driving, 2=Working
            status = 0
            if self.robot_orders[i] == 0: status = 0
            elif self._is_in_position(r, self.robot_orders[i]): status = 2
            else: status = 1
            
            global_obs.extend([
                r.x / self.sim_config['field']['width_inches'],
                r.y / self.sim_config['field']['length_inches'],
                r.holding / r.capacity,
                self.robot_orders[i] / 4.0, # Norm order
                status / 2.0
            ])
            
        # Pad if fewer than 3 robots
        while len(global_obs) < 22:
            global_obs.append(0.0)
            
        return np.array(global_obs, dtype=np.float32)

    def _is_in_position(self, robot, order, buffer=0):
        # Check if robot is in the correct Zone for the order
        if order in [1, 2]: # Alliance
            # x < div_x + buffer
            return robot.x < (self.sim_config['field']['divider_x'] + buffer)
        if order in [3, 4]: # Neutral
            div_x = self.sim_config['field']['divider_x']
            # x > div_x - buffer AND x < W - div_x + buffer
            return robot.x > (div_x - buffer) and robot.x < (self.sim_config['field']['width_inches'] - div_x + buffer)
        return False

    def step(self, action):
        # Action is [Order_R1, Order_R2, Order_R3]
        self.robot_orders = action
        
        total_reward = 0
        terminated = False
        truncated = False
        
        # Run Physics Loop (Manager Step Duration)
        # Optimization: Update Worker policies only every N frames (Action Repeat)
        
        for step_idx in range(self.manager_step_rate):
            
            # Control Robots (Update Actions at N Hz)
            if step_idx % self.worker_interval == 0:
                for i, robot in enumerate(self.robots):
                    if i >= 3: continue
                    order = action[i]
                    
                    robot_action = np.zeros(6) 
                    
                    target_zone = None
                    target_sector = None
                    worker_model = None
                    
                    if order == 1: target_zone, target_sector, worker_model = "alliance", "top", self.janitor_model
                    elif order == 2: target_zone, target_sector, worker_model = "alliance", "bottom", self.janitor_model
                    elif order == 3: target_zone, target_sector, worker_model = "neutral", "top", self.lobber_model
                    elif order == 4: target_zone, target_sector, worker_model = "neutral", "bottom", self.lobber_model
                    
                    if target_zone:
                        # Hysteresis Logic
                        was_in_pos = self.robot_location_status[i]
                        buf = 15.0 if was_in_pos else 0.0 # 15 inch buffer (Keep working even if slightly out)
                        
                        is_in_pos = self._is_in_position(robot, order, buffer=buf)
                        self.robot_location_status[i] = is_in_pos
                        
                        if is_in_pos:
                            # WORKER MODE
                            if worker_model:
                                from ml_utils import get_observation
                                tx, ty = 0, 0
                                can_pass = False
                                if target_zone == "alliance": tx = 50; ty=150; 
                                else: tx = 320; ty=150; can_pass = True
                                
                                w_obs = get_observation(
                                    robot, self.field, self.pieces, self.sim_config, 
                                    self.game_time, 20.0, 
                                    can_score=True, can_pass=can_pass, target_x=tx, target_y=ty
                                )
                                act, _ = worker_model.predict(w_obs, deterministic=True)
                                robot_action = act
                        else:
                            # NAVIGATOR MODE
                            tx, ty = self.navigator.get_target_cluster(robot, target_zone, target_sector, self.pieces, self.robots)
                            vx, vy, rot = self.navigator.get_action(robot, tx, ty)
                            robot_action[0] = vx
                            robot_action[1] = vy
                            robot_action[2] = rot
                    
                    ai_inputs = {
                        'x': robot_action[0], 'y': robot_action[1], 'rot': robot_action[2],
                        'shoot_state': robot_action[3] > 0,
                        'pass_state': robot_action[4] > 0,
                        'dump_state': robot_action[5] > 0
                    }
                    self.robot_ais[robot] = ai_inputs
            
            # Super Step (Physics)
            self.game_time += self.dt
            
            # Real-time Visualization Hook
            if hasattr(self, 'visualize') and self.visualize:
                self.render()
                # Timestamp handling logic removed
            
            # Update all robots
            for robot in self.robots:
                # Get inputs we just calculated
                ctrl = self.robot_ais.get(robot, {})
                # Robot physics
                # We tell the robot it CAN score (so it attempts shots), but we filter the result below
                res = robot.update(self.dt, {}, {}, self.field, self.game_time, self.robots, self.pieces, can_score=True, ai_inputs=ctrl)
                if isinstance(res, dict):
                    if res.get('scored'):
                         self.pieces.recycle_fuel(robot, self.sim_config['field'])
                         
                         # Check if the hub is ACTUALLY active
                         if self._get_can_score(robot.alliance):
                             self.total_scored += 2 # Standard score
                             r_score = 2.0 # +2 per goal for Manager
                             total_reward += r_score
                             self.ep_rewards['rew_score'] += r_score

            self.pieces.update(self.robots, self.game_time, self.sim_config)
            
            if self.game_time >= self.match_duration:
                terminated = True
                break
        
        info = {
            'score': self.total_scored,
            'rew_score': self.ep_rewards['rew_score']
        }
        if terminated:
            # Pass full breakdown to Monitor wrapper
            info.update(self.ep_rewards)
            info['episode'] = {'r': self.total_reward, 'l': self.game_time} # Fallback
                
        return self._get_global_obs(), total_reward, terminated, truncated, info

    def _draw_extra_overlays(self):
        if not self.screen: return
        
        if not hasattr(self, 'font') or self.font is None:
            self.font = pygame.font.SysFont("Arial", 18)
            
        font = self.font
        
        # Draw Orders above Robots
        for i, robot in enumerate(self.robots):
            if i >= 3: break
            order = self.robot_orders[i]
            
            # Map Order ID to Text
            txt = ""
            if order == 0: txt = "IDLE"
            elif order == 1: txt = "ALL_TOP"
            elif order == 2: txt = "ALL_BOT"
            elif order == 3: txt = "NEU_TOP"
            elif order == 4: txt = "NEU_BOT"
            
            # Color
            color = (255, 255, 255)
            if order in [1, 2]: color = (255, 100, 100) # Red-ish
            if order in [3, 4]: color = (100, 255, 100) # Green-ish
            
            # Draw Text
            surf = font.render(txt, True, color)
            self.screen.blit(surf, (robot.x * self.field.ppi - 20, robot.y * self.field.ppi - 40))
        
        # Draw Score & Time (Top Center)
        # Determine Stage Name
        stage_name = "TELEOP"
        if self.mini_match:
            if self.game_time < 10: stage_name = "AUTO"
            elif self.game_time < 15: stage_name = "TRANSITION"
            elif self.game_time < 40: stage_name = "STAGE 1"
            elif self.game_time < 65: stage_name = "STAGE 2"
            else: stage_name = "ENDGAME"
        else:
            if self.game_time < 15: stage_name = "AUTO"
            elif self.game_time < 130: stage_name = "TELEOP"
            else: stage_name = "ENDGAME"
            
        # Determine Hub Status
        can_score = self._get_can_score("red")
        hub_status = "ACTIVE" if can_score else "LOCKED"
        hub_color = (0, 255, 0) if can_score else (255, 0, 0)
        
        score_txt = f"Score: {self.total_scored} | Time: {self.match_duration - self.game_time:.1f} | {stage_name} | HUB: {hub_status}"
        s_surf = font.render(score_txt, True, (255, 255, 0))
        
        # Draw Hub Status Indicator (Circle near Red Hub)
        # Assuming Red Hub is at x=0, y=FieldLength/2 or similar. 
        # But text is enough for now. 
        # Actually, let's draw a colored box behind the HUB text? No, simple text color for Hub Status part would be nice but Font.render is one color.
        # Let's just render the HUB part separately with color.
        
        w_pixels = self.sim_config['field']['width_inches'] * self.sim_config['field']['pixels_per_inch']
        l_pixels = self.sim_config['field']['length_inches'] * self.sim_config['field']['pixels_per_inch']
        
        # Draw Main HUD
        self.screen.blit(s_surf, (w_pixels/2 - 200, 10))
        
        # Draw Hub Indicator Circle on the actual field
        # Red Hub is Index 0 presumably?
        if self.field and len(self.field.hubs) > 0:
            hub = self.field.hubs[0]
            hx, hy = hub['x'] * self.field.ppi, hub['y'] * self.field.ppi
            import pygame
            pygame.draw.circle(self.screen, hub_color, (int(hx), int(hy)), 20, 3) # Ring around hub
        
        # Draw Model Info (Bottom Left) if set
        if hasattr(self, 'model_steps'):
            m_txt = f"Model: {getattr(self, 'model_steps', '?')} ({getattr(self, 'model_time', '?')})"
            m_surf = font.render(m_txt, True, (200, 200, 200))
            self.screen.blit(m_surf, (10, l_pixels - 30))
