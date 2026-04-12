"""
Grader for Backup Recovery Task
"""

from typing import Dict, Any


def _get_field(obj: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Get field from dict or Pydantic model."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump().get(key, default)
    return obj.get(key, default)


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the backup recovery task"""
    quality_score = 0.0

    pvcs = world_state.get("persistentvolumeclaims", [])
    database_pvc = next(
        (p for p in pvcs if _get_field(p, "name") == "database-pvc"), None
    )

    pvs = world_state.get("persistentvolumes", [])
    pv_database = next((p for p in pvs if _get_field(p, "name") == "pv-database"), None)

    if database_pvc and pv_database:
        pvc_bound = 1.0 if _get_field(database_pvc, "status") == "Bound" else 0.0
        pv_bound = 1.0 if _get_field(pv_database, "status") == "Bound" else 0.0

        pods = world_state.get("pods", [])
        db_pods = [p for p in pods if _get_field(p, "deployment") == "database"]
        db_running = len([p for p in db_pods if _get_field(p, "status") == "Running"])
        db_ready = db_running / len(db_pods) if db_pods else 0.0

        quality_score = (0.3 * pvc_bound) + (0.3 * pv_bound) + (0.4 * db_ready)

    if max_steps > 0:
        progress_ratio = min(max(step / max_steps, 0.0), 1.0)
        efficiency_factor = 1.0 - (progress_ratio * 0.2)
        score = quality_score * efficiency_factor
    else:
        score = quality_score

    return max(0.0001, min(score, 0.9999))
