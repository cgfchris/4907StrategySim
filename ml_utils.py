import numpy as np

def get_observation(robot, field, pieces, sim_config, game_time, match_duration):
    is_red = robot.alliance == "red"
    
    # 1. Self params (Normalized)
    obs_self = [
        robot.x / sim_config['field']['width_inches'],
        robot.y / sim_config['field']['length_inches'],
        (robot.angle % 360) / 360.0,
        robot.holding / robot.capacity,
        1.0 if is_red else 0.0
    ]

    # 2. Closest Fuel
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
            obs_fuel.extend([
                dx / 200.0, 
                dy / 200.0,
                min(1.0, fuel.bounces / 3.0),
                1.0 if fuel.immune_timer > 0 else 0.0
            ])
        else:
            obs_fuel.extend([0, 0, 0, 0])

    # 3. Grid View (4x4) - Zone Aware
    # X Boundaries: [Red Side, Neutral Left, Neutral Right, Blue Side]
    width = sim_config['field']['width_inches']
    height = sim_config['field']['length_inches']
    divider_x = sim_config['field']['divider_x']
    
    x_bins = [0, divider_x, width/2, width - divider_x, width]
    y_bins = np.linspace(0, height, 5) # 4 rows
    
    grid_counts = np.zeros((4, 4))
    for fuel in pieces.fuels:
        if not fuel.collected:
            # Find bins
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
                
    obs_grid = (grid_counts.flatten() / 20.0).tolist()

    # 4. Game State
    obs_state = [
        game_time / match_duration,
        1.0 
    ]

    # 5. Strategic Points
    own_hub = field.hubs[0] if is_red else field.hubs[1]
    enemy_hub = field.hubs[1] if is_red else field.hubs[0]
    obs_strat = [
        (own_hub['x'] - robot.x) / 200.0,
        (own_hub['y'] - robot.y) / 200.0,
        (enemy_hub['x'] - robot.x) / 200.0,
        (enemy_hub['y'] - robot.y) / 200.0
    ]

    return np.array(obs_self + obs_fuel + obs_grid + obs_state + obs_strat, dtype=np.float32)
