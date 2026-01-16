# AI Handover Context: FRC ML Training 🤖⚖️

## 🎯 Current Project Goal
We are training specialized **Reinforcement Learning** agents (PPO) for an FRC Rapid React simulator. The focus is on two distinct roles:
1.  **Janitor (Scorer)**: Clears the alliance zone and scores high-hub goals.
2.  **Lobber (Passer)**: Gathers fuel in the neutral zone and passes it across the divider into the alliance zone.

---

## 🛠️ The "Scoring Lab" (Current Environment)
We are currently in **Experiment 1.5**, using `SpecializedFrcEnv` in `gym_env_specialized.py`.
- **Match Duration**: 30 seconds (Turbo Lab).
- **Solo Training**: 1v0 setup to minimize noise.
- **Robot-Oriented Vision**: Observation indices 6-25 (Fuels) and 44-45 (Targets) are now **Self-Oriented** (Front/Back/Left/Right relative to intake).
- **Restored Signals**: Index 47 correctly reflects the `can_pass` flag (Critical for Lobber).
- **Independent Numbering**: Runs are separated into `PPO_N_janitor` and `PPO_N_lobber` sequences.

---

## 📈 Reward Economy (The "Hustle" State)
We have pivoted to a **Strict Completion** economy to stop "Lazy Farming":
- **Zero Progress Rewards**: `hub_proximity_reward_factor` and `stashing_reward_factor` are set to **0.0**. Robots get paid $0 for driving.
- **Strict Completion**: Rewards (+200) only trigger on the literal moment of scoring or stashed_delta.
- **Hustle Pressure**: `time_penalty_per_step` is increased to **-0.1**. Doing nothing is now twice as expensive.
- **Trigger Bonus**: `+10.0` for the `pass/dump` action to reward "pulling the trigger."

---

## 💻 Technical Setup
- **Training Script**: `train_specialized.py`
- **Inference/Watch Script**: `watch_specialized.py`
- **Smart Resume**: Uses recursive search to find `best_model.zip`.
- **Parallelism**: 14 environments across 28 cores (`--n_envs 14`).
- **TensorBoard**: Step counts are continuous across resumes (`reset_num_timesteps=False`).

---

## 🚧 Known Behaviors / Next Steps
- **Swerve "No-Turn"**: The AI (Red 1) uses a Swerve drive. It often strafes and drives backwards because it's more efficient than turning. This is expected.
- **Janitor Progress**: Clearing ~50-60% of fuel.
- **Lobber Progress**: Currently relearning the "Delta" reward after a history of "Absolute Reward" exploits.
- **Goal**: Reach **10M steps** for both models for a stable baseline.
