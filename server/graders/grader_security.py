"""
Grader for Security Task

Action-based scoring: rewards the agent for taking correct actions:
1. Remove credentials from ConfigMaps (patch)
2. Create Secrets with the credentials

Uses injected_failures to track which services still have exposed credentials.
"""

from typing import Dict, Any


def _get_field(obj: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get field from dict or Pydantic model."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump().get(key, default)
    return obj.get(key, default)


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the security task based on actions taken."""
    injected_failures = world_state.get("injected_failures", {})

    exposed_services = {
        svc
        for svc, info in injected_failures.items()
        if info.get("failure_type") == "security_exposed"
    }

    sensitive_keys = {"API_KEY", "DB_PASSWORD", "JWT_SECRET", "SECRET", "PASSWORD"}
    sensitive_values = {"sk_live_", "p@ss", "secret", "超级"}

    configmaps = world_state.get("configmaps", [])
    still_exposed = 0
    for cm in configmaps:
        data = _get_field(cm, "data", {})
        for key, value in data.items():
            if key.upper() in sensitive_keys or any(
                v in str(value) for v in sensitive_values
            ):
                still_exposed += 1
                break

    total_configmaps = len(configmaps) if configmaps else 1
    cleanup_ratio = 1.0 - (still_exposed / total_configmaps)

    secrets = world_state.get("secrets", [])
    created_secrets = len(secrets)

    action_score = (cleanup_ratio * 0.7) + (min(created_secrets / 2, 1.0) * 0.3)

    if max_steps > 0:
        progress_ratio = min(max(step / max_steps, 0.0), 1.0)
        efficiency_factor = 1.0 - (progress_ratio * 0.2)
        score = action_score * efficiency_factor
    else:
        score = action_score

    return max(0.0001, min(score, 0.9999))
