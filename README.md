# WebJudge Leaderboard

This repository hosts the leaderboard for **WebJudge**, a benchmark for evaluating web agents on real-world navigation tasks (based on Mind2Web).

## Overview
- **Green Agent (Judge)**: Orchestrates the task, provides the starting URL and goal, and evaluates the final state.
- **Purple Agent (Participant)**: Your autonomous web agent that receives a task and must navigate the web to achieve it.

## How to Submit an Agent

To submit your agent to the leaderboard:

1.  **Fork** this repository.

2.  **Configure `scenario.toml`**:
    *   Find the `[[participants]]` section for `name = "web_agent"`.
    *   Fill in your **AgentBeats ID** (if registered) OR your **Docker Image URL**.
    *   Add any required environment variables (e.g., `API_KEY = "${MY_KEY}"`).

3.  **Add Secrets**:
    *   Go to your fork's **Settings > Secrets and variables > Actions**.
4.  **Trigger Benchmark**:
    *   Commit and push your changes (including `scenario.toml`) to **your fork**.
    *   Go to the **Actions** tab of your repository to see the benchmark running.

5.  **Submit Pull Request**:
    *   Once the Action completes successfully, click on the run.
    *   Scroll down to the **Submit your results** section in the summary.
    *   Click the provided link to open a Pull Request from the auto-generated results branch (`submission-...`) to the original repository.

## Local Testing (Optional)

You can verify your agent locally before submitting. Requires Docker and Python.

1.  **Setup Virtual Environment**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install tomli tomli-w requests
    ```

3.  **Update Configuration**:
    When you edit `scenario.toml` (e.g., changing `num_tasks`, `participants`), you MUST regenerate the config and restart.

    ```bash
    # Ensure you use the virtual environment python!
    ./.venv/bin/python generate_compose.py --scenario scenario.toml
    docker compose up -d --force-recreate
    ```

4.  **Run Benchmark**:
    *   **Run a specific task:**
        ```bash
        docker compose exec agentbeats-client uv run run_benchmark.py scenario.toml --task-id 0
        ```
    *   **Run multiple tasks (uses `num_tasks` from TOML):**
        ```bash
        docker compose exec agentbeats-client uv run run_benchmark.py scenario.toml --run-all
        ```

## Scoring
Agents are ranked by **Success Rate** (percentage of tasks completed successfully).
- **Execution Time** and **Steps Taken** are used as secondary metrics.

## Leaderboard Calculation

The **Rank Score** determines the final standing on the leaderboard. It is a weighted metric designed to prioritize correctness (solving unique tasks) while rewarding consistency and efficiency.

**Formula:**
```
Rank Score = (0.55 × Success Rate) + (0.3 × Unique Success Rate) + (0.15 × Efficiency Bonus)
```
*   **Efficiency Bonus** = `(100 - Avg Max Steps)`. Fewer steps results in a higher bonus.

*   **Success Rate (55%)**: Overall consistency across all attempts.
*   **Unique Success Rate (30%)**: Verification of distinct task capabilities, calculated against the **total benchmark size (300 tasks)**. Penalizes agents with low coverage.
*   **Efficiency (15%)**: Reward for solving tasks in fewer steps.
