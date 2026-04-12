"""
Grader for Autoscaling Task
"""

from typing import Dict, Any


def _get_field(obj: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get field from dict or Pydantic model."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump().get(key, default)
    return obj.get(key, default)


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the autoscaling task"""
    quality_score = 0.0

    deployments = world_state.get("deployments", [])
    backend_deployment = next(
        (d for d in deployments if _get_field(d, "name") == "backend"),
        None,
    )
    if not backend_deployment:
        return 0.0001

    desired = _get_field(backend_deployment, "desired_replicas", 0)
    available = _get_field(backend_deployment, "available_replicas", 0)

    if desired > 0:
        replica_ratio = min(available / desired, 1.0)
        quality_score += replica_ratio * 0.4

    hpas = world_state.get("hpas", [])
    backend_hpa = next(
        (h for h in hpas if _get_field(h, "name") == "backend-hpa"),
        None,
    )
    hpa_ok = (
        backend_hpa is not None
        and _get_field(backend_hpa, "min_replicas", 0) >= 2
        and _get_field(backend_hpa, "max_replicas", 0) >= 6
        and _get_field(backend_hpa, "cpu_target_percent", 100) <= 70
    )
    if hpa_ok:
        quality_score += 0.2

    pods = world_state.get("pods", [])
    backend_pods = [
        p
        for p in pods
        if _get_field(p, "deployment") == "backend"
        and _get_field(p, "status") == "Running"
    ]
    total_backend_pods = [p for p in pods if _get_field(p, "deployment") == "backend"]

    if total_backend_pods:
        health_ratio = len(backend_pods) / len(total_backend_pods)
        quality_score += health_ratio * 0.4

        unstable = [
            p
            for p in total_backend_pods
            if _get_field(p, "status") != "Running" or _get_field(p, "restarts", 0) >= 5
        ]
        stability_ratio = 1.0 - (len(unstable) / len(total_backend_pods))
        quality_score += stability_ratio * 0.2

    # Strong step penalty: longer trajectories are penalized quadratically.
    if max_steps > 0:
        progress_ratio = min(max(step / max_steps, 0.0), 1.0)
        efficiency_factor = 1.0 - (progress_ratio * 0.2)
        score = quality_score * efficiency_factor
    else:
        score = quality_score

    return max(0.0001, min(score, 0.9999))
