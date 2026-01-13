import pygame
import json
import time
import os
import sys
from robot import Robot
from field import Field
from game_piece import GamePieceManager
from ai import RobotAI

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def main():
    pygame.init()
    
    with open(resource_path('config.json'), 'r') as f:
        config = json.load(f)
    
    ppi = config['field']['pixels_per_inch']
    field_width = int(config['field']['width_inches'] * ppi)
    field_height = int(config['field']['length_inches'] * ppi)
    
    hud_height = 140 
    screen = pygame.display.set_mode((field_width, field_height + hud_height))
    pygame.display.set_caption("4907 Strategy Sim - Custom Robot Battle")
    
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 18)
    bold_font = pygame.font.SysFont("Arial", 18, bold=True)
    huge_font = pygame.font.SysFont("Arial", 40, bold=True)
    
    field = Field(config['field'])
    pieces = GamePieceManager(config, ppi)
    
    # Swapped Control Schemes
    # RED: WASD
    red_ctrl = {
        'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d,
        'rotate_l': pygame.K_q, 'rotate_r': pygame.K_e,
        'shoot_key': pygame.K_v, 'pass_key': pygame.K_b
    }
    # BLUE: ARROWS
    blue_ctrl = {
        'up': pygame.K_UP, 'down': pygame.K_DOWN, 'left': pygame.K_LEFT, 'right': pygame.K_RIGHT,
        'rotate_l': pygame.K_COMMA, 'rotate_r': pygame.K_PERIOD,
        'shoot_key': pygame.K_SLASH, 'pass_key': pygame.K_RSHIFT
    }
    
    # Initialize separate robot configs
    red_robot = Robot(100, field_height/(2*ppi) - 50, config['red_robot'], "red")
    blue_robot = Robot(config['field']['width_inches'] - 100, field_height/(2*ppi) + 50, config['blue_robot'], "blue")
    robots = [red_robot, blue_robot]
    
    # AI Initialization
    robot_ais = {}
    if config['red_robot'].get('is_ai'):
        robot_ais[red_robot] = RobotAI("red", config['red_robot']['drivetrain'] == "tank")
    if config['blue_robot'].get('is_ai'):
        robot_ais[blue_robot] = RobotAI("blue", config['blue_robot']['drivetrain'] == "tank")
    
    # Game State
    scores = {"red": 0, "blue": 0}
    game_time = 0
    paused = False
    last_abs_time = time.time()
    
    # Tuning State
    tuning_targets = ["bounciness", "friction"]
    target_idx = 0
    
    running = True
    while running:
        current_abs_time = time.time()
        dt = current_abs_time - last_abs_time
        last_abs_time = current_abs_time
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r: return main()
                if event.key == pygame.K_t: paused = not paused
                
                # Independent Toggles
                if event.key == red_ctrl['shoot_key']: red_robot.auto_shoot_enabled = not red_robot.auto_shoot_enabled
                if event.key == red_ctrl['pass_key']: red_robot.auto_pass_enabled = not red_robot.auto_pass_enabled
                if event.key == blue_ctrl['shoot_key']: blue_robot.auto_shoot_enabled = not blue_robot.auto_shoot_enabled
                if event.key == blue_ctrl['pass_key']: blue_robot.auto_pass_enabled = not blue_robot.auto_pass_enabled
                
                # Tuning Controls
                if event.key == pygame.K_LEFTBRACKET: target_idx = (target_idx - 1) % len(tuning_targets)
                if event.key == pygame.K_RIGHTBRACKET: target_idx = (target_idx + 1) % len(tuning_targets)
                
                tvar = tuning_targets[target_idx]
                if event.key == pygame.K_MINUS:
                    setattr(pieces, tvar, max(0.0, getattr(pieces, tvar) - 0.01))
                if event.key == pygame.K_EQUALS: # Plus key
                    setattr(pieces, tvar, min(1.0, getattr(pieces, tvar) + 0.01))
        
        if not paused:
            game_time += dt
            
            # Match State Machine
            active_alliance = "both"
            if 0 <= game_time < 20: active_alliance = "both" # Auto
            elif 20 <= game_time < 30: active_alliance = "both" # Transition
            elif 30 <= game_time < 130:
                stage = int((game_time - 30) // 25)
                active_alliance = "red" if stage % 2 == 0 else "blue"
            elif 130 <= game_time < 160: active_alliance = "both" # Endgame
            else: active_alliance = None # Match Over
            
            keys = pygame.key.get_pressed()
            
            # Update Robots
            for robot in robots:
                ctrl = red_ctrl if robot.alliance == "red" else blue_ctrl
                can_score = (active_alliance == "both") or (active_alliance == robot.alliance)
                
                ai_inputs = None
                if robot in robot_ais:
                    ai_inputs = robot_ais[robot].update(robot, field, pieces, can_score)
                
                if robot.update(dt, keys, ctrl, field, game_time, robots, pieces, can_score, ai_inputs):
                    if can_score:
                        scores[robot.alliance] += 1
                        pieces.recycle_fuel(robot, config['field'])
                
            pieces.update(robots, game_time, config['field'])
        
        # --- DRAWING ---
        screen.fill((20, 20, 20))
        field_surf = pygame.Surface((field_width, field_height))
        field.draw(field_surf, active_alliance)
        pieces.draw(field_surf)
        for robot in robots:
            robot.draw(field_surf, ppi, font)
        screen.blit(field_surf, (0, hud_height))
        
        # --- HUD ---
        hud_bg = pygame.Rect(0, 0, field_width, hud_height)
        pygame.draw.rect(screen, (40, 40, 40), hud_bg)
        pygame.draw.line(screen, (100, 100, 100), (0, hud_height), (field_width, hud_height), 2)
        
        # Timer and Phase
        screen.blit(font.render(f"TIME: {int(game_time)}s", True, (255, 255, 255)), (20, 10))
        phase_name = "MATCH OVER"
        phase_color = (200, 200, 200)
        if 0 <= game_time < 20: phase_name, phase_color = "AUTO", (255, 255, 0)
        elif 20 <= game_time < 30: phase_name, phase_color = "TRANSITION", (255, 165, 0)
        elif 30 <= game_time < 130: phase_name, phase_color = f"TELEOP STAGE {int((game_time-30)//25)+1}", (0, 255, 0)
        elif 130 <= game_time < 160: phase_name, phase_color = "ENDGAME", (255, 0, 255)
        
        phase_surf = bold_font.render(f"PHASE: {phase_name}", True, phase_color)
        screen.blit(phase_surf, (20, 35))

        # Scores (Positioned to the left to avoid status overlap)
        score_x_anchor = 300
        red_score_surf = huge_font.render(f"RED: {scores['red']}", True, (255, 100, 100))
        blue_score_surf = huge_font.render(f"BLUE: {scores['blue']}", True, (100, 100, 255))
        screen.blit(red_score_surf, (score_x_anchor, 20))
        screen.blit(blue_score_surf, (score_x_anchor + 200, 20))
        
        # Robot Status / Controls
        # Red
        r_shoot = "ON" if red_robot.auto_shoot_enabled else "OFF"
        r_pass = "ON" if red_robot.auto_pass_enabled else "OFF"
        screen.blit(font.render(f"RED: {red_robot.drivetrain.upper()} S={r_shoot}(V) P={r_pass}(B)", True, (255, 150, 150)), (field_width - 320, 10))
        # Blue
        b_shoot = "ON" if blue_robot.auto_shoot_enabled else "OFF"
        b_pass = "ON" if blue_robot.auto_pass_enabled else "OFF"
        screen.blit(font.render(f"BLUE: {blue_robot.drivetrain.upper()} S={b_shoot}(/) P={b_pass}(SHFT)", True, (150, 150, 255)), (field_width - 320, 35))
        
        # Tuning Panel
        pygame.draw.rect(screen, (30, 30, 30), (20, 65, 450, 25), border_radius=5)
        tuning_text = "TUNING: "
        for i, target in enumerate(tuning_targets):
            val = getattr(pieces, target)
            prefix = " > " if i == target_idx else "   "
            tuning_text += f"{prefix}{target}: {val:.2f}"
        tuning_text += "  ( [ ] - + keys )"
        screen.blit(font.render(tuning_text, True, (200, 200, 200)), (30, 68))
        
        # Controls (Moved to bottom)
        controls_text = "RED: WASD + Q E V B | BLUE: ARROWS + < > / SHIFT | R: Reset"
        screen.blit(font.render(controls_text, True, (180, 180, 180)), (field_width - 550, 105))
        
        # AI Recovery Status
        is_recovering = False
        for robot in robots:
            if robot in robot_ais and robot_ais[robot].recovery_timer > 0:
                is_recovering = True
                break
        if is_recovering:
            screen.blit(bold_font.render("AI RECOVERING...", True, (255, 255, 0)), (20, 105))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
