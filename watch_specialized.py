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
    
    model = None
    if args.model and os.path.exists(args.model):
        print(f"Loading model: {args.model}")
        model = PPO.load(args.model)

    obs, info = env.reset()
    running = True
    clock = pygame.time.Clock()

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
        # env.render() # No longer needed here, env.step() handles it smoothly

        if terminated or truncated:
            obs, info = env.reset()

    env.close()

if __name__ == "__main__":
    watch()
