"""
COEnv FastAPI Application
Exposes /reset /step /state endpoints
"""

from openenv.core.env_server import create_app
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List, Literal
import uvicorn
import json
import os
import sys

try:
    from .COEnv_environment import World
    from .models import ClusterObservation, RewardSignal, KubeAction
except ImportError:
    # Support running as a top-level module inside container images.
    from COEnv_environment import World
    from models import ClusterObservation, RewardSignal, KubeAction

app = FastAPI(title="COEnv", description="Kubernetes Simulator for OpenEnv")

# Global world instance
world_instance: Optional[World] = None
config: Dict[str, Any] = {}
current_task: Optional[str] = None
current_objective: str = ""


def load_config():
    """Load configuration from config.json"""
    global config
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        config = {
            "num_nodes": 3,
            "node_cpu_capacity": 4,
            "node_mem_capacity": 8192,
            "pod_cpu_request": 250,
            "pod_mem_request": 128,
            "pod_cpu_limit": 500,
            "pod_mem_limit": 256,
            "crash_loop_failure_rate": 0.7,
            "oom_kill_failure_rate": 0.6,
            "node_failure_rate": 0.3,
            "cascade_failure_probability": 0.5,
            "task_timeout_values": 300,
            "tasks": {
                "pod_recovery": {"max_steps": 15, "success_threshold": 0.9},
                "autoscaling": {"max_steps": 20, "success_threshold": 0.85},
                "incident": {"max_steps": 30, "success_threshold": 0.80}
            }
        }


# Import conditions for task injection
def get_condition_for_task(task_id: str):
    """Get the condition injector for a task"""
    if task_id == "pod_recovery":
        try:
            from .conditions.crash_loop import CrashLoopCondition
        except ImportError:
            from conditions.crash_loop import CrashLoopCondition
        return CrashLoopCondition(world_instance, config)
    elif task_id == "autoscaling":
        try:
            from .conditions.oom_kill import OOMKillCondition
        except ImportError:
            from conditions.oom_kill import OOMKillCondition
        return OOMKillCondition(world_instance, config)
    elif task_id == "incident":
        try:
            from .conditions.cascade_failure import CascadeFailureCondition
        except ImportError:
            from conditions.cascade_failure import CascadeFailureCondition
        return CascadeFailureCondition(world_instance, config)
    return None


def get_objective_for_task(task_id: str) -> str:
    """Get the objective string for a task"""
    objectives = {
        "pod_recovery": "The frontend deployment is crash-looping. Diagnose and fix the root cause so that all pods reach Running state.",
        "autoscaling": "Traffic has spiked 10×. The api-server deployment is overloaded. Configure autoscaling and ensure p95 latency stays below 500ms.",
        "incident": "A cascading incident has degraded auth-service, api-gateway, and data-processor. Identify the root cause and restore all three services to healthy state without data loss."
    }
    return objectives.get(task_id, "Maintain cluster health")


@app.on_event("startup")
async def startup_event():
    """Initialize the world on startup"""
    global world_instance, current_task, current_objective
    load_config()
    world_instance = World(config, seed=config.get("seed"))
    print("COEnv initialized")


class ResetRequest(BaseModel):
    """Request body for /reset endpoint"""
    task: Optional[str] = Field(default="pod_recovery", description="Task ID to initialize")


@app.post("/reset")
async def reset(request: ResetRequest = ResetRequest()):
    """Reset the environment and return initial observation"""
    global world_instance, current_task, current_objective
    
    if world_instance is None:
        raise HTTPException(status_code=500, detail="World not initialized")
    
    current_task = request.task
    current_objective = get_objective_for_task(request.task)
    
    # Get condition for the task and inject it
    condition = get_condition_for_task(request.task)
    
    # Reset with the condition
    observation = world_instance.reset(condition)
    
    return observation


class StepRequest(BaseModel):
    """Request body for /step endpoint"""
    action: Dict[str, Any] = Field(..., description="Action to execute")


