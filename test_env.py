import numpy as np
from gym_env import FrcEnv

def test_env():
    print("Initializing FRC Environment...")
    try:
        env = FrcEnv(render_mode=None)
        obs, info = env.reset()
        print(f"Reset successful. Observation shape: {obs.shape}")
        
        # Take 10 steps with random actions
        print("Taking 10 random steps...")
        for i in range(10):
            action = env.action_space.sample()
            obs, reward, terminated, truncated, info = env.step(action)
            print(f"Step {i+1}: Reward = {reward:.2f}")
            if terminated or truncated:
                print("Environment finished early.")
                break
        
        print("Test completed successfully!")
        env.close()
    except Exception as e:
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_env()
