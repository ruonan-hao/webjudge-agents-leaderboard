
import asyncio
import argparse
import sys
import os
import signal
import subprocess
import time
import json
import shlex
import tomllib
from pathlib import Path
# Add src to path to import agentbeats modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))
from agentbeats.client import send_message, calculate_timeout_from_max_steps
from agentbeats.models import EvalRequest
from agentbeats.run_scenario import parse_toml, wait_for_agents

# Import dataset loader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "scenarios/webjudge")))
import dataset_loader

# load_dotenv(override=True)  # Environment variables provided by runtime

async def run_benchmark_task(task_data: dict, green_url: str, base_config: dict, timeout: int = None):
    """
    Run a single benchmark task.
    """
    # Merge task data into config
    # We override task_description and start_url
    task_config = base_config.copy()
    task_config["task_description"] = task_data["task_description"]
    task_config["start_url"] = task_data["start_url"]
    
    print(f"\n🚀 Running Task {task_data['index']} (ID: {task_data['task_id']})")
    print(f"📝 Description: {task_data['task_description']}")
    print(f"🔗 URL: {task_data['start_url']}")
    
    # Construct request
    # Note: We need to reconstruct the participants map as in client_cli.py
    # But here we assume `req` object structure or reconstruct it.
    # To keep it simple, we'll assume the caller passes a proper EvalRequest structure 
    # but with updated config.
    
    # Actually, we need to reconstruct the EvalRequest
    participants = {}
    # We need to know participants from somewhere. 
    # Let's pass the parsed TOML data to this function or just the participants map.
    
    return {
        "success": False, 
        "score": 0.0, 
        "reasoning": "Not implemented yet"
    }

async def event_consumer(event, card):
    """
    Consume events and extract final result.
    This is similar to client_cli.py but we want to capture the result return it.
    """
    # We'll use a simple print for now, but in a real benchmark we'd capture data
    from a2a.types import Message, TaskStatusUpdateEvent, TaskArtifactUpdateEvent
    
    match event:
        case Message() as msg:
             # Check for final result in message parts
             pass
                
        case (task, TaskStatusUpdateEvent() as status_event):
            status = status_event.status
            print(f"[Status: {status.state.value}]")
            if status.state.value == "completed":
                # Try to parse artifacts to find score
                pass

        case (task, TaskArtifactUpdateEvent() as artifact_event):
            # Print artifact updates
            pass

        case _:
            pass

# We need a shared result container/queue because event_consumer is a callback
class ResultCollector:
    def __init__(self):
        self.result = {"success": False, "final_score": 0.0, "reasoning": "No result received"}
        self.completed = False

    async def consumer(self, event, card):
        from a2a.types import Message, TaskStatusUpdateEvent, TaskArtifactUpdateEvent, TextPart
        
        match event:
            case (task, TaskStatusUpdateEvent() as status_event):
                print(f"[Status: {status_event.status.state.value}]")
                if status_event.status.state.value == "completed":
                    self.completed = True
                    # Check artifacts for final score
                    if task.artifacts:
                         for artifact in task.artifacts:
                             for part in artifact.parts:
                                 if isinstance(part.root, TextPart):
                                     try:
                                         data = json.loads(part.root.text)
                                         if "final_score" in data:
                                             self.result = data
                                     except:
                                         pass
            case _:
                pass

