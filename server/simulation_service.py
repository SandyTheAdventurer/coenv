"""Simulation service layer for the coenv OpenEnv adapter.

This module contains task config loading, condition injection, action execution,
and reward/completion logic so server app wiring stays thin.
"""

from __future__ import annotations

from typing import Dict, Any
import json
import os
from openenv.core.env_server.interfaces import Environment
try:
    from .coenv_environment import World
except ImportError:
    from coenv_environment import World

try:
    from ..models import CoenvAction, CoenvObservation
except ImportError:
    from models import CoenvAction, CoenvObservation


def load_config() -> Dict[str, Any]:
    """Load configuration from config.json with sensible defaults."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
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
                "incident": {"max_steps": 30, "success_threshold": 0.80},
            },
        }


def get_objective_for_task(task_id: str) -> str:
    """Get the objective string for a task."""
    objectives = {
        "pod_recovery": "The frontend deployment is crash-looping. Diagnose and fix the root cause so that all pods reach Running state.",
        "autoscaling": "Traffic has spiked 10x. The api-server deployment is overloaded. Configure autoscaling and ensure p95 latency stays below 500ms.",
        "incident": "A cascading incident has degraded auth-service, api-gateway, and data-processor. Identify the root cause and restore all three services to healthy state without data loss.",
    }
    return objectives.get(task_id, "Maintain cluster health")


def get_condition_for_task(task_id: str, world: World, config: Dict[str, Any]):
    """Get condition injector for a task id."""
    if task_id == "pod_recovery":
        try:
            from .conditions.crash_loop import CrashLoopCondition
        except ImportError:
            from conditions.crash_loop import CrashLoopCondition
        return CrashLoopCondition(world, config)

    if task_id == "autoscaling":
        try:
            from .conditions.oom_kill import OOMKillCondition
        except ImportError:
            from conditions.oom_kill import OOMKillCondition
        return OOMKillCondition(world, config)

    if task_id == "incident":
        try:
            from .conditions.cascade_failure import CascadeFailureCondition
        except ImportError:
            from conditions.cascade_failure import CascadeFailureCondition
        return CascadeFailureCondition(world, config)

    return None


def calculate_reward(world: World, task_id: str) -> float:
    """Calculate reward based on current state."""
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
    """Check if task objective is complete."""
    if task_id == "pod_recovery":
        pods = world.get_pods()
        frontend_pods = [p for p in pods if p.deployment == "frontend"]
        running = [p for p in frontend_pods if p.status == "Running"]
        return len(frontend_pods) > 0 and len(running) == len(frontend_pods)

    if task_id == "autoscaling":
        pods = world.get_pods()
        backend_pods = [p for p in pods if p.deployment == "backend"]
        running = [p for p in backend_pods if p.status == "Running"]
        return len(backend_pods) >= 2 and len(running) >= 2

    if task_id == "incident":
        pods = world.get_pods()
        key_services = ["auth-service", "api-gateway", "frontend"]
        for svc in key_services:
            svc_pods = [p for p in pods if p.deployment == svc]
            running = [p for p in svc_pods if p.status == "Running"]
            if svc_pods and len(running) < len(svc_pods) * 0.8:
                return False
        return True

    return False


class CoenvEnvironment(Environment):
    """OpenEnv environment adapter over the in-memory Kubernetes simulator."""

    def __init__(self):
        self.config: Dict[str, Any] = load_config()
        self.world = World(self.config, seed=self.config.get("seed"))
        self.current_task = "pod_recovery"
        self.current_objective = get_objective_for_task(self.current_task)

    def reset(self, task: str = "pod_recovery", **_: Any) -> CoenvObservation:
        """Reset simulator state for the selected task and return initial observation."""
        self.current_task = task
        self.current_objective = get_objective_for_task(task)
        condition = get_condition_for_task(task, self.world, self.config)
        self.world.reset(condition)
        return self._observation(done=False, reward=0.0, info={"task": task})

    def step(self, action: CoenvAction, **_: Any) -> CoenvObservation:
        """Apply one action, tick the world, and return updated observation with reward."""
        info: Dict[str, Any] = {}

        try:
            if action.action_type == "scale":
                deployment = action.deployment or ""
                replicas = action.replicas if action.replicas is not None else 1
                self.world.scale(deployment, replicas)
                info["scaled"] = deployment
                info["replicas"] = replicas

            elif action.action_type == "delete_pod":
                pod_name = action.pod_name or ""
                self.world.delete_pod(pod_name)
                info["deleted"] = pod_name

            elif action.action_type == "patch":
                resource_type = action.resource_type or ""
                name = action.name or ""
                patch = action.patch or {}
                self.world.apply_patch(resource_type, name, patch)
                info["patched"] = f"{resource_type}/{name}"

            elif action.action_type == "rollout_restart":
                deployment = action.deployment or ""
                self.world.rollout_restart(deployment)
                info["restarted"] = deployment

            elif action.action_type == "drain_node":
                node_name = action.node_name or ""
                self.world.drain_node(node_name)
                info["drained"] = node_name

            elif action.action_type == "set_hpa":
                deployment = action.deployment or ""
                min_replicas = action.min_replicas if action.min_replicas is not None else 1
                max_replicas = action.max_replicas if action.max_replicas is not None else 10
                cpu_target = action.cpu_target_percent if action.cpu_target_percent is not None else 80
                self.world.set_hpa(deployment, min_replicas, max_replicas, cpu_target)
                info["hpa_set"] = deployment

            elif action.action_type == "describe":
                resource_type = action.resource_type or ""
                name = action.name or ""
                info["described"] = f"{resource_type}/{name}"
                info["describe_detail"] = self.world.describe(resource_type, name)

            else:
                info["error"] = f"Unknown action type: {action.action_type}"

        except Exception as e:
            info["error"] = str(e)

        self.world.tick()

        reward = calculate_reward(self.world, self.current_task)

        done = False
        max_steps = self.config.get("tasks", {}).get(self.current_task, {}).get("max_steps", 15)
        if self.world.step_count >= max_steps:
            done = True
        if check_task_complete(self.world, self.current_task):
            done = True

        return self._observation(done=done, reward=reward, info=info)

    def state(self, **_: Any) -> Dict[str, Any]:
        """Return lightweight environment state metadata."""
        return {
            "step": self.world.step_count,
            "task": self.current_task,
            "objective": self.current_objective,
        }

    def _observation(self, done: bool, reward: float, info: Dict[str, Any]) -> CoenvObservation:
        obs = self.world.get_observation(self.current_objective)
        return CoenvObservation(
            nodes=obs.nodes,
            pods=obs.pods,
            deployments=obs.deployments,
            services=obs.services,
            configmaps=obs.configmaps,
            hpas=obs.hpas,
            events=obs.events,
            step=obs.step,
            objective=obs.objective,
            done=done,
            reward=reward,
            metadata=info,
        )
    def close(self) -> None:
        return