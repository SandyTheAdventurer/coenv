"""
UnderutilizationCondition - Simulates over-provisioned cluster
"""

from typing import Dict, Any, Optional
from ..coenv_environment import World
from datetime import datetime
from ..models import ClusterEvent


class UnderutilizationCondition:
    """Injects low resource utilization for cost optimization task"""

    def __init__(self, world: World, config: Dict[str, Any]):
        self.world = world
        self.config = config

    def inject(
        self,
        target_deployment: Optional[str] = None,
        failure_rate: Optional[float] = None,
    ):
        """Set deployments to over-provisioned state (high replicas, low usage)"""
        deployments = self.world.cluster_state["deployments"]

        for dep in deployments:
            if dep["name"] in ["frontend", "backend"]:
                dep["desired_replicas"] = dep["desired_replicas"] * 2
                dep["available_replicas"] = dep["desired_replicas"]

        nodes = self.world.cluster_state["nodes"]
        for node in nodes:
            node["cpu_usage"] = float(self.world.rng.uniform(5, 15))
            node["mem_usage"] = float(self.world.rng.uniform(10, 25))
            node["last_updated"] = datetime.now().isoformat()

        self.world.inject_failure_condition("cluster", "underutilized", 1.0)

        event = ClusterEvent(
            event_id=f"event-cost-{int(self.world.rng.integers(1000, 10000))}",
            timestamp=datetime.now().isoformat(),
            type="Warning",
            reason="CostAlert",
            message="Cluster utilization below threshold. Consider downscaling for cost savings.",
            involved_object="cluster",
        )
        self.world.events.append(event)
