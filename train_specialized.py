import os
import json
import argparse
import glob
from stable_baselines3 import PPO
from stable_baselines3.common.monitor import Monitor
from stable_baselines3.common.vec_env import DummyVecEnv, SubprocVecEnv
from stable_baselines3.common.callbacks import CheckpointCallback, EvalCallback, BaseCallback
from gym_env_specialized import SpecializedFrcEnv

def linear_schedule(initial_value: float):
    def func(progress_remaining: float) -> float:
        return progress_remaining * initial_value
    return func

class TensorboardCallback(BaseCallback):
    def __init__(self, verbose=0):
        super(TensorboardCallback, self).__init__(verbose)

    def _on_step(self) -> bool:
        for info in self.locals['infos']:
            if 'episode' in info:
                scored = info.get('scored', 0)
                self.logger.record('rollout/ep_scored', scored)
                for key, value in info.items():
                    if key.startswith('rew_'):
                        self.logger.record(f'reward/{key}', value)
        return True

def train():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str, choices=["janitor", "lobber"], default="janitor", help="Specialized training mode")
    parser.add_argument("--suffix", type=str, default="", help="Optional suffix for the run ID")
    parser.add_argument("--resume", type=str, help="Path to a model ZIP to resume from")
    args = parser.parse_args()

    # Load ML config
    with open("ml_config.json", "r") as f:
        ml_config = json.load(f)
    
    train_cfg = ml_config['training_params']
    
    # Create environment factory
    def make_env(rank, seed=0):
        def _init():
            env = SpecializedFrcEnv(render_mode=None, mode=args.mode)
            env.reset(seed=seed + rank)
            return Monitor(env)
        return _init
    
    n_envs = train_cfg.get('n_envs', 1)
    env = SubprocVecEnv([make_env(i) for i in range(n_envs)]) if n_envs > 1 else DummyVecEnv([make_env(0)])
    
    model_dir = "ml_models"
    log_dir = "ml_logs"
    os.makedirs(model_dir, exist_ok=True)
    os.makedirs(log_dir, exist_ok=True)

    # Detect Run ID
    existing_runs = [d for d in os.listdir(log_dir) if d.startswith("PPO_")]
    run_num = 1
    if existing_runs:
        try:
            run_numbers = [int(d.split("_")[1]) for d in existing_runs if d.split("_")[1].isdigit()]
            run_num = max(run_numbers) + 1
        except:
            run_num = len(existing_runs) + 1
    
    run_id = f"PPO_{run_num}_{args.mode}"
    if args.suffix:
        run_id = f"{run_id}_{args.suffix}"
    
    run_model_dir = os.path.join(model_dir, run_id)
    os.makedirs(run_model_dir, exist_ok=True)

    if args.resume and os.path.exists(args.resume):
        print(f"Resuming from: {args.resume}")
        model = PPO.load(args.resume, env=env, tensorboard_log=log_dir, learning_rate=train_cfg['learning_rate'])
    else:
        print(f"Starting NEW {args.mode} training: {run_id}")
        policy_kwargs = dict(net_arch=[256, 256])
        model = PPO(
            "MlpPolicy",
            env,
            verbose=1,
            learning_rate=linear_schedule(train_cfg['learning_rate']),
            n_steps=train_cfg['n_steps'],
            batch_size=train_cfg['batch_size'],
            ent_coef=train_cfg.get('ent_coef', 0.0),
            gamma=train_cfg['gamma'],
            policy_kwargs=policy_kwargs,
            tensorboard_log=log_dir
        )
    
    checkpoint_callback = CheckpointCallback(
        save_freq=max(5000, 100000 // n_envs), 
        save_path=run_model_dir,
        name_prefix=f"{run_id}_specialized"
    )
    
    eval_env = Monitor(SpecializedFrcEnv(render_mode=None, mode=args.mode))
    best_model_path = os.path.join(run_model_dir, "best_model")
    os.makedirs(best_model_path, exist_ok=True)
    
    eval_callback = EvalCallback(
        eval_env,
        best_model_save_path=best_model_path,
        log_path=log_dir,
        eval_freq=max(1000, train_cfg.get('eval_freq', 20000) // n_envs),
        deterministic=True,
        n_eval_episodes=train_cfg.get('eval_episodes', 5)
    )
    
    callbacks = [checkpoint_callback, eval_callback, TensorboardCallback()]
    
    model.learn(
        total_timesteps=train_cfg['total_timesteps'],
        callback=callbacks,
        progress_bar=True,
        tb_log_name=run_id
    )
    
    final_path = os.path.join(run_model_dir, f"{run_id}_final")
    model.save(final_path)
    print(f"Training complete! Model saved to {final_path}")

if __name__ == "__main__":
    train()
