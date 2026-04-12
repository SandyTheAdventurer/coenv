"""
Grader for Pod Recovery Task
"""

from typing import Dict, Any


def _get_field(obj: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get field from dict or Pydantic model."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump().get(key, default)
    return obj.get(key, default)


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the pod recovery task"""
    quality_score = 0.0

    pods = world_state.get("pods", [])

    frontend_pods = [
        p
        for p in pods
        if _get_field(p, "deployment") == "frontend"
        and _get_field(p, "status") == "Running"
    ]
    total_frontend_pods = [p for p in pods if _get_field(p, "deployment") == "frontend"]

    if total_frontend_pods:
        running_ratio = len(frontend_pods) / len(total_frontend_pods)
        quality_score += running_ratio * 0.5

    if total_frontend_pods and len(frontend_pods) == len(total_frontend_pods):
        quality_score += 0.4

    # Strong step penalty: longer trajectories are penalized quadratically.
    if max_steps > 0:
        progress_ratio = min(max(step / max_steps, 0.0), 1.0)
        efficiency_factor = 1.0 - (progress_ratio * 0.5)
        score = quality_score * efficiency_factor
    else:
        score = quality_score

    return max(0.0001, min(score, 0.9999))
