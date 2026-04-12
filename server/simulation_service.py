"""Simulation service layer for the coenv OpenEnv adapter.

This module contains task config loading, condition injection, action execution,
and reward/completion logic so server app wiring stays thin.
"""

from __future__ import annotations

from typing import Dict, Any, Optional
import json
import os
from datetime import datetime
from openenv.core.env_server.interfaces import Environment

try:
    from .coenv_environment import World
except ImportError:
    from coenv_environment import World

try:
    from ..models import CoenvAction, CoenvObservation, CoenvState
except ImportError:
    from models import CoenvAction, CoenvObservation, CoenvState

try:
    from .graders import (
        pod_recovery_grade,
        autoscaling_grade,
        incident_grade,
        security_grade,
        backup_recovery_grade,
        resource_optimization_grade,
    )
except ImportError:
    from graders import (
        pod_recovery_grade,
        autoscaling_grade,
        incident_grade,
        security_grade,
        backup_recovery_grade,
        resource_optimization_grade,
    )


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
        "pod_recovery": "The frontend deployment is crash-looping. The pods are in CrashLoopBackOff state and need to be restarted to recover.",
        "autoscaling": "Traffic has spiked 10x. The backend deployment is experiencing OOM crashes due to overload. Configure Horizontal Pod Autoscaling (set_hpa) to handle the increased load, then restart any crashed pods.",
        "incident": "A cascading incident has degraded auth-service, api-gateway, and frontend services. Multiple pods are in CrashLoopBackOff. Identify the failing services and restart them to restore.",
        "resource_optimization": "The cluster is over-provisioned! Nodes are underutilized (CPU <20%, Memory <30%). Reduce costs by downscaling unused replicas while maintaining service availability (SLA >99%).",
        "security": "A security scan found sensitive data (API keys, passwords) exposed in ConfigMaps. Move all credentials to Kubernetes Secrets and verify no sensitive data remains in ConfigMaps.",
        "backup_recovery": "The database PVC is in Lost state! The PersistentVolume is Available but the claim is broken. Restore data by recreating the PVC and ensuring the database pod mounts the correct volume.",
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

    if task_id == "security":
        try:
            from .conditions.secret_exposure import SecurityCondition
        except ImportError:
            from conditions.secret_exposure import SecurityCondition
        return SecurityCondition(world, config)

    if task_id == "backup_recovery":
        try:
            from .conditions.pvc_lost import PVCLostCondition
        except ImportError:
            from conditions.pvc_lost import PVCLostCondition
        return PVCLostCondition(world, config)

    if task_id == "resource_optimization":
        try:
            from .conditions.underutilization import UnderutilizationCondition
        except ImportError:
            from conditions.underutilization import UnderutilizationCondition
        return UnderutilizationCondition(world, config)

    return None


GRADERS: Dict[str, Any] = {
    "pod_recovery": pod_recovery_grade,
    "autoscaling": autoscaling_grade,
    "incident": incident_grade,
    "security": security_grade,
    "backup_recovery": backup_recovery_grade,
    "resource_optimization": resource_optimization_grade,
}


