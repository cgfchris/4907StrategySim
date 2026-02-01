import argparse
import os
import pygame
from gym_env_specialized import SpecializedFrcEnv
from stable_baselines3 import PPO

def watch():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, choices=["janitor", "lobber"], default="janitor", help="Specialized mode to watch")
    parser.add_argument("--model", type=str, help="Path to the model .zip file")
    args = parser.parse_args()

    pygame.init()
    # Initialize environment in human mode
    env = SpecializedFrcEnv(render_mode="human", mode=args.mode)
    
    def load_model():
        if args.model and os.path.exists(args.model):
            try:
                # We need to suppress output or it will spam the console
                return PPO.load(args.model)
            except Exception as e:
                print(f"Error loading model (might be writing): {e}")
                return None
        return None

    model = load_model()
    model_time = ""
    model_steps = ""
    if model: 
        print(f"Loaded initial model: {args.model}")
        import datetime
        mtime = os.path.getmtime(args.model)
        model_time = datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
        model_steps = f"{model.num_timesteps / 1e6:.2f}M"

    obs, info = env.reset()
    running = True
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 22)

    print(f"Watching {args.mode.upper()} mode. Press Esc to quit.")

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                running = False

        if model:
            action, _ = model.predict(obs, deterministic=True)
        else:
            action = env.action_space.sample() # Random movement if no model

        obs, reward, terminated, truncated, info = env.step(action)
        
        # Pass data to env for native rendering (avoids flickering)
        env.model_time = model_time
        env.model_steps = model_steps

        if terminated or truncated:
            obs, info = env.reset()
            # Reload model to catch updates
            new_model = load_model()
            if new_model:
                model = new_model
                import datetime
                mtime = os.path.getmtime(args.model)
                model_time = datetime.datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
                model_steps = f"{model.num_timesteps / 1e6:.2f}M"
                print(f"Reloaded model: {args.model} (Saved: {model_time}, Steps: {model_steps})")

    env.close()

if __name__ == "__main__":
    watch()
