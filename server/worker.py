"""COEnv Worker - Episode loop manager"""

from typing import Dict, Any, Optional, List


class EpisodeResult:
    """Result of a single episode"""
    
    def __init__(self, rewards: List[float], steps: int, success: bool, info: Dict[str, Any]):
        self.rewards = rewards
        self.steps = steps
        self.success = success
        self.info = info


class Worker:
    """Manages the full lifecycle of a single episode"""
    
    def __init__(self, world, executor, validator):
        self.world = world
        self.executor = executor
        self.validator = validator
    
    def run_episode(self, task_id: str, task_objective: str, max_steps: int, 
                    get_action_fn=None) -> EpisodeResult:
        """
        Run a single episode
        
        Args:
            task_id: Task ID to run
            task_objective: Objective string for the task
            max_steps: Maximum steps for the episode
            get_action_fn: Function to get action from agent (if None, uses random)
            
        Returns:
            EpisodeResult with rewards, steps, success, and info
        """
        import random
        
        # Reset world with task condition
        observation = self.world.reset(task_objective)
        rewards = []
        steps = 0
        info = {}
        
        for step in range(1, max_steps + 1):
            steps = step
            
            # Get action from agent (or random for now)
            if get_action_fn:
                action = get_action_fn(observation)
            else:
                # Random action for testing
                action = self._random_action()
            
            # Validate action
            is_valid, error_msg = self.validator.validate(action)
            if not is_valid:
                info["error"] = error_msg
                # Still execute but with penalty
                result = self.executor.execute(action, task_id, max_steps)
                result.reward = -0.1  # Penalty for invalid action
            else:
                # Execute valid action
                result = self.executor.execute(action, task_id, max_steps)
            
            rewards.append(result.reward)
            
            if result.done:
                info["success"] = True
                info["final_reward"] = result.reward
                break
        else:
            info["success"] = False
            info["final_reward"] = rewards[-1] if rewards else 0.0
        
        return EpisodeResult(
            rewards=rewards,
            steps=steps,
            success=info.get("success", False),
            info=info
        )
    
    def _random_action(self) -> Dict[str, Any]:
        """Generate a random action for testing"""
        import random
        
        action_types = [
            {"action_type": "describe", "resource_type": "deployment", "name": "frontend"},
            {"action_type": "describe", "resource_type": "pod", "name": "frontend-abc123"},
            {"action_type": "scale", "deployment": "frontend", "replicas": random.randint(1, 5)},
            {"action_type": "scale", "deployment": "backend", "replicas": random.randint(1, 5)},
            {"action_type": "delete_pod", "pod_name": "frontend-xyz789"},
            {"action_type": "patch", "resource_type": "deployment", "name": "frontend", 
             "patch": {"desired_replicas": random.randint(1, 5)}},
            {"action_type": "rollout_restart", "deployment": "frontend"},
            {"action_type": "set_hpa", "deployment": "backend", 
             "min_replicas": 1, "max_replicas": 10, "cpu_target_percent": 80},
        ]
        
        return random.choice(action_types)