def _get_field(obj: Any, key: str, default: Any = None) -> Any:
    """Get field from dict or Pydantic model."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump().get(key, default)
    if hasattr(obj, "get"):
        return obj.get(key, default)
    return getattr(obj, key, default)


def validate_action(action: CoenvAction, world: World) -> Optional[str]:
    """Validate action before execution."""
    world_state = world.get_full_state()

    if action.action_type == "scale":
        deployments = world_state.get("deployments", [])
        deployment_names = [_get_field(d, "name") for d in deployments]
        if action.deployment not in deployment_names:
            return f"Deployment '{action.deployment}' not found. Available: {deployment_names}"
        if action.replicas is not None and (
            action.replicas < 1 or action.replicas > 20
        ):
            return f"Replica count must be between 1 and 20, got {action.replicas}"

    elif action.action_type == "delete_pod":
        pods = world_state.get("pods", [])
        pod_names = [_get_field(p, "name") for p in pods]
        if action.pod_name not in pod_names:
            return f"Pod '{action.pod_name}' not found. Available: {pod_names}"

    elif action.action_type == "patch":
        resource_type = action.resource_type or ""
        name = action.name or ""
        if resource_type == "deployment":
            deployments = world_state.get("deployments", [])
            deployment_names = [_get_field(d, "name") for d in deployments]
            if name not in deployment_names:
                return f"Deployment '{name}' not found. Available: {deployment_names}"
        elif resource_type == "configmap":
            configmaps = world_state.get("configmaps", [])
            configmap_names = [_get_field(c, "name") for c in configmaps]
            if name not in configmap_names:
                return f"ConfigMap '{name}' not found. Available: {configmap_names}"
        elif resource_type == "service":
            services = world_state.get("services", [])
            service_names = [_get_field(s, "name") for s in services]
            if name not in service_names:
                return f"Service '{name}' not found. Available: {service_names}"

    elif action.action_type == "rollout_restart":
        deployments = world_state.get("deployments", [])
        deployment_names = [_get_field(d, "name") for d in deployments]
        if action.deployment not in deployment_names:
            return f"Deployment '{action.deployment}' not found. Available: {deployment_names}"

    elif action.action_type == "set_hpa":
        deployments = world_state.get("deployments", [])
        deployment_names = [_get_field(d, "name") for d in deployments]
        if action.deployment not in deployment_names:
            return f"Deployment '{action.deployment}' not found. Available: {deployment_names}"
        if action.max_replicas is not None and action.min_replicas is not None:
            if action.max_replicas < action.min_replicas:
                return f"max_replicas ({action.max_replicas}) must be >= min_replicas ({action.min_replicas})"
        if action.cpu_target_percent is not None:
            if action.cpu_target_percent < 10 or action.cpu_target_percent > 90:
                return f"cpu_target_percent must be between 10 and 90, got {action.cpu_target_percent}"

    elif action.action_type == "drain_node":
        nodes = world_state.get("nodes", [])
        node_names = [_get_field(n, "name") for n in nodes]
        if action.node_name not in node_names:
            return f"Node '{action.node_name}' not found. Available: {node_names}"

    elif action.action_type == "describe":
        resource_type = action.resource_type or ""
        name = action.name or ""
        if resource_type == "deployment":
            deployments = world_state.get("deployments", [])
            deployment_names = [_get_field(d, "name") for d in deployments]
            if name not in deployment_names:
                return f"Deployment '{name}' not found. Available: {deployment_names}"
        elif resource_type == "pod":
            pods = world_state.get("pods", [])
            pod_names = [_get_field(p, "name") for p in pods]
            if name not in pod_names:
                return f"Pod '{name}' not found. Available: {pod_names}"
        elif resource_type == "node":
            nodes = world_state.get("nodes", [])
            node_names = [_get_field(n, "name") for n in nodes]
            if name not in node_names:
                return f"Node '{name}' not found. Available: {node_names}"
        elif resource_type == "service":
            services = world_state.get("services", [])
            service_names = [_get_field(s, "name") for s in services]
            if name not in service_names:
                return f"Service '{name}' not found. Available: {service_names}"
        elif resource_type == "configmap":
            configmaps = world_state.get("configmaps", [])
            configmap_names = [_get_field(c, "name") for c in configmaps]
            if name not in configmap_names:
                return f"ConfigMap '{name}' not found. Available: {configmap_names}"
        elif resource_type == "secret":
            secrets = world_state.get("secrets", [])
            secret_names = [_get_field(s, "name") for s in secrets]
            if name not in secret_names:
                return f"Secret '{name}' not found. Available: {secret_names}"

    return None


GRADERS: Dict[str, Any] = {
    "pod_recovery": pod_recovery_grade,
    "autoscaling": autoscaling_grade,
    "incident": incident_grade,
    "security": security_grade,
    "backup_recovery": backup_recovery_grade,
    "resource_optimization": resource_optimization_grade,
}


def calculate_reward(world: World, task_id: str, step: int, max_steps: int) -> float:
    """Calculate reward based on current state using graders."""
    grader = GRADERS.get(task_id)
    if grader is None:
        return 0.0

    world_state = world.get_full_state()
    return grader(world_state, step, max_steps)


def _collect_task_metrics(world: World) -> Dict[str, Any]:
    """Collect state metrics used by completion logic."""
    pods = world.get_pods()
    deployments = world.get_deployments() if hasattr(world, "get_deployments") else []
    hpas = world.get_hpas() if hasattr(world, "get_hpas") else []

    def _deployment_running_ratio(name: str) -> float:
        dep_pods = [p for p in pods if p.deployment == name]
        if not dep_pods:
            return 0.0
        running = [p for p in dep_pods if p.status == "Running"]
        return len(running) / len(dep_pods)

    def _deployment_unstable_count(name: str, restart_threshold: int = 5) -> int:
        dep_pods = [p for p in pods if p.deployment == name]
        unstable = [
            p
            for p in dep_pods
            if p.status != "Running"
            or p.status == "CrashLoopBackOff"
            or getattr(p, "restarts", 0) >= restart_threshold
        ]
        return len(unstable)

    key_services = ["auth-service", "api-gateway", "frontend"]
    incident_unhealthy_services = 0
    for svc in key_services:
        if _deployment_running_ratio(svc) < 0.8:
            incident_unhealthy_services += 1

    backend_hpa = next((h for h in hpas if h.name == "backend-hpa"), None)
    backend_hpa_ok = (
        backend_hpa is not None
        and backend_hpa.min_replicas >= 2
        and backend_hpa.max_replicas >= 6
        and backend_hpa.cpu_target_percent <= 70
    )

    backend_dep = next((d for d in deployments if d.name == "backend"), None)
    backend_available_ratio = 0.0
    if backend_dep is not None and backend_dep.desired_replicas > 0:
        backend_available_ratio = (
            backend_dep.available_replicas / backend_dep.desired_replicas
        )

    return {
        "frontend_unstable": _deployment_unstable_count("frontend"),
        "frontend_running_ratio": _deployment_running_ratio("frontend"),
        "backend_unstable": _deployment_unstable_count("backend"),
        "backend_running_ratio": _deployment_running_ratio("backend"),
        "backend_hpa_ok": backend_hpa_ok,
        "backend_available_ratio": backend_available_ratio,
        "incident_unhealthy_services": incident_unhealthy_services,
        "incident_key_unstable": sum(
            _deployment_unstable_count(svc) for svc in key_services
        ),
    }


def check_task_complete(
    world: World, task_id: str, baseline_metrics: Optional[Dict[str, Any]] = None
) -> bool:
    """Check if task objective is complete via observable state recovery."""
    metrics = _collect_task_metrics(world)
    baseline = baseline_metrics or {}
    has_baseline = bool(baseline)

    injected_failures = getattr(world, "_injected_failures", {})

    if task_id == "pod_recovery":
        frontend_fixed = (
            "frontend" not in injected_failures
            or injected_failures.get("frontend", {}).get("failure_type") is None
        )

        if not has_baseline:
            return (
                metrics["frontend_unstable"] == 0
                and metrics["frontend_running_ratio"] >= 1.0
                and frontend_fixed
            )
        had_problem = baseline.get("frontend_unstable", 0) > 0
        recovered = (
            metrics["frontend_unstable"] == 0
            and metrics["frontend_running_ratio"] >= 1.0
        )
        return had_problem and recovered and frontend_fixed

    if task_id == "autoscaling":
        backend_fixed = (
            "backend" not in injected_failures
            or injected_failures.get("backend", {}).get("failure_type") is None
        )

        if not has_baseline:
            return (
                metrics["backend_unstable"] == 0
                and metrics["backend_running_ratio"] >= 1.0
                and metrics["backend_available_ratio"] >= 1.0
                and metrics["backend_hpa_ok"]
                and backend_fixed
            )
        had_problem = baseline.get("backend_unstable", 0) > 0
        recovered = (
            metrics["backend_unstable"] == 0
            and metrics["backend_running_ratio"] >= 1.0
            and metrics["backend_available_ratio"] >= 1.0
        )
        return had_problem and recovered and metrics["backend_hpa_ok"] and backend_fixed

    if task_id == "incident":
        key_services = ["auth-service", "api-gateway", "frontend"]
        all_fixed = all(
            svc not in injected_failures
            or injected_failures.get(svc, {}).get("failure_type") is None
            for svc in key_services
        )

        if not has_baseline:
            return (
                metrics["incident_unhealthy_services"] == 0
                and metrics["incident_key_unstable"] == 0
                and all_fixed
            )
        had_problem = (
            baseline.get("incident_unhealthy_services", 0) > 0
            or baseline.get("incident_key_unstable", 0) > 0
        )
        recovered = (
            metrics["incident_unhealthy_services"] == 0
            and metrics["incident_key_unstable"] == 0
        )
        return had_problem and recovered and all_fixed

    if task_id == "security":
        configmaps = world.get_configmaps()
        sensitive_keys = {"API_KEY", "DB_PASSWORD", "JWT_SECRET", "SECRET", "PASSWORD"}
        has_exposed = any(
            any(
                k.upper() in sensitive_keys
                or v in {"sk_live_", "p@ss", "secret", "超级", "_secret"}
                for k, v in cm.data.items()
            )
            for cm in configmaps
        )
        secrets = world.get_secrets()
        has_secrets = len(secrets) > 0
        if not has_baseline:
            return not has_exposed and has_secrets
        had_problem = baseline.get("security_exposed_services", 0) > 0
        recovered = not has_exposed and has_secrets
        return had_problem and recovered

    if task_id == "backup_recovery":
        pvcs = world.get_persistentvolumeclaims()
        pvc = next((p for p in pvcs if p.name == "database-pvc"), None)
        pvs = world.get_persistentvolumes()
        pv = next((p for p in pvs if p.name == "pv-database"), None)
        pods = world.get_pods()
        db_pods = [p for p in pods if p.deployment == "database"]
        db_ready = all(p.status == "Running" for p in db_pods) if db_pods else False
        if not has_baseline:
            return (
                (pvc and pvc.status == "Bound")
                and (pv and pv.status == "Bound")
                and db_ready
            )
        had_problem = baseline.get("pvc_status") == "Lost"
        recovered = pvc and pvc.status == "Bound" and pv and pv.status == "Bound"
        return had_problem and recovered and db_ready

    if task_id == "resource_optimization":
        nodes = world.get_nodes()
        total_cpu = sum(n.cpu_usage for n in nodes) / len(nodes) if nodes else 100
        total_mem = sum(n.mem_usage for n in nodes) / len(nodes) if nodes else 100
        optimal = 25 <= total_cpu <= 70 and 35 <= total_mem <= 80
        deployments = world.get_deployments()
        total_replicas = sum(d.available_replicas for d in deployments)
        ideal = 6
        if not has_baseline:
            return optimal and total_replicas <= ideal
        had_problem = baseline.get("cluster_overprovisioned", True)
        recovered = total_replicas <= ideal
        return had_problem and recovered and optimal

    return False


class CoenvEnvironment(Environment):
    """OpenEnv environment adapter over the in-memory Kubernetes simulator."""

    def __init__(self):
        self.config: Dict[str, Any] = load_config()
        self.episode_id = f"episode-{os.getpid()}-{int(os.times()[4] * 1000)}"
        self.world = World(self.config, seed=self.config.get("seed"))
        self.current_task = "pod_recovery"
        self.current_objective = get_objective_for_task(self.current_task)
        self._baseline_metrics: Dict[str, Any] = {}

    def reset(self, task: str = "pod_recovery", **_: Any) -> CoenvObservation:
        """Reset simulator state for the selected task and return initial observation."""
        self.current_task = task
        self.current_objective = get_objective_for_task(task)
        condition = get_condition_for_task(task, self.world, self.config)

        self.world.reset_to_healthy()
        if condition is not None:
            if task == "pod_recovery":
                condition.inject(target_deployment="frontend", failure_rate=0.8)
            elif task == "autoscaling":
                condition.inject(target_deployment="backend", failure_rate=0.8)
            elif task == "incident":
                condition.inject(
                    root_cause_service="auth-service", failure_probability=0.8
                )
                try:
                    from .conditions.crash_loop import CrashLoopCondition
                except ImportError:
                    from conditions.crash_loop import CrashLoopCondition
                CrashLoopCondition(self.world, self.config).inject(
                    target_deployment="api-gateway", failure_rate=0.7
                )
                CrashLoopCondition(self.world, self.config).inject(
                    target_deployment="frontend", failure_rate=0.5
                )
            elif task == "security":
                condition.inject()
            elif task == "backup_recovery":
                condition.inject()
            elif task == "resource_optimization":
                condition.inject()
            self._baseline_metrics = _collect_task_metrics(self.world)

        return self._observation(done=False, reward=0.0, info={"task": task})

    def step(self, action: CoenvAction, **_: Any) -> CoenvObservation:
        """Apply one action, tick the world, and return updated observation with reward."""
        info: Dict[str, Any] = {}

        validation_error = validate_action(action, self.world)
        if validation_error:
            info["error"] = validation_error
            info["invalid_action"] = True

            # Invalid actions still consume a step so episodes make progress and can truncate.
            self.world.tick()

            max_steps = (
                self.config.get("tasks", {})
                .get(self.current_task, {})
                .get("max_steps", 15)
            )
            reward = calculate_reward(
                self.world, self.current_task, self.world.step_count, max_steps
            )
            done = check_task_complete(
                self.world, self.current_task, self._baseline_metrics
            )

            truncated = self.world.step_count >= max_steps and not done
            if truncated:
                info["truncated"] = True
                done = True

            return self._observation(done=done, reward=reward, info=info)

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
                min_replicas = (
                    action.min_replicas if action.min_replicas is not None else 1
                )
                max_replicas = (
                    action.max_replicas if action.max_replicas is not None else 10
                )
                cpu_target = (
                    action.cpu_target_percent
                    if action.cpu_target_percent is not None
                    else 80
                )
                self.world.set_hpa(deployment, min_replicas, max_replicas, cpu_target)
                info["hpa_set"] = deployment

            elif action.action_type == "describe":
                resource_type = action.resource_type or ""
                name = action.name or ""
                info["described"] = f"{resource_type}/{name}"
                info["describe_detail"] = self.world.describe(resource_type, name)

            elif action.action_type == "wait":
                info["waited"] = True

            elif action.action_type == "create_secret":
                new_secret = {
                    "name": action.name,
                    "data": action.data or {},
                    "type": "Opaque",
                    "last_updated": datetime.now().isoformat(),
                }
                self.world.cluster_state["secrets"].append(new_secret)
                info["secret_created"] = action.name

            else:
                info["error"] = f"Unknown action type: {action.action_type}"

        except Exception as e:
            info["error"] = str(e)

        self.world.tick()

        max_steps = (
            self.config.get("tasks", {}).get(self.current_task, {}).get("max_steps", 15)
        )
        reward = calculate_reward(
            self.world, self.current_task, self.world.step_count, max_steps
        )

        done = check_task_complete(
            self.world, self.current_task, self._baseline_metrics
        )
        truncated = self.world.step_count >= max_steps and not done
        if truncated:
            info["truncated"] = True
            done = True

        return self._observation(done=done, reward=reward, info=info)

    @property
    def state(self) -> CoenvState:
        """Return current observation without applying an action."""
        return CoenvState(episode_id=self.episode_id, step_count=self.world.step_count)

    def _observation(
        self, done: bool, reward: float, info: Dict[str, Any]
    ) -> CoenvObservation:
        obs = self.world.get_observation(self.current_objective)
        return CoenvObservation(
            nodes=obs.nodes,
            pods=obs.pods,
            deployments=obs.deployments,
            services=obs.services,
            configmaps=obs.configmaps,
            secrets=obs.secrets,
            ingresses=obs.ingresses,
            persistentvolumes=obs.persistentvolumes,
            persistentvolumeclaims=obs.persistentvolumeclaims,
            hpas=obs.hpas,
            events=obs.events,
            logs=obs.logs,
            metrics=obs.metrics,
            step=obs.step,
            objective=obs.objective,
            done=done,
            reward=reward,
            metadata=info,
        )

    def close(self) -> None:
        return