async def main():
    parser = argparse.ArgumentParser(description="Run WebJudge Benchmark")
    parser.add_argument("scenario", help="Path to scenario TOML file")
    parser.add_argument("--task-id", type=int, help="Run specific task index")
    parser.add_argument("--random", action="store_true", help="Run random task")
    parser.add_argument("--run-all", action="store_true", help="Run all tasks")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of tasks for run-all (overrides config)")
    parser.add_argument("--show-logs", action="store_true", help="Show agent stdout/stderr")
    args = parser.parse_args()

    if not (args.task_id is not None or args.random or args.run_all):
        print("Please specify --task-id, --random, or --run-all")
        sys.exit(1)

    # Parse scenario config to get agent info
    cfg = parse_toml(args.scenario)
    
    # Start agents
    procs = []
    sink = None if args.show_logs else subprocess.DEVNULL
    parent_bin = str(Path(sys.executable).parent)
    base_env = os.environ.copy()
    base_env["PATH"] = parent_bin + os.pathsep + base_env.get("PATH", "")
    
    try:
        # Start participants
        for p in cfg["participants"]:
            cmd_args = shlex.split(p.get("cmd", ""))
            if cmd_args:
                print(f"Starting {p['role']} at {p['host']}:{p['port']}")
                procs.append(subprocess.Popen(
                    cmd_args, env=base_env, stdout=sink, stderr=sink,
                    text=True, start_new_session=True
                ))
        
        # Start green agent
        green_cmd = cfg["green_agent"].get("cmd", "")
        if green_cmd:
            print(f"Starting green agent at {cfg['green_agent']['host']}:{cfg['green_agent']['port']}")
            procs.append(subprocess.Popen(
                shlex.split(green_cmd), env=base_env, stdout=sink, stderr=sink,
                text=True, start_new_session=True
            ))
            
        # Wait for agents
        if not await wait_for_agents(cfg):
            print("Error: Agents failed to start")
            return

        # Prepare tasks
        tasks = []
        if args.task_id is not None:
             tasks.append(dataset_loader.load_mind2web_task(index=args.task_id))
        elif args.random:
             tasks.append(dataset_loader.load_mind2web_task(index=None))
        elif args.run_all:
             total = dataset_loader.get_total_tasks()
             # Determine limit: CLI arg > TOML config > Default (10)
             limit_val = args.limit
             if limit_val is None:
                 limit_val = int(cfg["config"].get("num_tasks", 10))
                 
             limit = min(total, limit_val)
             print(f"Running {limit} tasks...")
             for i in range(limit):
                 tasks.append(dataset_loader.load_mind2web_task(index=i))
        
        # Parse connection info for Client
        green = cfg["green_agent"]
        green_endpoint = f"http://{green['host']}:{green['port']}"
        
        participants_map = {}
        for p in cfg["participants"]:
             role = p.get("role")
             # Host/port are extracted in parse_toml as host, port keys
             # but we need full endpoint string if it wasn't preserved
             # parse_toml returns dict with 'host', 'port'. 
             # We should probably use the 'endpoint' from the raw TOML if available, 
             # OR reconstruct it. parse_toml logic: `host, int(port)`.
             # Let's reconstruct:
             participants_map[role] = f"http://{p['host']}:{p['port']}"

        # Base config from TOML
        base_config = cfg["config"]

        # Run benchmark loop
        results = []
        
        for task in tasks:
            print(f"\n--- Processing Task {task['index']} ---")
            
            # Construct dynamic config
            dynamic_config = base_config.copy()
            dynamic_config["task_description"] = task["task_description"]
            dynamic_config["start_url"] = task["start_url"]
            dynamic_config["task_id"] = task["task_id"]
            
            # Create EvalRequest
            req = EvalRequest(
                participants=participants_map,
                config=dynamic_config
            )
            
            # Calculate timeout
            max_steps = dynamic_config.get("max_steps", 30)
            timeout = calculate_timeout_from_max_steps(max_steps, seconds_per_step=30, buffer=180)
            
            # Run task
            collector = ResultCollector()
            msg = req.model_dump_json()
            
            start_time = time.time()
            try:
                await send_message(msg, green_endpoint, streaming=True, consumer=collector.consumer, timeout=timeout)
                duration = time.time() - start_time
                
                print(f"Completed in {duration:.2f}s")
                print(f"Result: {collector.result}")
                
                results.append({
                    "task_index": task["index"],
                    "task_id": task["task_id"],
                    "goal": task["task_description"],
                    "max_steps": max_steps,
                    "success": collector.result.get("success", False),
                    "final_score": collector.result.get("final_score", 0.0),
                    "reasoning": collector.result.get("reasoning", ""),
                    "duration": duration
                })
                
            except Exception as e:
                print(f"Task failed with error: {e}")
                results.append({
                    "task_index": task["index"],
                    "task_id": task["task_id"],
                    "error": str(e)
                })

        # Print Summary
        print("\n--- Benchmark Summary ---")
        success_count = sum(1 for r in results if r.get("success"))
        print(f"Total Tasks: {len(results)}")
        print(f"Success Rate: {success_count}/{len(results)} ({success_count/len(results)*100:.1f}%)")
        # Save results to output/results.json
        # Re-read raw TOML to get metadata that parse_toml might drop
        with open(args.scenario, "rb") as f:
            raw_cfg = tomllib.load(f)
        
        # Build map: name/role -> agentbeats_id
        # Check both 'name' (original toml) and 'role' (generated a2a-scenario.toml)
        raw_participants = {}
        for p in raw_cfg.get("participants", []):
            key = p.get("name") or p.get("role")
            if key:
                raw_participants[key] = p.get("agentbeats_id", "")
        
        # Format must match AgentBeats schema: { "participants": {role: id}, "results": [...] }
        # Note: cfg['participants'] uses 'role' (enforced by parse_toml) matching raw 'name'/'role'
        participants_info = {p["role"]: raw_participants.get(p["role"], "") for p in cfg["participants"]}
        
        final_output = {
            "participants": participants_info,
            "results": results
        }
        
        output_path = Path("output/results.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(final_output, f, indent=2)
        print(f"Results saved to {output_path}")

    except Exception as e:
        print(f"Benchmark error: {e}")
    finally:
        print("\nShutting down agents...")
        for p in procs:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGTERM)
        time.sleep(1)
        for p in procs:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)

if __name__ == "__main__":
    asyncio.run(main())
