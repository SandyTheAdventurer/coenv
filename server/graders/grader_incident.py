"""
Grader for Incident Task
"""

from typing import Dict, Any


def _get_field(obj: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get field from dict or Pydantic model."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump().get(key, default)
    return obj.get(key, default)


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the incident task"""
    quality_score = 0.0

    key_services = ["auth-service", "api-gateway", "frontend"]
    healthy_services = 0

    deployments = world_state.get("deployments", [])
    for service_name in key_services:
        deployment = next(
            (d for d in deployments if _get_field(d, "name") == service_name),
            None,
        )
        if deployment:
            desired = _get_field(deployment, "desired_replicas", 0)
            available = _get_field(deployment, "available_replicas", 0)

            if desired > 0:
                if available / desired >= 0.8:
                    healthy_services += 1

    if key_services:
        service_health_score = healthy_services / len(key_services)
        quality_score += service_health_score * 0.6

    pods = world_state.get("pods", [])
    key_service_pods = [p for p in pods if _get_field(p, "deployment") in key_services]
    crashloop_pods = [
        p for p in key_service_pods if _get_field(p, "status") == "CrashLoopBackOff"
    ]

    if key_service_pods:
        crashloop_ratio = len(crashloop_pods) / len(key_service_pods)
        # Penalize for crashlooping pods (inverse relationship)
        health_bonus = (1.0 - crashloop_ratio) * 0.3  # 30% for no crashloops
        quality_score += health_bonus

    # Strong step penalty: longer trajectories are penalized quadratically.
    if max_steps > 0:
        progress_ratio = min(max(step / max_steps, 0.0), 1.0)
        efficiency_factor = 1.0 - (progress_ratio * 0.5)
        score = quality_score * efficiency_factor
    else:
        score = quality_score

    return max(0.0001, min(score, 0.9999))
