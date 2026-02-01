from gym_env_manager import ManagerFrcEnv
import traceback
import numpy as np
import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

try:
    print("Initializing Env...")
    env = ManagerFrcEnv()
    print("Resetting Env...")
    obs, info = env.reset()
    
    # Force action: Robot 0 -> Order 3 (Neutral Top)
    # This should trigger Navigator if robot is not there.
    action = np.array([3, 0, 0])
    
    print("Stepping 60 frames...")
    for i in range(60):
        obs, reward, terminated, truncated, info = env.step(action)
        
    print("Done.")
    
except Exception:
    traceback.print_exc()

    
