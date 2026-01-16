import numpy as np
import math

def get_observation(robot, field, pieces, sim_config, game_time, match_duration, can_score=False, can_pass=False, target_x=None, target_y=None):
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

    # Rotation for Robot-Oriented Vision (aligning intake with local X-axis)
    # math.radians(robot.angle) is in degrees, likely compass-style
    # We want local coordinates: +X is Front (Intake), +Y is Left
    c, s = math.cos(-rad), math.sin(-rad)

    # 2. Closest Fuel - 20 features (Indices 6-25)
    fuels = []
    for fuel in pieces.fuels:
        if not fuel.collected:
            dx_field = fuel.x - robot.x
            dy_field = fuel.y - robot.y
            dist_sq = dx_field**2 + dy_field**2
            # Rotate into robot frame
            dx_rel = dx_field * c - dy_field * s
            dy_rel = dx_field * s + dy_field * c
            fuels.append((dist_sq, dx_rel, dy_rel, fuel))
    
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
    # (Grid stays field-oriented as it's a 'minimap' feature)
    divider_x = sim_config['field']['divider_x']
    x_bins = [0, divider_x, width/2, width - divider_x, width]
    y_bins = np.linspace(0, height, 5) 
    
    grid_counts = np.zeros((4, 4))
    for fuel in pieces.fuels:
        if not fuel.collected:
            gx, gy = -1, -1
            for i in range(4):
                if x_bins[i] <= fuel.x < x_bins[i+1]:
                    gx = i
                    break
            for i in range(4):
                if y_bins[i] <= fuel.y < y_bins[i+1]:
                    gy = i
                    break
            if gx != -1 and gy != -1:
                grid_counts[gx, gy] += 1
                
    obs_grid = (grid_counts.flatten() / 10.0).tolist()

    # 4. Game State - 2 features (Indices 42-43)
    obs_state = [
        game_time / match_duration,
        1.0 if can_score else 0.0
    ]

    # 5. Strategic Points - 4 features (Indices 44-47)
    own_hub = field.hubs[0] if is_red else field.hubs[1]
    enemy_hub = field.hubs[1] if is_red else field.hubs[0]
    
    # Defaults in Field Frame (Relative to Robot Position)
    vals = [
        (own_hub['x'] - robot.x) / width,
        (own_hub['y'] - robot.y) / height,
        (enemy_hub['x'] - robot.x) / width,
        1.0 if can_pass else 0.0 # Index 47!
    ]
    
    if target_x is not None and target_y is not None:
        # Specialized Mode: Overwrite Indices 44-45 with Robot-Oriented Target Vector
        # Index 46 stays Enemy Hub X (unused in lab)
        # Index 47 stays can_pass (CRITICAL FIX)
        tdx_field = target_x - robot.x
        tdy_field = target_y - robot.y
        tdx_rel = tdx_field * c - tdy_field * s
        tdy_rel = tdx_field * s + tdy_field * c
        vals[0] = tdx_rel / width
        vals[1] = tdy_rel / height

    return np.array(obs_self + obs_fuel + obs_grid + obs_state + vals, dtype=np.float32)
