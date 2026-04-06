"""
CrashLoopCondition - Simulates pods stuck in CrashLoopBackOff
"""

from typing import Dict, List, Any, Optional
from ..COEnv_environment import World


class CrashLoopCondition:
    """Injects CrashLoopBackOff failures into pods"""
    
    def __init__(self, world: World, config: Dict[str, Any]):
        self.world = world
        self.config = config
        
    def inject(self, target_deployment: Optional[str] = None, failure_rate: Optional[float] = None):
        """
        Inject crash loop failures into pods
        
        Args:
            target_deployment: Specific deployment to target (None for random)
            failure_rate: Probability of each pod failing (0.0-1.0)
        """
        if failure_rate is None:
            failure_rate = self.config.get("crash_loop_failure_rate", 0.8)
        else:
            failure_rate = float(failure_rate)
            
        deployments = self.world.get_deployments()
        
        if target_deployment is not None:
            target_deps = [d for d in deployments if d.name == target_deployment]
        else:
            target_deps = [self.world.rng.choice(deployments)] if deployments else []
            
        for deployment in target_deps:
            pods = [p for p in self.world.get_pods() if p.deployment == deployment.name]
            
            for pod in pods:
                if failure_rate is not None and float(self.world.rng.random()) < failure_rate:
                    patch = {
                        "status": "CrashLoopBackOff",
                        "restarts": int(self.world.rng.integers(5, 21))
                    }
                    self.world.apply_patch("pod", pod.name, patch)
                    self._add_crashloop_event(pod.name)
    
    def _add_crashloop_event(self, pod_name: str):
        """Add a crashloop event"""
        from ..models import ClusterEvent
        from datetime import datetime
        
        event = ClusterEvent(
            event_id=f"event-crashloop-{int(self.world.rng.integers(1000, 10000))}",
            timestamp=datetime.now().isoformat(),
            type="Warning",
            reason="BackOff",
            message=f"Back-off restarting failed container pod/{pod_name}",
            involved_object=pod_name
        )
        self.world.events.append(event)