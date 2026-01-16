# Walkthrough: Starting Specialized Workers (Experiment 1.5) 🧪🤖

This guide explains how to start specialized training and addresses your questions on testing and strategy.

## 🚀 Training Commands

### 🧪 The "Scoring Lab" Curriculum
To speed up learning, the specialized environment now uses a **Focused Curriculum**:
- **Solo Training**: Opponent robots are removed to eliminate noise and physics crashes.
- **Micro-Matches**: Match duration is reduced to **60 seconds** for faster evaluation loops.
- **Focused Fuel**:
    - **Janitor**: 50-80 balls spawn *only* in the Alliance Zone.
    - **Lobber**: 75-100 balls spawn *only* in the Neutral Zone.
- **Isolation**: No fuel spawns in the "forbidden" zones, forcing the robot to master its specific station.

### 1. Training the "Janitor" (The Scorer)
```bash
# Recommendation: Give each 14 workers, and eval every 5,000 steps for faster feedback
python train_specialized.py --mode janitor --suffix v1 --n_envs 14 --eval_freq 5000
```

### 2. Training the "Lobber" (The Passer)
```bash
python train_specialized.py --mode lobber --suffix v1 --n_envs 14 --eval_freq 5000
```

### 3. Training "Watching" (The Homework View)
If you want to see exactly what the robot "sees" during its specialized training (with target zone markers), use the new watch script:
```bash
python watch_specialized.py --mode janitor --model ml_models/PPO_X_janitor_v1/best_model/model.zip
```

### � 4. Monitoring Progress (TensorBoard)
To see your reward curves, loss, and entropy in real-time, run TensorBoard in a separate terminal:
```bash
tensorboard --logdir ml_logs
```
- Open [http://localhost:6006](http://localhost:6006) in your browser.
- **Pro Tip**: Focus on the `reward/` section. These charts update every training update and show you the "Equal Pay" rewards we set up.

### �🔄 Smart Resuming
I've made resuming much easier! You no longer need to find the specific `.zip` path:

1.  **Auto-Resume (Easiest)**: Automatically picks the latest run for your mode.
    ```bash
    python train_specialized.py --mode janitor --resume
    ```
2.  **Folder-Resume**: Just point to the directory, it will find the `best_model.zip` inside.
    ```bash
    python train_specialized.py --mode janitor --resume ml_models/PPO_X_janitor_v1
    ```
3.  **Specific-Resume**: Still works if you want a specific old checkpoint file.
    ```bash
    python train_specialized.py --mode janitor --resume ml_models/path/to/my_model.zip
    ```

---

## ❓ Q&A and Feedback Adjustments

### 1. "How do I view a model in a test sim?"
I've added a new command-line flag to `main.py` so you can skip the manual config editing!

To test a specific model (e.g., your Janitor), simply run:
```bash
python main.py --model ml_models/PPO_22_janitor_v1/best_model/model.zip
```
- This will automatically start a **1v1 match** as the Red 1 robot using your chosen model.
- You can even use it while your training jobs are running!

### 2. "Resource Management (2 jobs x 15 workers?)"
Since you have **28 cores**, I added a `--n_envs` flag to the trainer.
- Running **14 workers** each is the "Sweet Spot" for your 28 cores. 
- You do **not** need different suffixes for different modes; the system automatically names them `PPO_X_janitor_v1` and `PPO_X_lobber_v1`.

### 3. "Staying Penalty vs. Crossing Penalty"
Great catch. I have confirmed that the penalty in [gym_env_specialized.py](file:///home/chris/frc/4907StrategySim/gym_env_specialized.py) is a **per-step "Stay" penalty**.
- As long as the robot is in the wrong zone, it loses points every single frame. This ensures it doesn't just "accept" the fine and stay there; it is incentivized to return immediately.

### 4. "Why keep the same Observation Space?"
You asked if we should change the observation space now that the robot is localized. 
**Answer: Keep it the same.**
- By keeping the 48-feature vector identical (including game stages), we ensure that the future **Manager** can hot-swap these models instantly.
- If the observation space changed, we would have to "re-wire" the robot's brain every time it switched from Passer to Scorer, which would cause a momentary "freeze" or crash.

---

## 🏆 Specialized Reward Structures

Since these models live in different parts of the field, their "Success" looks different in TensorBoard.

### 🤖 Janitor (The Scorer)
*   **Primary Reward**: `rew_score` (+200 per goal).
*   **Station Goal**: Staying near the **Alliance Wall**.
*   **TensorBoard Tips**: 
    *   Watch `rollout/ep_scored` and `reward/rew_score`.
    *   You should see a high `reward/rew_proximity` as it clears the wall.
    *   `reward/rew_stashing` will likely be **ZERO** (it clears balls, it doesn't pass them).

### 🤖 Lobber (The Passer)
*   **Primary Reward**: `reward/rew_stashing` (+ points for every ball sent deep).
*   **Station Goal**: Staying in the **Neutral Zone**.
*   **TensorBoard Tips**:
    *   Watch `reward/rew_stashing` closely—this is its "Scoring" metric!
    *   `rollout/ep_scored` will likely stay at **ZERO** (it's penalized if it tries to enter the scorer's zone).
    *   `reward/rew_proximity` shows its ability to stay centered in the neutral zone while hunting.

### ⚠️ Shared "Zone Stay" Logic
In BOTH models, there is a total `reward` penalty of **-5.0 per step** if the robot crosses into the forbidden zone. This isn't a separate chart yet, but you'll see it reflected as a sharp drop in `rollout/ep_rew_mean` if the robot "wanders off."
