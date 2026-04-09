"""
Grader for Incident Task
"""

from typing import Dict, Any


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the incident task"""
    quality_score = 0.0

    # Key services that should be healthy after incident resolution
    key_services = ["auth-service", "api-gateway", "frontend"]
    healthy_services = 0

    for service_name in key_services:
        # Check if deployment exists and has running pods
        deployment = next(
            (
                d
                for d in world_state.get("deployments", [])
                if d.get("name") == service_name
            ),
            None,
        )
        if deployment:
            desired = deployment.get("desired_replicas", 0)
            available = deployment.get("available_replicas", 0)

            if desired > 0:
                # Consider service healthy if at least 80% of desired replicas are available
                if available / desired >= 0.8:
                    healthy_services += 1

    # Score based on proportion of healthy services
    if key_services:
        service_health_score = healthy_services / len(key_services)
        quality_score += service_health_score * 0.6  # 60% for service health

    # Check for absence of crashlooping pods in key services
    key_service_pods = [
        p for p in world_state.get("pods", []) if p.get("deployment") in key_services
    ]
    crashloop_pods = [
        p for p in key_service_pods if p.get("status") == "CrashLoopBackOff"
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
