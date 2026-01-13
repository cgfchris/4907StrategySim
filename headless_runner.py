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

def run_match(config, match_id, verbose=False):
    ppi = config['field']['pixels_per_inch']
    field_width_in = config['field']['width_inches']
    field_height_in = config['field']['length_inches']
    
    field = Field(config['field'])
    pieces = GamePieceManager(config, ppi)
    
    # Initialize robots (using same positions as main.py)
    red_robot = Robot(100, field_height_in/2 - 50, config['red_robot'], "red")
    blue_robot = Robot(field_width_in - 100, field_height_in/2 + 50, config['blue_robot'], "blue")
    robots = [red_robot, blue_robot]
    
    # Initialize AIs
    robot_ais = {}
    if config['red_robot'].get('is_ai'):
        robot_ais[red_robot] = RobotAI("red", config['red_robot']['drivetrain'] == "tank")
    if config['blue_robot'].get('is_ai'):
        robot_ais[blue_robot] = RobotAI("blue", config['blue_robot']['drivetrain'] == "tank")
        
    scores = {"red": 0, "blue": 0}
    game_time = 0
    dt = 1/60.0
    match_duration = 160
    
    keys = [False] * 512
    dummy_ctrl = {'up': 0, 'down': 0, 'left': 0, 'right': 0, 'rotate_l': 0, 'rotate_r': 0, 'shoot_key': 0, 'pass_key': 0}
    
    last_phase = ""
    start_real = time.perf_counter()
    
    while game_time < match_duration:
        # Match Phases
        active_alliance = "both"
        if 0 <= game_time < 20: phase = "AUTO"
        elif 20 <= game_time < 30: phase = "TRANSITION"
        elif 30 <= game_time < 130:
            stage = int((game_time - 30) // 25)
            phase = f"TELEOP STAGE {stage + 1}"
            active_alliance = "red" if stage % 2 == 0 else "blue"
        elif 130 <= game_time < 160: phase = "ENDGAME"
        else: phase = "FINISHED"

        if verbose and phase != last_phase:
            print(f"  [{int(game_time)}s] Phase: {phase} | Score: R:{scores['red']} B:{scores['blue']}")
            last_phase = phase

        for robot in robots:
            can_score = (active_alliance == "both") or (active_alliance == robot.alliance)
            ai_inputs = robot_ais[robot].update(robot, field, pieces, can_score) if robot in robot_ais else None
            
            if robot.update(dt, keys, dummy_ctrl, field, game_time, robots, pieces, can_score, ai_inputs):
                if can_score:
                    scores[robot.alliance] += 1
                    pieces.recycle_fuel(robot, config['field'])
        
        pieces.update(robots, game_time, config['field'])
        game_time += dt
        
    end_real = time.perf_counter()
    duration = end_real - start_real
    
    print(f"Match {match_id:2d}: RED {scores['red']:3d} - BLUE {scores['blue']:3d} ({duration:.2f}s)")
    return scores, duration

def main():
    parser = argparse.ArgumentParser(description="FRC Strategy Simulator - Headless Batch Runner")
    parser.add_argument("--runs", type=int, default=1, help="Number of match simulations to run")
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
        score, dur = run_match(config, i + 1, args.verbose)
        all_results.append(score)
        
    total_end = time.perf_counter()
    total_dur = total_end - total_start
    
    # Calculate Stats
    red_scores = [r['red'] for r in all_results]
    blue_scores = [r['blue'] for r in all_results]
    red_wins = sum(1 for r in all_results if r['red'] > r['blue'])
    blue_wins = sum(1 for r in all_results if r['blue'] > r['red'])
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
    print(f"RED Score:  Avg: {sum(red_scores)/args.runs:.1f} | Max: {max(red_scores)} | Min: {min(red_scores)}")
    print(f"BLUE Score: Avg: {sum(blue_scores)/args.runs:.1f} | Max: {max(blue_scores)} | Min: {min(blue_scores)}")
    print("=" * 40)

    pygame.quit()

if __name__ == "__main__":
    main()
