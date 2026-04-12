"""
Grader for Security Task
"""

from typing import Dict, Any


def _get_field(obj: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get field from dict or Pydantic model."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump().get(key, default)
    return obj.get(key, default)


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the security task"""
    quality_score = 0.0

    configmaps = world_state.get("configmaps", [])
    sensitive_keys = {"API_KEY", "DB_PASSWORD", "JWT_SECRET", "SECRET", "PASSWORD"}

    exposed_count = 0
    for cm in configmaps:
        data = _get_field(cm, "data", {})
        has_exposed = any(
            k.upper() in sensitive_keys or v in {"sk_live_", "p@ss", "secret", "超级"}
            for k, v in data.items()
        )
        if not has_exposed:
            exposed_count += 1

    secrets = world_state.get("secrets", [])
    has_secrets = len(secrets) > 0

    config_has_no_creds = exposed_count / len(configmaps) if configmaps else 1.0
    quality_score = (0.4 * config_has_no_creds) + (0.6 * (1.0 if has_secrets else 0.0))

    if max_steps > 0:
        progress_ratio = min(max(step / max_steps, 0.0), 1.0)
        efficiency_factor = 1.0 - (progress_ratio * 0.5)
        score = quality_score * efficiency_factor
    else:
        score = quality_score

    return max(0.0001, min(score, 0.9999))
