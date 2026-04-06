"""
Grader for Autoscaling Task
"""

from typing import Dict, Any


def grade(world_state: Dict[str, Any], step: int, max_steps: int) -> float:
    """Grade the autoscaling task"""
    score = 0.0
    
    # Check backend deployment status
    backend_deployment = next((d for d in world_state.get("deployments", []) if d.get("name") == "backend"), None)
    if not backend_deployment:
        return 0.0
    
    # Check if we have adequate replicas
    desired = backend_deployment.get("desired_replicas", 0)
    available = backend_deployment.get("available_replicas", 0)
    
    if desired > 0:
        replica_ratio = min(available / desired, 1.0)
        score += replica_ratio * 0.4  # 40% for proper scaling
    
    # Check backend pod health
    backend_pods = [p for p in world_state.get("pods", []) 
                   if p.get("deployment") == "backend" and p.get("status") == "Running"]
    total_backend_pods = [p for p in world_state.get("pods", []) 
                         if p.get("deployment") == "backend"]
    
    if total_backend_pods:
        health_ratio = len(backend_pods) / len(total_backend_pods)
        score += health_ratio * 0.4  # 40% for pod health
    
    # Efficiency bonus
    if max_steps > 0:
        efficiency = 1.0 - (step / max_steps)
        score += efficiency * 0.2  # 20% for efficiency
    
    return min(score, 1.0)