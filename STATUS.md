# FRC ML Status Report - Experiment 1.5 (Specialized Workers Breakdown) 🛠️
**Timestamp**: 2026-01-16 16:30 ET

## 🎯 Current Status: Vision Upgrade (v4)
*   **Goal**: Fix "Circling" and lack of "Swerving" (Rear vision).
*   **Change**: Converted Vision Grid from Field-Centric (Map) to **Ego-Centric (Robot)**.
    *   **Old**: "Fuel at North-West" (Requires mental math).
    *   **New**: "Fuel at Back-Left" (Direct actionable input).
*   **Coverage**: 20ft x 20ft box centered on the robot.

## ⏭️ Next Step: Retrain (v4)
*   **Command**: Start fresh (v4) because the input meanings have changed.
    ```bash
    # Terminal 1 (Janitor)
    python train_specialized.py --mode janitor --suffix v4
    
    # Terminal 2 (Lobber)
    python train_specialized.py --mode lobber --suffix v4
    ```
