
import time
import numpy as np
from gym_env_manager import ManagerFrcEnv

def run_benchmark(interval, steps=50):
    print(f"\n--- Benchmarking Worker Interval: {interval} (Update every {interval} frames) ---")
    env = ManagerFrcEnv()
    env.set_worker_interval(interval) 
    env.reset()
    
    # Force robots to have assignments so logic actually runs
    # Order 1 = All_Top (Janitor)
    action = [1, 1, 1] 
    
    start_time = time.time()
    for i in range(steps):
        env.step(action)
    end_time = time.time()
    
    duration = end_time - start_time
    fps = (steps * 60) / duration # Physics frames per second
    steps_per_sec = steps / duration
    
    print(f"Time for {steps} Manager Steps (simulating {steps*60} frames): {duration:.4f}s")
    print(f"Manager Steps/Sec: {steps_per_sec:.2f}")
    print(f"Physics FPS: {fps:.2f}")
    
    expected_train_time = (1_000_000 / steps_per_sec) / 3600.0 / 8 # Assuming 8 cores
    print(f"Est. Training Time (1M Steps, 8 Cores): {expected_train_time:.2f} Hours")
    
    env.close()

if __name__ == "__main__":
    # Test 1: Baseline (Every Frame)
    run_benchmark(1)
    
    # Test 2: Optimized (Every 6 Frames)
    run_benchmark(6)