@app.post("/step")
async def step(request: StepRequest):
    """Apply an action and return next observation, reward, done, info"""
    global world_instance, current_task, current_objective
    
    if world_instance is None:
        raise HTTPException(status_code=500, detail="World not initialized")
    
    action = request.action
    action_type = action.get("action_type", "")
    
    # Execute action
    info = {}
    reward = 0.0
    done = False
    
    try:
        if action_type == "scale":
            deployment = action.get("deployment", "")
            replicas = action.get("replicas", 1)
            world_instance.scale(deployment, replicas)
            info["scaled"] = deployment
            info["replicas"] = replicas
            
        elif action_type == "delete_pod":
            pod_name = action.get("pod_name", "")
            world_instance.delete_pod(pod_name)
            info["deleted"] = pod_name
            
        elif action_type == "patch":
            resource_type = action.get("resource_type", "")
            name = action.get("name", "")
            patch = action.get("patch", {})
            world_instance.apply_patch(resource_type, name, patch)
            info["patched"] = f"{resource_type}/{name}"
            
        elif action_type == "rollout_restart":
            deployment = action.get("deployment", "")
            world_instance.rollout_restart(deployment)
            info["restarted"] = deployment
            
        elif action_type == "drain_node":
            node_name = action.get("node_name", "")
            world_instance.apply_patch("node", node_name, {"status": "SchedulingDisabled"})
            info["drained"] = node_name
            
        elif action_type == "set_hpa":
            deployment = action.get("deployment", "")
            min_replicas = action.get("min_replicas", 1)
            max_replicas = action.get("max_replicas", 10)
            cpu_target = action.get("cpu_target_percent", 80)
            hpa_name = f"{deployment}-hpa"
            world_instance.apply_patch("hpa", hpa_name, {
                "min_replicas": min_replicas,
                "max_replicas": max_replicas,
                "cpu_target_percent": cpu_target
            })
            info["hpa_set"] = deployment
            
        elif action_type == "describe":
            # Investigation action - no state change
            resource_type = action.get("resource_type", "")
            name = action.get("name", "")
            info["described"] = f"{resource_type}/{name}"
            
        else:
            info["error"] = f"Unknown action type: {action_type}"
            reward = -0.1  # Penalty for invalid action
            
    except Exception as e:
        info["error"] = str(e)
        reward = -0.1
    
    # Always tick after an action
    world_instance.tick()
    
    # Calculate reward based on current state
    reward = calculate_reward(world_instance, current_task)
    
    # Check if task is done
    max_steps = config.get("tasks", {}).get(current_task, {}).get("max_steps", 15)
    if world_instance.step_count >= max_steps:
        done = True
    
    # Check if all pods are running (simplified done check)
    if check_task_complete(world_instance, current_task):
        done = True
    
    observation = world_instance.get_observation(current_objective)
    
    reward_signal = RewardSignal(reward=reward, done=done, info=info)
    
    return {
        "observation": observation.model_dump(),
        "reward": reward_signal.reward,
        "done": reward_signal.done,
        "info": reward_signal.info
    }


def calculate_reward(world: World, task_id: str) -> float:
    """Calculate reward based on current state"""
    if task_id == "pod_recovery":
        pods = world.get_pods()
        frontend_pods = [p for p in pods if p.deployment == "frontend"]
        running = [p for p in frontend_pods if p.status == "Running"]
        if frontend_pods:
            return len(running) / len(frontend_pods)
    elif task_id == "autoscaling":
        pods = world.get_pods()
        backend_pods = [p for p in pods if p.deployment == "backend"]
        running = [p for p in backend_pods if p.status == "Running"]
        if backend_pods:
            return min(len(running) / len(backend_pods), 1.0)
    elif task_id == "incident":
        pods = world.get_pods()
        key_services = ["auth-service", "api-gateway", "frontend"]
        healthy_count = 0
        for svc in key_services:
            svc_pods = [p for p in pods if p.deployment == svc]
            running = [p for p in svc_pods if p.status == "Running"]
            if svc_pods and len(running) >= len(svc_pods) * 0.8:
                healthy_count += 1
        return healthy_count / len(key_services) if key_services else 0.0
    
    return 0.0


def check_task_complete(world: World, task_id: str) -> bool:
    """Check if task is complete"""
    if task_id == "pod_recovery":
        pods = world.get_pods()
        frontend_pods = [p for p in pods if p.deployment == "frontend"]
        running = [p for p in frontend_pods if p.status == "Running"]
        return len(frontend_pods) > 0 and len(running) == len(frontend_pods)
    elif task_id == "autoscaling":
        pods = world.get_pods()
        backend_pods = [p for p in pods if p.deployment == "backend"]
        running = [p for p in backend_pods if p.status == "Running"]
        return len(backend_pods) >= 2 and len(running) >= 2
    elif task_id == "incident":
        pods = world.get_pods()
        key_services = ["auth-service", "api-gateway", "frontend"]
        for svc in key_services:
            svc_pods = [p for p in pods if p.deployment == svc]
            running = [p for p in svc_pods if p.status == "Running"]
            if svc_pods and len(running) < len(svc_pods) * 0.8:
                return False
        return True
    return False


@app.get("/state")
async def get_state():
    """Return full current simulator state"""
    global world_instance, current_objective
    
    if world_instance is None:
        raise HTTPException(status_code=500, detail="World not initialized")
    
    return world_instance.get_observation(current_objective).model_dump()


@app.get("/health")
async def health():
    """Container health endpoint used by Docker health checks."""
    return {"status": "ok"}


def main() -> None:
    """Application entrypoint for local execution."""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()