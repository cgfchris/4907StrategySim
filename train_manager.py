import os

# Optimize for Parallel Training: Force Single-Threaded per Process
# This prevents 24 processes x 8 threads from choking the CPU
os.environ["OMP_NUM_THREADS"] = "1" 

import argparse
import json
from stable_baselines3 import PPO
from stable_baselines3.common.env_util import make_vec_env
from stable_baselines3.common.vec_env import SubprocVecEnv, VecMonitor
from gym_env_manager import ManagerFrcEnv

def train():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suffix", type=str, default="v1", help="Run suffix")
    parser.add_argument("--timesteps", type=int, default=100000, help="Total timesteps (Manager Steps)")
    parser.add_argument("--resume", type=str, nargs='?', const='auto', help="Resume training from model or auto-detect")
    args = parser.parse_args()
    
    log_dir = "ml_logs"
    model_dir = "ml_models"
    resume_path = None
    
    # Auto-Resume Logic
    if args.resume == 'auto':
        import glob
        # Look for existing Manager runs
        candidates = glob.glob(os.path.join(model_dir, "PPO_Manager_*"))
        if candidates:
             candidates.sort(key=lambda x: os.path.getmtime(x), reverse=True)
             args.resume = candidates[0]
             print(f"Auto-resuming latest run: {args.resume}")
             parts = os.path.basename(args.resume).split('_')
             if len(parts) >= 3:
                 args.suffix = "_".join(parts[2:])
                 
    if args.resume and args.resume != 'auto':
        if os.path.isdir(args.resume):
             opts = [
                 os.path.join(args.resume, "best_model", "best_model.zip"), 
                 os.path.join(args.resume, "best_model", "model.zip"),
                 os.path.join(args.resume, "final_model.zip")
             ]
             for o in opts:
                 if os.path.exists(o): 
                     resume_path = o
                     break
        elif os.path.exists(args.resume):
             resume_path = args.resume
    
    run_id = f"PPO_Manager_{args.suffix}"
    
    run_model_dir = os.path.join(model_dir, run_id)
    os.makedirs(log_dir, exist_ok=True)
    os.makedirs(run_model_dir, exist_ok=True)
    
    # Load config
    with open("ml_config.json", "r") as f:
        config = json.load(f)
        
    train_cfg = config.get('manager_training_params', config.get('training_params')) # Fallback
    n_envs = train_cfg.get('n_envs', 28)
    
    print(f"Initializing Manager Environment with {n_envs} parallel processes...")
    
    # Vectorized Environment (Simultaneous matches)
    # Using SubprocVecEnv to utilize all cores
    env = make_vec_env(
        ManagerFrcEnv, 
        n_envs=n_envs, 
        seed=42, 
        vec_env_cls=SubprocVecEnv
    )
    env = VecMonitor(env)
    
    # Network Architecture
    net_arch = train_cfg.get('net_arch', [256, 256])
    
    if resume_path:
        print(f"Resuming Training from: {resume_path}")
        # Need to re-attach env and ensure hyperparameters (lr, ent_coef) are updated if config changed
        model = PPO.load(
            resume_path, 
            env=env, 
            tensorboard_log=log_dir,
            learning_rate=train_cfg.get('learning_rate', 0.0003), # Use .get for safety
            ent_coef=train_cfg.get('ent_coef', 0.01), # Use .get for safety
            n_steps=train_cfg.get('n_steps', 320), # Use .get for safety
            batch_size=train_cfg.get('batch_size', 64), # Use .get for safety
            gamma=train_cfg.get('gamma', 0.99) # Use .get for safety
        )
    else:
        print(f"Starting NEW Training: {run_id}")
        policy_kwargs = dict(net_arch=net_arch)
        
        model = PPO(
            "MlpPolicy", 
            env, 
            verbose=1,
            tensorboard_log=log_dir,
            policy_kwargs=policy_kwargs,
            learning_rate=train_cfg.get('learning_rate', 0.0003),
            n_steps=train_cfg.get('n_steps', 320),
            batch_size=train_cfg.get('batch_size', 64),
            ent_coef=train_cfg.get('ent_coef', 0.01),
            gamma=train_cfg.get('gamma', 0.99)
        )    
    
    total_timesteps = args.timesteps if args.timesteps != 100000 else train_cfg.get('total_timesteps', 1000000)
    
    from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
    
    # Checkpoint every 50k steps (Total)
    checkpoint_freq = max(1000, 50000 // n_envs)
    checkpoint_callback = CheckpointCallback(
        save_freq=checkpoint_freq,
        save_path=run_model_dir,
        name_prefix=f"manager_checkpoint"
    )
    
    # Evaluation (Optional, but good for tracking 'true' score without exploration noise)
    # Use config eval_freq (steps per env)
    eval_freq = train_cfg.get('eval_freq', 20000)
    eval_env = ManagerFrcEnv() # Single instance for eval
    # Wrap in Monitor for stats
    from stable_baselines3.common.monitor import Monitor
    eval_env = Monitor(eval_env)
    
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=os.path.join(run_model_dir, "best_model"),
        log_path=log_dir,
        eval_freq=max(eval_freq // n_envs, 1), # SB3 counts calls, which happen 1 per n_envs steps? No.
        # SB3 EvalCallback: "Check every n_steps calls to the callback".
        # Callback is called every GLOBAL step? No, every rollout step?
        # Standard: eval_freq is "number of steps per env".
        deterministic=True,
        n_eval_episodes=train_cfg.get('eval_episodes', 5)
    )
    
    print(f"Starting Training for {total_timesteps} steps...")
    model.learn(total_timesteps=total_timesteps, tb_log_name=run_id, callback=[checkpoint_callback, eval_callback])
    
    model.save(f"{run_model_dir}/final_model")
    print(f"Training Complete. Model saved to {run_model_dir}")

if __name__ == "__main__":
    train()
