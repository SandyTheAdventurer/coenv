"""
OOMKillCondition - Simulates memory-limit failures causing repeated restarts
"""

from typing import Dict, List, Any, Optional
from ..COEnv_environment import World
import random


class OOMKillCondition:
    """Injects OOMKill failures into pods"""
    
    def __init__(self, world: World, config: Dict[str, Any]):
        self.world = world
        self.config = config
        
    def inject(self, target_deployment: Optional[str] = None, failure_rate: Optional[float] = None):
        """
        Inject OOMKill failures into pods
        
        Args:
            target_deployment: Specific deployment to target (None for random)
            failure_rate: Probability of each pod failing (0.0-1.0)
        """
        if failure_rate is None:
            failure_rate = self.config.get("oom_kill_failure_rate", 0.6)
        else:
            # Ensure failure_rate is a float
            failure_rate = float(failure_rate)
            
        deployments = self.world.get_deployments()
        
        if target_deployment is not None:
            target_deps = [d for d in deployments if d.name == target_deployment]
        else:
            # Target a random deployment
            target_deps = [random.choice(deployments)] if deployments else []
            
        for deployment in target_deps:
            # Get pods for this deployment
            pods = [p for p in self.world.get_pods() if p.deployment == deployment.name]
            
            for pod in pods:
                if failure_rate is not None and random.random() < failure_rate:
                    # Simulate OOMKill by setting high memory usage and restart count
                    patch = {
                        "status": "Running",  # OOMKill pods often show as Running but crash
                        "restarts": random.randint(10, 30)  # High restart count from OOM
                    }
                    self.world.apply_patch("pod", pod.name, patch)
                    
                    # Also reduce the pod's memory limit to simulate the condition that caused OOM
                    mem_patch = {
                        "mem_limit": max(64, pod.mem_limit // 2) if pod.mem_limit else 128
                    }
                    self.world.apply_patch("pod", pod.name, mem_patch)
                    
                    # Add event
                    self._add_oom_event(pod.name)
    
    def _add_oom_event(self, pod_name: str):
        """Add an OOMKill event"""
        from .models import ClusterEvent
        from datetime import datetime
        
        event = ClusterEvent(
            event_id=f"event-oom-{random.randint(1000, 9999)}",
            timestamp=datetime.now().isoformat(),
            type="Warning",
            reason="OOMKilling",
            message=f"Container {pod_name} exceeded memory limit",
            involved_object=pod_name
        )
        self.world.events.append(event)