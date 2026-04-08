"""
Grader for Pod Recovery Task
"""

from typing import Dict, Any


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the pod recovery task"""
    quality_score = 0.0

    # Count running frontend pods
    frontend_pods = [
        p
        for p in world_state.get("pods", [])
        if p.get("deployment") == "frontend" and p.get("status") == "Running"
    ]
    total_frontend_pods = [
        p for p in world_state.get("pods", []) if p.get("deployment") == "frontend"
    ]

    if total_frontend_pods:
        running_ratio = len(frontend_pods) / len(total_frontend_pods)
        quality_score += running_ratio * 0.5

    # Bonus for all pods running
    if total_frontend_pods and len(frontend_pods) == len(total_frontend_pods):
        quality_score += 0.4

    # Strong step penalty: longer trajectories are penalized quadratically.
    if max_steps > 0:
        progress_ratio = min(max(step / max_steps, 0.0), 1.0)
        efficiency_factor = 1.0 - (progress_ratio * 0.5)
        score = quality_score * efficiency_factor
    else:
        score = quality_score

    return min(score, 1.0)
