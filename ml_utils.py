import numpy as np
import math

def get_observation(robot, field, pieces, sim_config, game_time, match_duration, can_score=False, can_pass=False):
    is_red = robot.alliance == "red"
    width = sim_config['field']['width_inches']
    height = sim_config['field']['length_inches']
    
    # 1. Self params (Normalized) - 6 features (Indices 0-5)
    rad = math.radians(robot.angle)
    obs_self = [
        robot.x / width,
        robot.y / height,
        math.sin(rad),
        math.cos(rad),
        robot.holding / robot.capacity,
        1.0 if is_red else 0.0
    ]

    # 2. Closest Fuel - 20 features (Indices 6-25)
    fuels = []
    for fuel in pieces.fuels:
        if not fuel.collected:
            dx = fuel.x - robot.x
            dy = fuel.y - robot.y
            dist_sq = dx**2 + dy**2
            fuels.append((dist_sq, dx, dy, fuel))
    
    fuels.sort(key=lambda x: x[0])
    obs_fuel = []
    for i in range(5):
        if i < len(fuels):
            _, dx, dy, fuel = fuels[i]
            val_x = dx / width
            val_y = dy / height
            obs_fuel.extend([
                math.copysign(math.sqrt(abs(val_x)), val_x),
                math.copysign(math.sqrt(abs(val_y)), val_y),
                min(1.0, fuel.bounces / 3.0),
                1.0 if fuel.immune_timer > 0 else 0.0
            ])
        else:
            obs_fuel.extend([0, 0, 0, 0])

    # 3. Grid View (4x4) - 16 features (Indices 26-41)
    divider_x = sim_config['field']['divider_x']
    x_bins = [0, divider_x, width/2, width - divider_x, width]
    y_bins = np.linspace(0, height, 5) 
    
    grid_counts = np.zeros((4, 4))
    for fuel in pieces.fuels:
        if not fuel.collected:
            gx = -1
            for i in range(4):
                if x_bins[i] <= fuel.x < x_bins[i+1]:
                    gx = i
                    break
            
            gy = -1
            for i in range(4):
                if y_bins[i] <= fuel.y < y_bins[i+1]:
                    gy = i
                    break
            
            if gx != -1 and gy != -1:
                grid_counts[gx, gy] += 1
                
    obs_grid = (grid_counts.flatten() / 10.0).tolist()

    # 4. Game State - 2 features (Indices 42-43)
    # We MUST keep this at index 42/43 to avoid shifting the Hub coordinates (44-47).
    # Replacement: Index 43 (formerly constant 1.0) now holds can_score.
    obs_state = [
        game_time / match_duration,
        1.0 if can_score else 0.0
    ]

    # 5. Strategic Points - 4 features (Indices 44-47)
    # We MUST keep these at indices 44-47.
    own_hub = field.hubs[0] if is_red else field.hubs[1]
    enemy_hub = field.hubs[1] if is_red else field.hubs[0]
    # Replacement: Index 47 (formerly enemy_hub_y) now holds can_pass.
    # Hub Y is identical for both hubs, so Index 45 (own_hub_y) still provides the Y coordinate.
    obs_strat = [
        (own_hub['x'] - robot.x) / width,
        (own_hub['y'] - robot.y) / height,
        (enemy_hub['x'] - robot.x) / width,
        1.0 if can_pass else 0.0 # Replaces enemy_hub_y which was redundant
    ]

    return np.array(obs_self + obs_fuel + obs_grid + obs_state + obs_strat, dtype=np.float32)
