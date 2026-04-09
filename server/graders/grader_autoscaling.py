"""
Grader for Autoscaling Task
"""

from typing import Dict, Any


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the autoscaling task"""
    quality_score = 0.0

    # Check backend deployment status
    backend_deployment = next(
        (d for d in world_state.get("deployments", []) if d.get("name") == "backend"),
        None,
    )
    if not backend_deployment:
        return 0.0001

    # Check if we have adequate replicas
    desired = backend_deployment.get("desired_replicas", 0)
    available = backend_deployment.get("available_replicas", 0)

    if desired > 0:
        replica_ratio = min(available / desired, 1.0)
        quality_score += replica_ratio * 0.4  # 40% for proper scaling

    # Check backend pod health
    backend_pods = [
        p
        for p in world_state.get("pods", [])
        if p.get("deployment") == "backend" and p.get("status") == "Running"
    ]
    total_backend_pods = [
        p for p in world_state.get("pods", []) if p.get("deployment") == "backend"
    ]

    if total_backend_pods:
        health_ratio = len(backend_pods) / len(total_backend_pods)
        quality_score += health_ratio * 0.4  # 40% for pod health

    # Strong step penalty: longer trajectories are penalized quadratically.
    if max_steps > 0:
        progress_ratio = min(max(step / max_steps, 0.0), 1.0)
        efficiency_factor = 1.0 - (progress_ratio * 0.5)
        score = quality_score * efficiency_factor
    else:
        score = quality_score

    return max(0.0001, min(score, 0.9999))
