
import math

# Mocking the physics from the files
def simulate_pass(start_x, target_x, friction, dt=1/60.0):
    dx = target_x - start_x
    dist = abs(dx)
    
    # Logic from robot.py
    needed_mag = (dist * (1.0 - friction)) / dt
    
    vel_x = (dx / dist) * needed_mag
    
    # Simulation
    x = start_x
    trajectory = []
    
    print(f"Start: {start_x}, Target: {target_x}, Friction: {friction}")
    print(f"Calculated Mag: {needed_mag}, Vel_X: {vel_x}")
    
    steps = 0
    while abs(vel_x) > 0.1 and steps < 300: # 5 seconds cap
        old_x = x
        
        # Logic from game_piece.py update
        x += vel_x * dt
        vel_x *= friction
        
        steps += 1
        if steps % 10 == 0:
            trajectory.append(x)
            
    print(f"Final X: {x:.2f} after {steps} steps.")
    if abs(x - target_x) < 5:
        print("SUCCESS: Landed near target.")
    else:
        print(f"FAILURE: Missed by {x - target_x:.2f}")

# Test with common friction values (usually 0.90 to 0.99 for games)
# Assuming 'config.json' has something like 0.98 or 0.95
print("--- Simulating Friction 0.98 ---")
simulate_pass(300, 60, 0.98)

print("\n--- Simulating Friction 0.95 ---")
simulate_pass(300, 60, 0.95)

print("\n--- Simulating Friction 0.90 ---")
simulate_pass(300, 60, 0.90)
