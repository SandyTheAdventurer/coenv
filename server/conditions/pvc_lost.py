"""
PVCLostCondition - Simulates PVC in Lost state
"""

from typing import Dict, Any, Optional
from ..coenv_environment import World
from datetime import datetime
from ..models import ClusterEvent


class PVCLostCondition:
    """Injects PVC failure for backup-recovery task"""

    def __init__(self, world: World, config: Dict[str, Any]):
        self.world = world
        self.config = config

    def inject(
        self,
        target_deployment: Optional[str] = None,
        failure_rate: Optional[float] = None,
    ):
        """Mark PVC as Lost and PV as Available (broken claim)"""
        pvcs = self.world.cluster_state.get("persistentvolumeclaims", [])
        pvs = self.world.cluster_state.get("persistentvolumeclaims", [])

        for pvc in pvcs:
            if pvc["name"] == "database-pvc":
                pvc["status"] = "Lost"
                pvc["volume_name"] = None
                pvc["last_updated"] = datetime.now().isoformat()

        for pv in self.world.cluster_state.get("persistentvolumes", []):
            if pv["name"] == "pv-database":
                pv["status"] = "Available"
                pv["claim_ref"] = None
                pv["last_updated"] = datetime.now().isoformat()

        self.world.inject_failure_condition("database-pvc", "pvc_lost", 1.0)

        event = ClusterEvent(
            event_id=f"event-pvc-{int(self.world.rng.integers(1000, 10000))}",
            timestamp=datetime.now().isoformat(),
            type="Error",
            reason="VolumeMisconfigured",
            message="PersistentVolumeClaim database-pvc is Lost. Volume mount failed.",
            involved_object="database-pvc",
        )
        self.world.events.append(event)
