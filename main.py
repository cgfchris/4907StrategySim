import pygame
import json
import time
import os
import sys
import argparse
import glob
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-latest", action="store_true", help="Test the latest model as Red 1 in 1v1 mode")
    args = parser.parse_args()

    pygame.init()
    
    with open(resource_path('config.json'), 'r') as f:
        config = json.load(f)
    
    ppi = config['field']['pixels_per_inch']
    field_width_in = config['field']['width_inches']
    field_height_in = config['field']['length_inches']
    field_width = int(field_width_in * ppi)
    field_height = int(field_height_in * ppi)
    
    hud_height = 140 
    screen = pygame.display.set_mode((field_width, field_height + hud_height))
    pygame.display.set_caption("4907 Strategy Sim - Custom Robot Battle")
    
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("Arial", 18)
    bold_font = pygame.font.SysFont("Arial", 18, bold=True)
    huge_font = pygame.font.SysFont("Arial", 40, bold=True)
    menu_font = pygame.font.SysFont("Arial", 28, bold=True)
    
    field = Field(config['field'])
    pieces = GamePieceManager(config, ppi)
    
    # Swapped Control Schemes
    # RED: WASD
    red_ctrl = {
        'up': pygame.K_w, 'down': pygame.K_s, 'left': pygame.K_a, 'right': pygame.K_d,
        'rotate_l': pygame.K_q, 'rotate_r': pygame.K_e,
        'shoot_key': pygame.K_v, 'pass_key': pygame.K_b,
        'dump_key': pygame.K_c
    }
    # BLUE: ARROWS
    blue_ctrl = {
        'up': pygame.K_UP, 'down': pygame.K_DOWN, 'left': pygame.K_LEFT, 'right': pygame.K_RIGHT,
        'rotate_l': pygame.K_COMMA, 'rotate_r': pygame.K_PERIOD,
        'shoot_key': pygame.K_SLASH, 'pass_key': pygame.K_RSHIFT,
        'dump_key': pygame.K_m
    }
    
    # Match Mode and UI state
    match_mode = config.get('match_mode', '3v3')
    sim_state = "MENU" # MENU or PLAYING
    
    if args.test_latest:
        match_mode = "1v1"
        sim_state = "PLAYING"
        
        # Find latest/best model
        model_dir = "ml_models"
        # Search recursively for all .zip files
        all_models = glob.glob(os.path.join(model_dir, "**", "*.zip"), recursive=True)
        
        if all_models:
            # Prioritize 'best_model.zip' if it exists in the subfolder of the most recent run
            # First, filter for only 'best_model.zip' files
            best_models = [f for f in all_models if os.path.basename(f) == "best_model.zip"]
            
            if best_models:
                # Use the 'best' model from the most recent run (by modification time of the better file)
                latest_model = max(best_models, key=os.path.getmtime)
                print(f"Testing the BEST discovered model: {latest_model}")
            else:
                # Fallback to the latest top-level checkpoint
                latest_model = max(all_models, key=os.path.getmtime)
                print(f"Testing the latest available model: {latest_model}")
                
            # Inject into config temp override
            config['red_alliance'][0]['model_path'] = latest_model
            config['red_alliance'][0]['is_ai'] = True
        else:
            print("No models found in ml_models/ to test.")
            sim_state = "MENU"
    
    # Initialize robots (will be populated on Start)
    robots = []
    robot_ais = {}
    
    scores = {"red": 0, "blue": 0}
    penalty_scores = {"red": 0, "blue": 0}
    game_time = 0
    auto_winner = None
    stage_alliances = ["red", "blue", "red", "blue"] # Default
    
    def init_match():
        nonlocal robots, robot_ais, scores, penalty_scores, game_time, auto_winner, stage_alliances
        robots = []
        robot_ais = {}
        scores = {"red": 0, "blue": 0}
        penalty_scores = {"red": 0, "blue": 0}
        game_time = 0
        auto_winner = None
        stage_alliances = ["red", "blue", "red", "blue"]
        
        red_all = config['red_alliance'] if match_mode == "3v3" else [config['red_alliance'][0]]
        blue_all = config['blue_alliance'] if match_mode == "3v3" else [config['blue_alliance'][0]]
        
        # Red Alliance
        for i, r_cfg in enumerate(red_all):
            spacing = field_height_in / (len(red_all) + 1)
            y_pos = spacing * (i + 1)
            robot = Robot(100, y_pos, r_cfg, "red")
            robot.holding = min(8, robot.capacity)
            robots.append(robot)
            if r_cfg.get('is_ai'):
                robot_ais[robot] = RobotAI("red", r_cfg.get('drivetrain') == "tank", r_cfg.get('model_path'))
                
        # Blue Alliance
        for i, b_cfg in enumerate(blue_all):
            spacing = field_height_in / (len(blue_all) + 1)
            y_pos = spacing * (i + 1)
            robot = Robot(field_width_in - 100, y_pos, b_cfg, "blue")
            robot.holding = min(8, robot.capacity)
            robots.append(robot)
            if b_cfg.get('is_ai'):
                robot_ais[robot] = RobotAI("blue", b_cfg.get('drivetrain') == "tank", b_cfg.get('model_path'))
        
        # Reset Game Pieces
        pieces.reset(config)
    
    # Game State
    scores = {"red": 0, "blue": 0}
    game_time = 0
    paused = False
    last_abs_time = time.time()
    
    # Match Logic State
    auto_winner = None
    stage_alliances = ["red", "blue", "red", "blue"] # Default
    tuning_targets = ["bounciness", "friction"]
    target_idx = 0
    
    if sim_state == "PLAYING":
        init_match()

    running = True
    while running:
        current_abs_time = time.time()
        dt = current_abs_time - last_abs_time
        last_abs_time = current_abs_time
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            if sim_state == "MENU":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    mx, my = event.pos
                    # Mode Buttons
                    if 150 <= mx <= 250 and 200 <= my <= 250: match_mode = "1v1"
                    if 300 <= mx <= 400 and 200 <= my <= 250: match_mode = "3v3"
                    # Start Button
                    if field_width//2 - 100 <= mx <= field_width//2 + 100 and 350 <= my <= 410:
                        sim_state = "PLAYING"
                        init_match()
            
            elif sim_state == "PLAYING":
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_SPACE:
                        paused = not paused
                    if event.key == pygame.K_7: # Reset to Menu
                        sim_state = "MENU"
                        game_time = 0
                        scores = {"red": 0, "blue": 0}
                
                if event.type == pygame.MOUSEBUTTONDOWN and game_time >= 160:
                    mx, my = event.pos
                    if field_width//2 - 150 <= mx <= field_width//2 + 150 and field_height//2 + 50 + hud_height <= my <= field_height//2 + 110 + hud_height:
                        sim_state = "MENU"
                        game_time = 0
                        scores = {"red": 0, "blue": 0}
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_LEFTBRACKET: target_idx = (target_idx - 1) % len(tuning_targets)
                    if event.key == pygame.K_RIGHTBRACKET: target_idx = (target_idx + 1) % len(tuning_targets)
                    
                    tvar = tuning_targets[target_idx]
                    if event.key == pygame.K_MINUS:
                        setattr(pieces, tvar, max(0.0, getattr(pieces, tvar) - 0.01))
                    if event.key == pygame.K_EQUALS: # Plus key
                        setattr(pieces, tvar, min(1.0, getattr(pieces, tvar) + 0.01))
        
        if sim_state == "PLAYING" and not paused:
            game_time += dt
            
            # Match State Machine
            if 0 <= game_time < 20: 
                active_alliance = "both"
            elif 20 <= game_time < 30: 
                active_alliance = "both"
                if auto_winner is None:
                    if scores["red"] > scores["blue"]: auto_winner = "red"
                    elif scores["blue"] > scores["red"]: auto_winner = "blue"
                    else: auto_winner = "tie"
                    
                    # Update Stage Alliances: Winner goes second (Stage 2 & 4)
                    if auto_winner == "red":
                        stage_alliances = ["blue", "red", "blue", "red"]
                    elif auto_winner == "blue":
                        stage_alliances = ["red", "blue", "red", "blue"]
                    # If tie, stay with default [red, blue, red, blue]
            
            elif 30 <= game_time < 130:
                stage_idx = int((game_time - 30) // 25)
                active_alliance = stage_alliances[stage_idx]
            elif 130 <= game_time < 160: 
                active_alliance = "both"
            else: 
                active_alliance = None
            
            keys = pygame.key.get_pressed()
            
            # Update Robots
            for robot in robots:
                ctrl = red_ctrl if robot.alliance == "red" else blue_ctrl
                can_score = (active_alliance == "both") or (active_alliance == robot.alliance)
                
                ai_inputs = None
                if robot in robot_ais:
                    ai_inputs = robot_ais[robot].update(robot, field, pieces, can_score, robots, game_time, 160, config)
                
                update_res = robot.update(dt, keys, ctrl, field, game_time, robots, pieces, can_score, ai_inputs)
                if isinstance(update_res, dict) and update_res.get('scored'):
                    if can_score:
                        scores[robot.alliance] += 1
                        pieces.recycle_fuel(robot, config['field'])
                
                # Check for manual dump
                if not ai_inputs and keys[ctrl['dump_key']]:
                    if robot.dump(game_time, pieces):
                        pieces.spawn_dump(robot.x, robot.y)
            
            # Update Game Pieces
            pieces.update(robots, game_time, config)
            # Process Penalties (+15 for opponent)
            for foul_alliance, amount in pieces.penalties:
                other = "blue" if foul_alliance == "red" else "red"
                penalty_scores[other] += amount
        
        # --- DRAWING ---
        screen.fill((20, 20, 20))
        
        if sim_state == "MENU":
            # Draw Title
            title_text = huge_font.render("4907 Strategy Sim", True, (255, 255, 255))
            screen.blit(title_text, (field_width//2 - title_text.get_width()//2, 80))
            
            # Match Mode Buttons
            # 1v1
            c1 = (100, 200, 100) if match_mode == "1v1" else (100, 100, 100)
            pygame.draw.rect(screen, c1, (150, 200, 100, 50))
            t1 = menu_font.render("1 v 1", True, (255, 255, 255))
            screen.blit(t1, (200 - t1.get_width()//2, 225 - t1.get_height()//2))
            
            # 3v3
            c3 = (100, 200, 100) if match_mode == "3v3" else (100, 100, 100)
            pygame.draw.rect(screen, c3, (300, 200, 100, 50))
            t3 = menu_font.render("3 v 3", True, (255, 255, 255))
            screen.blit(t3, (350 - t3.get_width()//2, 225 - t3.get_height()//2))
            
            # Start Button
            pygame.draw.rect(screen, (50, 150, 50), (field_width//2 - 100, 350, 200, 60))
            ts = huge_font.render("START", True, (255, 255, 255))
            screen.blit(ts, (field_width//2 - ts.get_width()//2, 380 - ts.get_height()//2))
            
            # Instructions
            instr = font.render("Press 'R' during match to return to menu", True, (200, 200, 200))
            screen.blit(instr, (field_width//2 - instr.get_width()//2, 450))

        else: # PLAYING
            field_surf = pygame.Surface((field_width, field_height))
            field.draw(field_surf, active_alliance)
            pieces.draw(field_surf)
            for robot in robots:
                robot.draw(field_surf, ppi, font)
            screen.blit(field_surf, (0, hud_height))
            
            # HUD remains (only drawn in PLAYING state)
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
        # Scores
        score_x_anchor = 250
        # Red HUD
        red_total = scores['red'] + penalty_scores['red']
        red_main = huge_font.render(f"RED: {red_total}", True, (255, 50, 50))
        red_foul = font.render(f"(+{penalty_scores['red']} Foul)", True, (255, 150, 150))
        screen.blit(red_foul, (score_x_anchor, 10))
        screen.blit(red_main, (score_x_anchor, 30))
        
        # Blue HUD
        blue_total = scores['blue'] + penalty_scores['blue']
        blue_main = huge_font.render(f"BLUE: {blue_total}", True, (50, 150, 255))
        blue_foul = font.render(f"(+{penalty_scores['blue']} Foul)", True, (150, 200, 255))
        screen.blit(blue_foul, (score_x_anchor + 220, 10))
        screen.blit(blue_main, (score_x_anchor + 220, 30))
        
        # Robot Status / Controls (Alliance Summaries)
        red_main = next((r for r in robots if r.alliance == "red"), None)
        blue_main = next((r for r in robots if r.alliance == "blue"), None)
        
        if red_main:
            r_shoot = "ON" if red_main.auto_shoot_enabled else "OFF"
            r_pass = "ON" if red_main.auto_pass_enabled else "OFF"
            team_label = "RED Team (3 Bots)" if match_mode == "3v3" else "RED Robot (1v1)"
            screen.blit(font.render(f"{team_label} S={r_shoot} P={r_pass}", True, (255, 150, 150)), (field_width - 250, 10))
            
        if blue_main:
            b_shoot = "ON" if blue_main.auto_shoot_enabled else "OFF"
            b_pass = "ON" if blue_main.auto_pass_enabled else "OFF"
            team_label = "BLUE Team (3 Bots)" if match_mode == "3v3" else "BLUE Robot (1v1)"
            screen.blit(font.render(f"{team_label} S={b_shoot} P={b_pass}", True, (150, 150, 255)), (field_width - 250, 35))
        
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

        # End of Match Button
        if sim_state == "PLAYING" and game_time >= 160:
            btn_rect = (field_width//2 - 150, field_height//2 + 50 + hud_height, 300, 60)
            pygame.draw.rect(screen, (50, 50, 150), btn_rect, border_radius=10)
            pygame.draw.rect(screen, (200, 200, 200), btn_rect, 2, border_radius=10)
            btn_text = bold_font.render("RETURN TO MENU", True, (255, 255, 255))
            screen.blit(btn_text, (field_width//2 - btn_text.get_width()//2, field_height//2 + 80 + hud_height - btn_text.get_height()//2))

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()

if __name__ == "__main__":
    main()
