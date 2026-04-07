"""
Incident Task - Hard difficulty
Handle multi-service cascading incident
"""

from typing import Dict, Any
from ..coenv_environment import World
from ..conditions.cascade_failure import CascadeFailureCondition


class IncidentTask:
    """Incident task implementation"""
    
    def __init__(self, world: World, config: Dict[str, Any]):
        self.world = world
        self.config = config
        self.task_id = "incident"
        self.description = "Handle multi-service cascading incident"
        
    def reset(self):
        """Reset the task to initial state"""
        self.world.reset_to_healthy()
        
        cascade_condition = CascadeFailureCondition(self.world, self.config)
        cascade_condition.inject(root_cause_service="auth-service", failure_probability=0.6)
        
        self.objective = "Auth-service OOMKill has caused cascading failures. Identify the root cause, fix memory limits, restart workloads, and verify downstream recovery."
        
    def is_complete(self) -> bool:
        """Check if the task is complete"""
        key_services = ["auth-service", "api-gateway", "frontend"]
        healthy_services = 0
        
        for service_name in key_services:
            deployment = next((d for d in self.world.get_deployments() if d.name == service_name), None)
            if deployment:
                running_pods = [p for p in self.world.get_pods() 
                              if p.deployment == service_name and p.status == "Running"]
                if len(running_pods) >= deployment.desired_replicas * 0.8:
                    healthy_services += 1
        
        return healthy_services >= len(key_services) * 0.67
    
    def get_observation(self) -> Dict[str, Any]:
        """Get current observation for the task"""
        observation = self.world.get_full_state()
        observation["objective"] = self.objective
        return observation
