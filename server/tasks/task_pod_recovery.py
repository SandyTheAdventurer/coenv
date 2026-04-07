"""
Pod Recovery Task - Easy difficulty
Fix crash-looping pods by identifying and patching bad configuration
"""

from typing import Dict, Any
from ..coenv_environment import World
from ..conditions.crash_loop import CrashLoopCondition


class PodRecoveryTask:
    """Pod recovery task implementation"""
    
    def __init__(self, world: World, config: Dict[str, Any]):
        self.world = world
        self.config = config
        self.task_id = "pod_recovery"
        self.description = "Fix crash-looping pods by identifying and patching bad configuration"
        
    def reset(self):
        """Reset the task to initial state"""
        self.world.reset_to_healthy()
        
        crash_loop_condition = CrashLoopCondition(self.world, self.config)
        crash_loop_condition.inject(target_deployment="frontend", failure_rate=0.8)
        
        self.objective = "All frontend pods should be running. Investigate the CrashLoopBackOff pods and fix the configuration issue."
        
    def is_complete(self) -> bool:
        """Check if the task is complete"""
        frontend_pods = [p for p in self.world.get_pods() 
                        if p.deployment == "frontend" and p.status == "Running"]
        total_frontend_pods = [p for p in self.world.get_pods() 
                              if p.deployment == "frontend"]
        
        if not total_frontend_pods:
            return False
            
        return len(frontend_pods) == len(total_frontend_pods)
    
    def get_observation(self) -> Dict[str, Any]:
        """Get current observation for the task"""
        observation = self.world.get_full_state()
        observation["objective"] = self.objective
        return observation
