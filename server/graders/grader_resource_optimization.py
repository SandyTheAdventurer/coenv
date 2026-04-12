"""
Grader for Resource Optimization Task
"""

from typing import Dict, Any


def _get_field(obj: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get field from dict or Pydantic model."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump().get(key, default)
    return obj.get(key, default)


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the resource optimization task"""
    quality_score = 0.0

    nodes = world_state.get("nodes", [])
    if nodes:
        total_cpu = sum(_get_field(n, "cpu_usage", 0) for n in nodes) / len(nodes)
        total_mem = sum(_get_field(n, "mem_usage", 0) for n in nodes) / len(nodes)
    else:
        total_cpu = 100
        total_mem = 100

    too_low = total_cpu < 20 or total_mem < 30
    deployments = world_state.get("deployments", [])
    total_replicas = sum(_get_field(d, "available_replicas", 0) for d in deployments)
    ideal_replicas = 6

    if total_replicas <= ideal_replicas and not too_low:
        quality_score = 1.0
    elif too_low:
        savings_potential = (
            1.0 - (ideal_replicas / total_replicas) if total_replicas > 0 else 0.0
        )
        quality_score = max(0.0, min(savings_potential, 0.7))
    else:
        quality_score = 0.5

    if max_steps > 0:
        progress_ratio = min(max(step / max_steps, 0.0), 1.0)
        efficiency_factor = 1.0 - (progress_ratio * 0.2)
        score = quality_score * efficiency_factor
    else:
        score = quality_score

    return max(0.0001, min(score, 0.9999))
