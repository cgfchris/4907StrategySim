# FRC ML Status Report - Experiment 1 (Large Brain Baseline) 🚀
**Timestamp**: 2026-01-15 09:40 ET

## 🎯 Current Status: Run 19-lb
*   **Architecture**: `[256, 256]` neurons (Experiment 1).
*   **Progress**: ~1,200,000 steps completed.
*   **Performance**: **~17,000 avg reward**.
*   **Observation**: The larger brain has mastered high-speed mechanics much faster than the 64-neuron models. It clears the alliance zone in seconds but currently refuses to cross the divider (the "Reward Desert" effect).

## ✅ Completed in this Session:
1.  **Replaced 1.0 Placeholder**: Fixed the "Phase-Blindness" bug by implementing real Score/Pass sensors.
2.  **Surgically Fixed Observation Indexing**: Restored matching feature indices for existing weights.
3.  **Upgraded Brain Capacity**: Successfully transitioned to the `[256, 256]` architecture.
4.  **Cleaning & Organizing**: Implemented run-specific subdirectories and custom `--suffix` labeling in `train.py`.

## ⏭️ Next Step: Experiment 1.5 (The Janitor Lab)
*   **Goal**: Train a specialized "Scorer/Janitor" worker in the Alliance Zone.
*   **Strategy**: Use `gym_env_specialized.py` to create a "Virtual Box" where the robot is rewarded for staying in its assigned zone while mastering pile-clearing.
*   **Status**: Preparing specialized environment file for launch later today.
