"""COEnv Validator - Action validation"""

from typing import Dict, Any, Optional, Tuple


class Validator:
    """Validates actions before execution"""
    
    def __init__(self, world):
        self.world = world
    
    def validate(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate an action before execution
        
        Returns:
            (is_valid, error_message)
        """
        action_type = action.get("action_type", "")
        
        if action_type == "scale":
            return self._validate_scale(action)
        elif action_type == "delete_pod":
            return self._validate_delete_pod(action)
        elif action_type == "patch":
            return self._validate_patch(action)
        elif action_type == "rollout_restart":
            return self._validate_rollout_restart(action)
        elif action_type == "set_hpa":
            return self._validate_set_hpa(action)
        elif action_type == "drain_node":
            return self._validate_drain_node(action)
        elif action_type == "describe":
            return self._validate_describe(action)
        else:
            return False, f"Unknown action type: {action_type}"
    
    def _validate_scale(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        deployment = action.get("deployment", "")
        replicas = action.get("replicas", 0)
        
        if not deployment:
            return False, "Deployment name is required"
        
        if replicas < 0 or replicas > 100:
            return False, "Replicas must be between 0 and 100"
        
        # Check if deployment exists
        deployments = self.world.get_deployments()
        if not any(d.name == deployment for d in deployments):
            return False, f"Deployment '{deployment}' does not exist"
        
        return True, None
    
    def _validate_delete_pod(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        pod_name = action.get("pod_name", "")
        
        if not pod_name:
            return False, "Pod name is required"
        
        # Check if pod exists
        pods = self.world.get_pods()
        if not any(p.name == pod_name for p in pods):
            return False, f"Pod '{pod_name}' does not exist"
        
        return True, None
    
    def _validate_patch(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        resource_type = action.get("resource_type", "")
        name = action.get("name", "")
        
        if not resource_type:
            return False, "Resource type is required"
        
        if not name:
            return False, "Resource name is required"
        
        # Check if resource exists
        if resource_type == "deployment":
            deployments = self.world.get_deployments()
            if not any(d.name == name for d in deployments):
                return False, f"Deployment '{name}' does not exist"
        elif resource_type == "pod":
            pods = self.world.get_pods()
            if not any(p.name == name for p in pods):
                return False, f"Pod '{name}' does not exist"
        elif resource_type == "node":
            nodes = self.world.get_nodes()
            if not any(n.name == name for n in nodes):
                return False, f"Node '{name}' does not exist"
        elif resource_type == "service":
            services = self.world.get_services()
            if not any(s.name == name for s in services):
                return False, f"Service '{name}' does not exist"
        elif resource_type == "configmap":
            configmaps = self.world.get_configmaps()
            if not any(cm.name == name for cm in configmaps):
                return False, f"ConfigMap '{name}' does not exist"
        
        return True, None
    
    def _validate_rollout_restart(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        deployment = action.get("deployment", "")
        
        if not deployment:
            return False, "Deployment name is required"
        
        # Check if deployment exists
        deployments = self.world.get_deployments()
        if not any(d.name == deployment for d in deployments):
            return False, f"Deployment '{deployment}' does not exist"
        
        return True, None
    
    def _validate_set_hpa(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        deployment = action.get("deployment", "")
        min_replicas = action.get("min_replicas", 0)
        max_replicas = action.get("max_replicas", 0)
        
        if not deployment:
            return False, "Deployment name is required"
        
        if min_replicas < 1 or min_replicas > 50:
            return False, "Min replicas must be between 1 and 50"
        
        if max_replicas < 1 or max_replicas > 100:
            return False, "Max replicas must be between 1 and 100"
        
        if min_replicas > max_replicas:
            return False, "Min replicas cannot be greater than max replicas"
        
        # Check if deployment exists
        deployments = self.world.get_deployments()
        if not any(d.name == deployment for d in deployments):
            return False, f"Deployment '{deployment}' does not exist"
        
        return True, None
    
    def _validate_drain_node(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        node_name = action.get("node_name", "")
        
        if not node_name:
            return False, "Node name is required"
        
        # Check if node exists
        nodes = self.world.get_nodes()
        if not any(n.name == node_name for n in nodes):
            return False, f"Node '{node_name}' does not exist"
        
        # Check if node is already drained/scheduling disabled
        node = next((n for n in nodes if n.name == node_name), None)
        if node and node.status == "SchedulingDisabled":
            return False, f"Node '{node_name}' is already drained"
        
        return True, None
    
    def _validate_describe(self, action: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        resource_type = action.get("resource_type", "")
        name = action.get("name", "")
        
        if not resource_type:
            return False, "Resource type is required"
        
        if not name:
            return False, "Resource name is required"
        
        return True, None
