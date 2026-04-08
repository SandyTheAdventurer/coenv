"""
NodeFailureCondition - Simulates node outages and scheduling disruption
"""

from typing import Dict, Any, Optional
from ..coenv_environment import World


class NodeFailureCondition:
    """Injects node failures into the cluster"""

    def __init__(self, world: World, config: Dict[str, Any]):
        self.world = world
        self.config = config

    def inject(
        self, target_node: Optional[str] = None, failure_rate: Optional[float] = None
    ):
        """
        Inject node failures

        Args:
            target_node: Specific node to target (None for random)
            failure_rate: Probability of node failing (0.0-1.0)
        """
        if failure_rate is None:
            failure_rate = self.config.get("node_failure_rate", 0.3)
        else:
            failure_rate = float(failure_rate)

        nodes = self.world.get_nodes()

        if target_node:
            target_nodes = [n for n in nodes if n.name == target_node]
        else:
            target_nodes = [
                n
                for n in nodes
                if failure_rate is not None
                and float(self.world.rng.random()) < failure_rate
            ]

        for node in target_nodes:
            patch = {"status": "NotReady", "cpu_usage": 0.0, "mem_usage": 0.0}
            self.world.apply_patch("node", node.name, patch)

            pods_on_node = [p for p in self.world.get_pods() if p.node == node.name]
            for pod in pods_on_node:
                patch = {"node": None, "status": "Pending"}
                self.world.apply_patch("pod", pod.name, patch)

            self._add_node_failure_event(node.name)

    def _add_node_failure_event(self, node_name: str):
        """Add a node failure event"""
        from ..models import ClusterEvent
        from datetime import datetime

        event = ClusterEvent(
            event_id=f"event-nodefail-{int(self.world.rng.integers(1000, 10000))}",
            timestamp=datetime.now().isoformat(),
            type="Warning",
            reason="NodeNotReady",
            message=f"Node {node_name} status is now: NodeNotReady",
            involved_object=node_name,
        )
        self.world.events.append(event)
