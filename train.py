import os
import json
import argparse
import glob
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback
from gym_env import FrcEnv

def train():
    parser = argparse.ArgumentParser()
    parser.add_argument("--resume", type=str, nargs='?', const='auto', help="Resume training from latest checkpoint ('auto') or specific path")
    args = parser.parse_args()

    # Load ML config
    with open("ml_config.json", "r") as f:
        ml_config = json.load(f)
    
    train_cfg = ml_config['training_params']
    
    # Create environment factory
    def make_env(rank, seed=0):
        def _init():
            # Wrap in Monitor to get rollout/ep_rew_mean in TensorBoard
            env = FrcEnv(render_mode=None)
            env.reset(seed=seed + rank)
            return Monitor(env)
        return _init
    
    n_envs = train_cfg.get('n_envs', 1)
    if n_envs > 1:
        print(f"Using SubprocVecEnv with {n_envs} parallel environments.")
        env = SubprocVecEnv([make_env(i) for i in range(n_envs)])
    else:
        print("Using DummyVecEnv (Single core).")
        env = DummyVecEnv([make_env(0)])
    
    # Model Setup
    model_dir = "ml_models"
    log_dir = "ml_logs"
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    # Detect current run name (PPO_1, PPO_2, etc)
    existing_runs = [d for d in os.listdir(log_dir) if d.startswith("PPO_")]
    if not existing_runs:
        run_id = "PPO_1"
    else:
        try:
            run_numbers = [int(d.split("_")[1]) for d in existing_runs if d.split("_")[1].isdigit()]
            run_id = f"PPO_{max(run_numbers) + 1}"
        except:
            run_id = f"PPO_{len(existing_runs) + 1}"
    
    print(f"Current Training Run: {run_id}")
    
    load_model = None
    if args.resume:
        if args.resume == 'auto':
            files = glob.glob(os.path.join(model_dir, "*.zip"))
            if files:
                load_model = max(files, key=os.path.getmtime)
                print(f"Resuming from latest model: {load_model}")
            else:
                print("No checkpoints found to resume. Starting from scratch.")
        else:
            if os.path.exists(args.resume):
                load_model = args.resume
                print(f"Resuming from specified model: {load_model}")
            else:
                # Fallback to auto if file not found? Or error? Let's error clearly.
                print(f"Error: Specified model path {args.resume} not found.")
                return

    if load_model:
        model = PPO.load(
            load_model,
            env=env,
            tensorboard_log=log_dir,
            learning_rate=train_cfg['learning_rate']
        )
        # Inherit the original log name if possible, or use a new one?
        # SB3 handles it if we don't specify tb_log_name, but let's be explicit
    else:
        model = PPO(
            "MlpPolicy",
            env,
            verbose=1,
            learning_rate=train_cfg['learning_rate'],
            n_steps=train_cfg['n_steps'],
            batch_size=train_cfg['batch_size'],
            gamma=train_cfg['gamma'],
            tensorboard_log=log_dir
        )
    
    # Callbacks
    checkpoint_callback = CheckpointCallback(
        save_freq=max(1000, 10000 // n_envs), # Adjust freq for parallel envs
        save_path=model_dir,
        name_prefix=f"{run_id}_frc_ppo"
    )
    
    # Best Model Tracker
    eval_env = Monitor(FrcEnv(render_mode=None))
    best_model_path = os.path.join(model_dir, f"{run_id}_best")
    os.makedirs(best_model_path, exist_ok=True)
    
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=best_model_path,
        log_path=log_dir,
        eval_freq=max(1000, train_cfg.get('eval_freq', 20000) // n_envs),
        deterministic=True,
        render=False,
        n_eval_episodes=train_cfg.get('eval_episodes', 5)
    )
    
    callbacks = [checkpoint_callback, eval_callback]
    
    print(f"Starting training for {train_cfg['total_timesteps']} timesteps...")
    model.learn(
        total_timesteps=train_cfg['total_timesteps'],
        callback=callbacks,
        progress_bar=True,
        reset_num_timesteps=load_model is None
    )
    
    # Save final model
    final_path = os.path.join(model_dir, f"{run_id}_frc_ppo_final")
    model.save(final_path)
    print(f"Training complete! Model saved to {final_path}")

if __name__ == "__main__":
    train()
