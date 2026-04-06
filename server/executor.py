"""COEnv Executor - Action execution bridge"""

from typing import Dict, Any, Optional


class ExecutionResult:
    """Result of action execution"""
    
    def __init__(self, observation, reward: float, done: bool, info: Dict[str, Any]):
        self.observation = observation
        self.reward = reward
        self.done = done
        self.info = info


class Executor:
    """Maps validated actions to world method calls"""
    
    def __init__(self, world, grader):
        self.world = world
        self.grader = grader
    
    def execute(self, action: Dict[str, Any], task_id: str, max_steps: int) -> ExecutionResult:
        """
        Execute an action and return the result
        
        Args:
            action: The action to execute
            task_id: Current task ID for grading
            max_steps: Maximum steps for the episode
            
        Returns:
            ExecutionResult with observation, reward, done, and info
        """
        action_type = action.get("action_type", "")
        info = {}
        reward = 0.0
        done = False
        
        try:
            if action_type == "scale":
                deployment = action.get("deployment", "")
                replicas = action.get("replicas", 1)
                self.world.scale(deployment, replicas)
                info["scaled"] = deployment
                info["replicas"] = replicas
                
            elif action_type == "delete_pod":
                pod_name = action.get("pod_name", "")
                self.world.delete_pod(pod_name)
                info["deleted"] = pod_name
                
            elif action_type == "patch":
                resource_type = action.get("resource_type", "")
                name = action.get("name", "")
                patch = action.get("patch", {})
                self.world.apply_patch(resource_type, name, patch)
                info["patched"] = f"{resource_type}/{name}"
                
            elif action_type == "rollout_restart":
                deployment = action.get("deployment", "")
                self.world.rollout_restart(deployment)
                info["restarted"] = deployment
                
            elif action_type == "drain_node":
                node_name = action.get("node_name", "")
                self.world.apply_patch("node", node_name, {"status": "SchedulingDisabled"})
                info["drained"] = node_name
                
            elif action_type == "set_hpa":
                deployment = action.get("deployment", "")
                min_replicas = action.get("min_replicas", 1)
                max_replicas = action.get("max_replicas", 10)
                cpu_target = action.get("cpu_target_percent", 80)
                hpa_name = f"{deployment}-hpa"
                self.world.apply_patch("hpa", hpa_name, {
                    "min_replicas": min_replicas,
                    "max_replicas": max_replicas,
                    "cpu_target_percent": cpu_target
                })
                info["hpa_set"] = deployment
                
            elif action_type == "describe":
                # Investigation action - no state change
                resource_type = action.get("resource_type", "")
                name = action.get("name", "")
                info["described"] = f"{resource_type}/{name}"
                
            else:
                info["error"] = f"Unknown action type: {action_type}"
                reward = -0.1
                
        except Exception as e:
            info["error"] = str(e)
            reward = -0.1
        
        # Always advance time after an action
        self.world.tick()
        
        # Calculate reward
        world_state = self.world.get_full_state()
        reward = self.grader.grade(world_state, self.world.step_count, max_steps)
        
        # Check if done
        if self.world.step_count >= max_steps:
            done = True
        
        # Check task completion
        if self._check_task_complete(task_id):
            done = True
        
        observation = self.world.get_observation()
        
        return ExecutionResult(
            observation=observation,
            reward=reward,
            done=done,
            info=info
        )
    
    def _check_task_complete(self, task_id: str) -> bool:
        """Check if task is complete"""
        pods = self.world.get_pods()
        
        if task_id == "pod_recovery":
            frontend_pods = [p for p in pods if p.deployment == "frontend"]
            running = [p for p in frontend_pods if p.status == "Running"]
            return len(frontend_pods) > 0 and len(running) == len(frontend_pods)
        
        elif task_id == "autoscaling":
            backend_pods = [p for p in pods if p.deployment == "backend"]
            running = [p for p in backend_pods if p.status == "Running"]
            return len(backend_pods) >= 2 and len(running) >= 2
        
        elif task_id == "incident":
            key_services = ["auth-service", "api-gateway", "frontend"]
            for svc in key_services:
                svc_pods = [p for p in pods if p.deployment == svc]
                running = [p for p in svc_pods if p.status == "Running"]
                if svc_pods and len(running) < len(svc_pods) * 0.8:
                    return False
            return True
        
        return False
