import os
import sys
import argparse
import time
import math
import random
import json

# Force Pygame to use dummy driver for headless operation
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
from robot import Robot
from field import Field
from game_piece import GamePieceManager
from ai import RobotAI

def resource_path(relative_path):
    """ Get absolute path to resource """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def run_match(config, match_id, mode="3v3", verbose=False):
    ppi = config['field']['pixels_per_inch']
    field_width_in = config['field']['width_inches']
    field_height_in = config['field']['length_inches']
    
    field = Field(config['field'])
    pieces = GamePieceManager(config, ppi)
    
    # Initialize robots
    robots = []
    robot_ais = {}
    
    red_all = config['red_alliance'] if mode == "3v3" else [config['red_alliance'][0]]
    blue_all = config['blue_alliance'] if mode == "3v3" else [config['blue_alliance'][0]]
    
    # Red Alliance
    for i, r_cfg in enumerate(red_all):
        spacing = field_height_in / (len(red_all) + 1)
        y_pos = spacing * (i + 1)
        robot = Robot(100, y_pos, r_cfg, "red")
        robot.holding = min(8, robot.capacity)
        robots.append(robot)
        if r_cfg.get('is_ai'):
            robot_ais[robot] = RobotAI("red", r_cfg.get('drivetrain') == "tank")
            
    # Blue Alliance
    for i, b_cfg in enumerate(blue_all):
        spacing = field_height_in / (len(blue_all) + 1)
        y_pos = spacing * (i + 1)
        robot = Robot(field_width_in - 100, y_pos, b_cfg, "blue")
        robot.holding = min(8, robot.capacity)
        robots.append(robot)
        if b_cfg.get('is_ai'):
            robot_ais[robot] = RobotAI("blue", b_cfg.get('drivetrain') == "tank")
    
    pieces.spawn_initial(config)
    
    # (AI initialization moved into the robot loops above)
        
    scores = {"red": 0, "blue": 0}
    penalty_scores = {"red": 0, "blue": 0}
    game_time = 0
    dt = 1/60.0
    match_duration = 160
    
    auto_winner = None
    stage_alliances = ["red", "blue", "red", "blue"] # Default
    
    keys = [False] * 512
    dummy_ctrl = {'up': 0, 'down': 0, 'left': 0, 'right': 0, 'rotate_l': 0, 'rotate_r': 0, 'shoot_key': 0, 'pass_key': 0}
    
    last_phase = ""
    start_real = time.perf_counter()
    
    while game_time < match_duration:
        # Match Phases
        active_alliance = "both"
        if 0 <= game_time < 20: 
            phase = "AUTO"
            active_alliance = "both"
        elif 20 <= game_time < 30: 
            phase = "TRANSITION"
            active_alliance = "both"
            if auto_winner is None:
                if scores["red"] > scores["blue"]: auto_winner = "red"
                elif scores["blue"] > scores["red"]: auto_winner = "blue"
                else: auto_winner = "tie"
                
                if auto_winner == "red":
                    stage_alliances = ["blue", "red", "blue", "red"]
                elif auto_winner == "blue":
                    stage_alliances = ["red", "blue", "red", "blue"]
        
        elif 30 <= game_time < 130:
            stage_idx = int((game_time - 30) // 25)
            phase = f"TELEOP STAGE {stage_idx + 1}"
            active_alliance = stage_alliances[stage_idx]
        elif 130 <= game_time < 160: 
            phase = "ENDGAME"
            active_alliance = "both"
        else: phase = "FINISHED"

        if verbose and phase != last_phase:
            print(f"  [{int(game_time)}s] Phase: {phase} | Score: R:{scores['red']} B:{scores['blue']}")
            last_phase = phase

        for robot in robots:
            can_score = (active_alliance == "both") or (active_alliance == robot.alliance)
            
            ai_inputs = None
            if robot in robot_ais:
                if robot.should_update_ai(dt):
                    ai_inputs = robot_ais[robot].update(robot, field, pieces, can_score, robots)
                else:
                    ai_inputs = robot.last_ai_inputs
            
            if robot.update(dt, keys, dummy_ctrl, field, game_time, robots, pieces, can_score, ai_inputs):
                if can_score:
                    scores[robot.alliance] += 1
                    pieces.recycle_fuel(robot, config['field'])
        
        pieces.update(robots, game_time, config)
        
        # Process Penalties (+15 for opponent gained by this alliance)
        for foul_alliance, amount in pieces.penalties:
            other = "blue" if foul_alliance == "red" else "red"
            penalty_scores[other] += amount
        
        game_time += dt
        
    end_real = time.perf_counter()
    duration = end_real - start_real
    
    red_total = scores['red'] + penalty_scores['red']
    blue_total = scores['blue'] + penalty_scores['blue']
    
    print(f"Match {match_id:2d}: RED {red_total:3d} (+{penalty_scores['red']}P) - BLUE {blue_total:3d} (+{penalty_scores['blue']}P) ({duration:.2f}s)")
    return {"scores": scores, "penalties": penalty_scores}, duration

def main():
    parser = argparse.ArgumentParser(description="FRC Strategy Simulator - Headless Batch Runner")
    parser.add_argument("--runs", type=int, default=1, help="Number of match simulations to run")
    parser.add_argument("--mode", type=str, default="3v3", choices=["1v1", "3v3"], help="Match mode (1v1 or 3v3)")
    parser.add_argument("--verbose", action="store_true", help="Print detailed phase transitions for each match")
    args = parser.parse_args()

    pygame.init()
    pygame.display.set_mode((1, 1))

    with open(resource_path('config.json'), 'r') as f:
        config = json.load(f)

    print(f"Starting {args.runs} Batch Simulation Run(s)...")
    print("-" * 40)
    
    all_results = []
    total_start = time.perf_counter()
    
    for i in range(args.runs):
        # Set unique seed for each match to ensure variability if random is used
        random.seed(time.time() + i)
        score, dur = run_match(config, i + 1, args.mode, args.verbose)
        all_results.append(score)
        
    total_end = time.perf_counter()
    total_dur = total_end - total_start
    
    # Calculate Stats
    red_scores = [r['scores']['red'] + r['penalties']['red'] for r in all_results]
    blue_scores = [r['scores']['blue'] + r['penalties']['blue'] for r in all_results]
    red_penalties = [r['penalties']['red'] for r in all_results]
    blue_penalties = [r['penalties']['blue'] for r in all_results]
    
    red_wins = sum(1 for r in all_results if (r['scores']['red'] + r['penalties']['red']) > (r['scores']['blue'] + r['penalties']['blue']))
    blue_wins = sum(1 for r in all_results if (r['scores']['blue'] + r['penalties']['blue']) > (r['scores']['red'] + r['penalties']['red']))
    ties = len(all_results) - red_wins - blue_wins
    
    print("-" * 40)
    print("SUMMARY STATISTICS")
    print(f"Total Matches: {args.runs}")
    print(f"Total Time:    {total_dur:.2f}s ({ (args.runs * 160) / total_dur:.1f}x real-time)")
    print("-" * 20)
    print(f"RED WINS:  {red_wins} ({red_wins/args.runs*100:.1f}%)")
    print(f"BLUE WINS: {blue_wins} ({blue_wins/args.runs*100:.1f}%)")
    if ties > 0: print(f"TIES:      {ties} ({ties/args.runs*100:.1f}%)")
    print("-" * 20)
    print(f"RED Score:  Avg: {sum(red_scores)/args.runs:.1f} (Avg Pen: {sum(red_penalties)/args.runs:.1f}) | Max: {max(red_scores)}")
    print(f"BLUE Score: Avg: {sum(blue_scores)/args.runs:.1f} (Avg Pen: {sum(blue_penalties)/args.runs:.1f}) | Max: {max(blue_scores)}")
    print("=" * 40)

    pygame.quit()

if __name__ == "__main__":
    main()
