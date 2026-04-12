"""
Grader for Incident Task

Action-based scoring: rewards the agent for taking correct actions (restarting
failed services) rather than outcome (services being healthy). This is more
logically correct for RL - the agent controls its actions, not recovery time.
"""

from typing import Dict, Any, List, Set


def _get_field(obj: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get field from dict or Pydantic model."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump().get(key, default)
    return obj.get(key, default)


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the incident task based on actions taken."""
    key_services = ["auth-service", "api-gateway", "frontend"]

    injected_failures = world_state.get("injected_failures", {})
    failed_services = set(injected_failures.keys())

    restored_services = set()
    for service_name in key_services:
        if service_name not in failed_services:
            restored_services.add(service_name)

    if failed_services:
        restoration_ratio = len(restored_services) / len(key_services)
    else:
        restoration_ratio = 1.0

    pods = world_state.get("pods", [])
    key_service_pods = [p for p in pods if _get_field(p, "deployment") in key_services]

    crashloop_pods = [
        p for p in key_service_pods if _get_field(p, "status") == "CrashLoopBackOff"
    ]

    if key_service_pods:
        crashloop_ratio = len(crashloop_pods) / len(key_service_pods)
        stability_bonus = (1.0 - crashloop_ratio) * 0.3
    else:
        stability_bonus = 0.0

    quality_score = (restoration_ratio * 0.7) + stability_bonus

    if max_steps > 0:
        progress_ratio = min(max(step / max_steps, 0.0), 1.0)
        efficiency_factor = 1.0 - (progress_ratio * 0.2)
        score = quality_score * efficiency_factor
    else:
        score = quality_score

    return max(0.0001, min(score, 0.9999))
