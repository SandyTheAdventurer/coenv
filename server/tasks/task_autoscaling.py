"""
Autoscaling Task - Medium difficulty
Configure HPA to handle traffic spike
"""

from typing import Dict, Any
from ..COEnv_environment import World


class AutoscalingTask:
    """Autoscaling task implementation"""
    
    def __init__(self, world: World, config: Dict[str, Any]):
        self.world = world
        self.config = config
        self.task_id = "autoscaling"
        self.description = "Configure HPA to handle traffic spike"
        
    def reset(self):
        """Reset the task to initial state"""
        self.world.reset_to_healthy()
        
        backend_pods = [p for p in self.world.get_pods() if p.deployment == "backend"]
        for pod in backend_pods:
            patch = {
                "cpu_request": int(pod.cpu_request * 3) if pod.cpu_request else 750,
                "mem_request": int(pod.mem_request * 3) if pod.mem_request else 384
            }
            self.world.apply_patch("pod", pod.name, patch)
        
        self.objective = "Backend service is overloaded due to traffic spike. Configure HPA to automatically scale the backend deployment based on CPU utilization."
        
    def is_complete(self) -> bool:
        """Check if the task is complete"""
        backend_deployment = next((d for d in self.world.get_deployments() if d.name == "backend"), None)
        if not backend_deployment:
            return False
            
        backend_pods = [p for p in self.world.get_pods() 
                       if p.deployment == "backend" and p.status == "Running"]
        return len(backend_pods) >= 2
    
    def get_observation(self) -> Dict[str, Any]:
        """Get current observation for the task"""
        observation = self.world.get_full_state()
        observation["objective"] = self.objective
        return observation
