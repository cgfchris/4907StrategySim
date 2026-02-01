
import argparse
import os
import pygame
import time
from gym_env_manager import ManagerFrcEnv
from stable_baselines3 import PPO

def watch():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suffix", type=str, default="v1", help="Suffix of the manager run (e.g. v1)")
    parser.add_argument("--model", type=str, help="Direct path to model zip")
    args = parser.parse_args()

    pygame.init()
    # Initialize environment in human mode
    env = ManagerFrcEnv(render_mode="human")
    
    # Determine Model Path
    model_path = args.model
    if not model_path:
        base_dir = f"ml_models/PPO_Manager_{args.suffix}"
        # We prefer "final_model.zip", then "best_model.zip", then whatever
        opts = [os.path.join(base_dir, "final_model.zip"), os.path.join(base_dir, "best_model.zip")]
        for o in opts:
            if os.path.exists(o):
                model_path = o
                break
        if not model_path and os.path.exists(base_dir):
            # Find any zip
            for f in os.listdir(base_dir):
                if f.endswith(".zip"):
                    model_path = os.path.join(base_dir, f)
                    break 

    def load_model(path):
        if path and os.path.exists(path):
            try:
                return PPO.load(path)
            except Exception as e:
                print(f"Error loading model: {e}")
                return None
        return None

    model = load_model(model_path)
    model_time = ""
    model_steps = ""
    
    if model: 
        print(f"Loaded: {model_path}")
        import datetime
        mtime = os.path.getmtime(model_path)
        model_time = datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
        model_steps = f"{model.num_timesteps / 1e6:.2f}M"

    obs, info = env.reset()
    running = True
    clock = pygame.time.Clock()
    
    # Enable Real-time visualization inside the Physics Loop
    env.visualize = True
    
    print(f"Watching Manager {args.suffix}. Press Esc to quit.")

    # Loop
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False

        if model:
            action, _ = model.predict(obs, deterministic=True)
            # print(f"Manager Action: {action}")
        else:
            action = env.action_space.sample() 

        # Step takes ~1 second of wall time now
        obs, reward, terminated, truncated, info = env.step(action)
        
        # Pass info to env for rendering (for the next frame)
        env.model_time = model_time
        env.model_steps = model_steps
        
        if terminated or truncated:
            obs, info = env.reset()
            # Reload
            new_model = load_model(model_path)
            if new_model:
                model = new_model
                mtime = os.path.getmtime(model_path)
                model_time = datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
                model_steps = f"{model.num_timesteps / 1e6:.2f}M"
                print(f"Reloaded: {model_path} ({model_time})")

    env.close()

if __name__ == "__main__":
    watch()
