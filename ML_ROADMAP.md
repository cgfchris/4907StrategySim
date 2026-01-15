# FRC ML Evolution Roadmap 🤖🚀

This document outlines the strategic progression of our AI development, moving from basic mechanics to high-level tactical mastery.

## 🏁 Phase 0: The Initial Sprints (PPO_1 to PPO_19)
**Objective**: Mastery of core mechanics and basic phase awareness.
*   **Result**: Mastered basic driving and scoring. Identified "Phase-Blindness" and architectural limitations.
*   **Success Metric**: Successfully verified rewards and vision sensors.

---

## 🏗️ Experiment 1: The "Tactical Brain" Upgrade (Baseline Established)
**Objective**: Evaluate the impact of neural capacity on decision-making.
*   **Result**: 1M steps reached ~17k reward. High-speed mechanics mastered. No "circling" behavior when fuel is present.
*   **Architecture**: `[256, 256]` neurons.
*   **Discovery**: Robot currently refuses to cross the divider to the Neutral Zone due to "Reward Desert" effect.

---

## 🧹 Experiment 1.5: The Janitor Lab (Specialized Workers - UPCOMING)
**Objective**: Train elite station-specific workers using a decoupled environment.
*   **Approach**: Create `gym_env_specialized.py` to allow for Station-specific rewards.
*   **De-confliction Strategy**: "Flexible Boundaries." Instead of hard physics walls, we use 2 observation features (`Target_X_Center`, `Target_Y_Center`) and a proximity reward.
*   **Hypothesis**: This allows a robot to be a "Scorer" in the Alliance Zone but still retain the ability to drive through the Neutral Zone if the Manager switches its mode.

---

## 🏛️ Experiment 2: Hierarchical RL (The Squad & The Coach)
**Objective**: Decouple mechanical skill from high-level alliance coordination.
*   **The Workers (The Squad)**: Specialized [64, 64] models.  The idea is these models are "modes" that any robot can be switched into
        *   **Score**: This robot masters the "Janitor" role. It stays in the alliance zone, identifies piles created by the lob shots, and clears them into the Hub with maximum efficiency.
        *   **Pass**: This robot masters "Neutral Zone Clearance." It hunts fuel across its assigned half (Upper/Lower) of the neutral zone and lobs it deep into the alliance zone, aiming for high-probability "Safe Zones" (corners) to avoid hitting the Hub structure.
*   **The Manager (The Coach)**: A centralized brain that looks at the status of all 3 robots and assigns roles on the fly.
*   **Solving Coordination Problems**:
    *   **De-confliction**: The Coach ensures two robots aren't chasing the same pile of fuel: do we need our "score" modes to have more input (a target?)
    *   **Phase Distribution**: Deciding that Robot A should build a "Stash" while Robot B and C "Score" to maintain a continuous cycle.
*   **Implementation**: Switching the active model in each `RobotAI` instance dynamically based on the Coach's command.

---

## 📈 Long-Term Aspirations
- **Opponent Awareness**: Introducing enemy robots and evasion tactics.
- **Teammate Coordination**: 3-robot collaborative "Cycles."
- **Behavioral Cloning**: Pre-training the AI using human-driven logic logs.
