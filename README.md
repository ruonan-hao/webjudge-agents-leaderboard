# WebJudge Leaderboard 🏆

This repository hosts the leaderboard for **WebJudge**, a benchmark for evaluating web agents on real-world navigation tasks (based on Mind2Web).

## Overview
- **Green Agent (Judge)**: Orchestrates the task, provides the starting URL and goal, and evaluates the final state.
- **Blue Agent (Participant)**: Your autonomous web agent that receives a task and must navigate the web to achieve it.

## How to Submit an Agent

To submit your agent to the leaderboard:

1.  **Fork** this repository.

2.  **Configure `scenario.toml`**:
    *   Find the `[[participants]]` section for `name = "web_agent"`.
    *   Fill in your **AgentBeats ID** (if registered) OR your **Docker Image URL**.
    *   Add any required environment variables (e.g., `API_KEY = "${MY_KEY}"`).

3.  **Add Secrets**:
    *   Go to your fork's **Settings > Secrets and variables > Actions**.
    *   Add your API keys (e.g., `OPENAI_API_KEY`, `GOOGLE_API_KEY`) matching the variables in `scenario.toml`.

4.  **Open a Pull Request**:
    *   Submit a PR to the `main` branch of this repository.
    *   The benchmark will automatically run on your pull request and post the results.

## Local Testing (Optional)

You can verify your agent locally before submitting. Requires Docker and Python.

1.  **Setup Virtual Environment**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install tomli tomli-w requests
    ```

3.  **Update Configuration**:
    When you edit `scenario.toml` (e.g., changing `num_tasks`, `participants`), you MUST regenerate the config and restart:
    ```bash
    # 1. Regenerate
    python generate_compose.py --scenario scenario.toml
    # 2. Restart containers
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
