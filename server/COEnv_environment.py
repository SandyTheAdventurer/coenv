"""
COEnv Environment - Cluster Simulator
In-memory dict that holds cluster state: nodes, pods, deployments, services.
Has methods like get_pods(), apply_patch(), tick() to advance time.
This is the brain of the whole project.
"""

from typing import Dict, List, Any, Optional, Literal
from datetime import datetime
import random
import time

from .models import (
    NodeStatus, PodStatus, DeploymentStatus, ServiceStatus, 
    ClusterEvent, ClusterObservation, KubeAction, RewardSignal,
    ConfigMapStatus, HPAStatus
)


class World:
    """In-memory Kubernetes cluster simulator"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.cluster_state = self._initialize_healthy_cluster()
        self.step_count = 0
        self.events = []
        self._event_counter = 0
        
    def _initialize_healthy_cluster(self) -> Dict[str, List[Dict]]:
        """Initialize a healthy cluster state based on config"""
        nodes = []
        for i in range(self.config.get("num_nodes", 3)):
            nodes.append({
                "name": f"node-{i+1}",
                "status": "Ready",
                "cpu_capacity": self.config.get("node_cpu_capacity", 4),
                "mem_capacity": self.config.get("node_mem_capacity", 8192),
                "cpu_usage": 0.0,
                "mem_usage": 0.0,
                "last_updated": datetime.now().isoformat()
            })
        
        pods = []
        deployments = []
        services = []
        configmaps = []
        hpas = []
        
        # Create some default deployments and their pods
        default_deployments = [
            {"name": "frontend", "image": "nginx:1.21", "replicas": 3},
            {"name": "backend", "image": "python:3.9", "replicas": 2},
            {"name": "database", "image": "postgres:13", "replicas": 1},
            {"name": "auth-service", "image": "auth:latest", "replicas": 2},
            {"name": "api-gateway", "image": "nginx:alpine", "replicas": 2}
        ]
        
        for dep in default_deployments:
            deployments.append({
                "name": dep["name"],
                "desired_replicas": dep["replicas"],
                "available_replicas": dep["replicas"],
                "image": dep["image"],
                "last_updated": datetime.now().isoformat()
            })
            
            # Create pods for this deployment
            for j in range(dep["replicas"]):
                pod_name = f"{dep['name']}-{random.randint(1000, 9999)}-{''.join([chr(random.randint(97, 122)) for _ in range(5)])}"
                pods.append({
                    "name": pod_name,
                    "status": "Running",
                    "node": nodes[j % len(nodes)]["name"] if nodes else None,
                    "restarts": 0,
                    "cpu_request": self.config.get("pod_cpu_request", 500),
                    "mem_request": self.config.get("pod_mem_request", 256),
                    "cpu_limit": self.config.get("pod_cpu_limit", 1000),
                    "mem_limit": self.config.get("pod_mem_limit", 512),
                    "deployment": dep["name"],
                    "last_updated": datetime.now().isoformat()
                })
        
        # Create some default services
        default_services = [
            {"name": "frontend-service", "type": "ClusterIP", "ports": [{"port": 80, "targetPort": 80}]},
            {"name": "backend-service", "type": "ClusterIP", "ports": [{"port": 8080, "targetPort": 8080}]},
            {"name": "database-service", "type": "ClusterIP", "ports": [{"port": 5432, "targetPort": 5432}]},
            {"name": "auth-service-service", "type": "ClusterIP", "ports": [{"port": 8000, "targetPort": 8000}]}
        ]
        
        for svc in default_services:
            services.append({
                "name": svc["name"],
                "type": svc["type"],
                "ports": svc["ports"],
                "selector": {"app": svc["name"].replace("-service", "")},
                "cluster_ip": f"10.96.{len(services)+1}.{len(services)+1}",
                "last_updated": datetime.now().isoformat()
            })
        
        # Create some default configmaps
        default_configmaps = [
            {"name": "frontend-config", "data": {"DB_HOST": "db.prod.internal", "DB_PORT": "5432"}},
            {"name": "backend-config", "data": {"LOG_LEVEL": "info", "CACHE_SIZE": "100"}},
            {"name": "database-config", "data": {"MAX_CONNECTIONS": "100", "TIMEOUT": "30"}}
        ]
        
        for cm in default_configmaps:
            configmaps.append({
                "name": cm["name"],
                "data": cm["data"],
                "last_updated": datetime.now().isoformat()
            })
        
        # Create some default HPAs
        default_hpas = [
            {"name": "frontend-hpa", "min_replicas": 2, "max_replicas": 10, "cpu_target_percent": 70},
            {"name": "backend-hpa", "min_replicas": 1, "max_replicas": 5, "cpu_target_percent": 80}
        ]
        
        for hpa in default_hpas:
            hpas.append({
                "name": hpa["name"],
                "min_replicas": hpa["min_replicas"],
                "max_replicas": hpa["max_replicas"],
                "current_replicas": hpa["min_replicas"],
                "cpu_target_percent": hpa["cpu_target_percent"],
                "last_updated": datetime.now().isoformat()
            })
        
        return {
            "nodes": nodes,
            "pods": pods,
            "deployments": deployments,
            "services": services,
            "configmaps": configmaps,
            "hpas": hpas
        }
    
    def get_pods(self, namespace: Optional[str] = None, selector: Optional[Dict[str, str]] = None) -> List[PodStatus]:
        """Returns filtered pod list (mimics kubectl get pods)"""
        pods = [PodStatus(**pod) for pod in self.cluster_state["pods"]]
        # Simple filtering by namespace (not fully implemented - just returns all for now)
        return pods
    
    def get_nodes(self) -> List[NodeStatus]:
        """Get all nodes as Pydantic models"""
        return [NodeStatus(**node) for node in self.cluster_state["nodes"]]
    
    def get_deployments(self) -> List[DeploymentStatus]:
        """Get all deployments as Pydantic models"""
        return [DeploymentStatus(**dep) for dep in self.cluster_state["deployments"]]
    
    def get_services(self) -> List[ServiceStatus]:
        """Get all services as Pydantic models"""
        return [ServiceStatus(**svc) for svc in self.cluster_state["services"]]
    
    def get_configmaps(self) -> List[ConfigMapStatus]:
        """Get all configmaps as Pydantic models"""
        return [ConfigMapStatus(**cm) for cm in self.cluster_state["configmaps"]]
    
    def get_hpas(self) -> List[HPAStatus]:
        """Get all HPAs as Pydantic models"""
        return [HPAStatus(**hpa) for hpa in self.cluster_state["hpas"]]
    
    def get_events(self) -> List[ClusterEvent]:
        """Get all events"""
        return self.events.copy()
    
    def apply_patch(self, resource_type: str, name: str, patch: Dict[str, Any]) -> bool:
        """Apply a patch to a resource"""
        try:
            if resource_type == "deployment":
                for dep in self.cluster_state["deployments"]:
                    if dep["name"] == name:
                        dep.update(patch)
                        dep["last_updated"] = datetime.now().isoformat()
                        if "desired_replicas" in patch or "available_replicas" in patch:
                            self._update_pods_for_deployment(name, dep.get("desired_replicas", dep["desired_replicas"]))
                        return True
            
            elif resource_type == "pod":
                for pod in self.cluster_state["pods"]:
                    if pod["name"] == name:
                        pod.update(patch)
                        pod["last_updated"] = datetime.now().isoformat()
                        return True
                        
            elif resource_type == "node":
                for node in self.cluster_state["nodes"]:
                    if node["name"] == name:
                        node.update(patch)
                        node["last_updated"] = datetime.now().isoformat()
                        return True
                        
            elif resource_type == "service":
                for svc in self.cluster_state["services"]:
                    if svc["name"] == name:
                        svc.update(patch)
                        svc["last_updated"] = datetime.now().isoformat()
                        return True
            
            elif resource_type == "configmap":
                for cm in self.cluster_state["configmaps"]:
                    if cm["name"] == name:
                        cm.update(patch)
                        cm["last_updated"] = datetime.now().isoformat()
                        return True
            
            elif resource_type == "hpa":
                for hpa in self.cluster_state["hpas"]:
                    if hpa["name"] == name:
                        hpa.update(patch)
                        hpa["last_updated"] = datetime.now().isoformat()
                        return True
            
            return False
        except Exception as e:
            print(f"Error applying patch: {e}")
            return False
    
    def _update_pods_for_deployment(self, deployment_name: str, desired_replicas: int):
        """Update pods count for a deployment"""
        current_pods = [p for p in self.cluster_state["pods"] if p.get("deployment") == deployment_name]
        current_count = len(current_pods)
        
        if desired_replicas > current_count:
            nodes = self.cluster_state["nodes"]
            for i in range(desired_replicas - current_count):
                deployment = next((d for d in self.cluster_state["deployments"] if d["name"] == deployment_name), None)
                if deployment:
                    pod_name = f"{deployment_name}-{random.randint(1000, 9999)}-{''.join([chr(random.randint(97, 122)) for _ in range(5)])}"
                    node = nodes[i % len(nodes)] if nodes else None
                    self.cluster_state["pods"].append({
                        "name": pod_name,
                        "status": "Pending",
                        "node": node["name"] if node else None,
                        "restarts": 0,
                        "cpu_request": self.config.get("pod_cpu_request", 500),
                        "mem_request": self.config.get("pod_mem_request", 256),
                        "cpu_limit": self.config.get("pod_cpu_limit", 1000),
                        "mem_limit": self.config.get("pod_mem_limit", 512),
                        "deployment": deployment_name,
                        "last_updated": datetime.now().isoformat()
                    })
        elif desired_replicas < current_count:
            pods_to_remove = current_pods[desired_replicas:]
            for pod in pods_to_remove:
                self.cluster_state["pods"].remove(pod)
    
    def scale(self, deployment_name: str, replicas: int) -> bool:
        """Changes replica count"""
        return self.apply_patch("deployment", deployment_name, {"desired_replicas": replicas})
    
    def delete_pod(self, pod_name: str) -> bool:
        """Removes a pod (it gets recreated by the deployment controller on next tick)"""
        pod_index = None
        for i, pod in enumerate(self.cluster_state["pods"]):
            if pod["name"] == pod_name:
                pod_index = i
                break
        
        if pod_index is not None:
            del self.cluster_state["pods"][pod_index]
            
            event_type: Literal["Normal"] = "Normal"  # type: ignore
            event = ClusterEvent(
                event_id=f"event-delpod-{random.randint(1000, 9999)}",
                timestamp=datetime.now().isoformat(),
                type=event_type,
                reason="UserDeleted",
                message=f"pod/{pod_name} deleted by user",
                involved_object=pod_name
            )
            self.events.append(event)
            
            return True
        return False
    
    def rollout_restart(self, deployment: str) -> bool:
        """Restart a deployment rollout"""
        # Delete all pods for this deployment - they'll get recreated with new config
        pods_to_delete = [p for p in self.cluster_state["pods"] if p.get("deployment") == deployment]
        
        for pod in pods_to_delete:
            event_type: Literal["Normal"] = "Normal"  # type: ignore
            event = ClusterEvent(
                event_id=f"event-restart-{random.randint(1000, 9999)}",
                timestamp=datetime.now().isoformat(),
                type=event_type,
                reason="RolledOut",
                message=f"Deployment {deployment} rollout restart triggered",
                involved_object=deployment
            )
            self.events.append(event)
        
        # Delete pods - they'll be recreated on next tick
        self.cluster_state["pods"] = [p for p in self.cluster_state["pods"] if p.get("deployment") != deployment]
        
        return True
    
    def tick(self):
        """Advances simulated time by one step. Pods in CrashLoopBackOff increment their restart counter. Pending pods on ready nodes eventually transition to Running. Dead nodes stay dead unless drained."""
        self.step_count += 1
        
        # Simulate some natural changes in resource usage
        for node in self.cluster_state["nodes"]:
            node["cpu_usage"] = max(0, min(100, node["cpu_usage"] + random.uniform(-5, 5)))
            node["mem_usage"] = max(0, min(100, node["mem_usage"] + random.uniform(-5, 5)))
            node["last_updated"] = datetime.now().isoformat()
        
        # Update pod statuses based on node status
        for pod in self.cluster_state["pods"]:
            node_name = pod.get("node")
            if node_name:
                node = next((n for n in self.cluster_state["nodes"] if n["name"] == node_name), None)
                if node and node["status"] != "Ready":
                    if pod["status"] == "Running":
                        pod["status"] = "Unknown"
                    elif pod["status"] == "Pending":
                        pod["status"] = "Unknown"
                elif node and node["status"] == "Ready" and pod["status"] == "Pending":
                    if random.random() > 0.7:
                        pod["status"] = "Running"
            pod["last_updated"] = datetime.now().isoformat()
        
        # Update deployment available replicas based on running pods
        for deployment in self.cluster_state["deployments"]:
            running_pods = [p for p in self.cluster_state["pods"] 
                          if p.get("deployment") == deployment["name"] and p["status"] == "Running"]
            deployment["available_replicas"] = len(running_pods)
            deployment["last_updated"] = datetime.now().isoformat()
        
        # Re-create pods for deployments that need them
        for deployment in self.cluster_state["deployments"]:
            desired = deployment.get("desired_replicas", 0)
            current_pods = [p for p in self.cluster_state["pods"] if p.get("deployment") == deployment["name"]]
            current_count = len(current_pods)
            
            if current_count < desired:
                nodes = self.cluster_state["nodes"]
                for i in range(desired - current_count):
                    pod_name = f"{deployment['name']}-{random.randint(1000, 9999)}-{''.join([chr(random.randint(97, 122)) for _ in range(5)])}"
                    node = nodes[i % len(nodes)] if nodes else None
                    self.cluster_state["pods"].append({
                        "name": pod_name,
                        "status": "Running",
                        "node": node["name"] if node else None,
                        "restarts": 0,
                        "cpu_request": self.config.get("pod_cpu_request", 500),
                        "mem_request": self.config.get("pod_mem_request", 256),
                        "cpu_limit": self.config.get("pod_cpu_limit", 1000),
                        "mem_limit": self.config.get("pod_mem_limit", 512),
                        "deployment": deployment["name"],
                        "last_updated": datetime.now().isoformat()
                    })
        
        # Generate occasional events
        if random.random() < 0.3:
            self._generate_event()
    
    def _generate_event(self):
        """Generate a realistic cluster event"""
        event_types = [
            {"type": "Normal", "reason": "Scheduled", "message": "Successfully assigned node"},
            {"type": "Warning", "reason": "FailedScheduling", "message": "0/3 nodes are available: 3 Insufficient cpu."},
            {"type": "Normal", "reason": "Pulling", "message": "Pulling image \"nginx:1.21\""},
            {"type": "Normal", "reason": "Pulled", "message": "Successfully pulled image \"nginx:1.21\""},
            {"type": "Normal", "reason": "Created", "message": "Created container"},
            {"type": "Normal", "reason": "Started", "message": "Started container"},
            {"type": "Warning", "reason": "BackOff", "message": "Back-off restarting failed container"},
            {"type": "Normal", "reason": "Killing", "message": "Stopping container"}
        ]
        
        event = random.choice(event_types)
        involved_objects = []
        involved_objects.extend([p["name"] for p in self.cluster_state["pods"][:3]])
        involved_objects.extend([d["name"] for d in self.cluster_state["deployments"][:3]])
        involved_objects.extend([n["name"] for n in self.cluster_state["nodes"][:3]])
        
        if not involved_objects:
            involved_objects = ["cluster"]
            
        event_type: Literal["Normal", "Warning"] = event["type"]  # type: ignore
        self.events.append(ClusterEvent(
            event_id=f"event-{self._event_counter:04d}",
            timestamp=datetime.now().isoformat(),
            type=event_type,
            reason=event["reason"],
            message=event["message"],
            involved_object=random.choice(involved_objects)
        ))
        self._event_counter += 1
        
        if len(self.events) > 100:
            self.events = self.events[-50:]
    
    def get_full_state(self) -> Dict[str, Any]:
        """Get the full cluster state for debugging"""
        return {
            "nodes": self.get_nodes(),
            "pods": self.get_pods(),
            "deployments": self.get_deployments(),
            "services": self.get_services(),
            "configmaps": self.get_configmaps(),
            "hpas": self.get_hpas(),
            "events": self.get_events(),
            "step": self.step_count
        }
    
    def reset_to_healthy(self):
        """Reset cluster to healthy state"""
        self.cluster_state = self._initialize_healthy_cluster()
        self.step_count = 0
        self.events = []
        self._event_counter = 0
    
    def reset(self, condition=None):
        """Reset the world state and optionally inject a failure condition"""
        self.reset_to_healthy()
        if condition:
            condition.inject(self)
        return self.get_observation()
    
    def get_observation(self, objective: str = "Maintain cluster health"):
        """Serialises the current state into a ClusterObservation Pydantic model"""
        observation_dict = self.get_full_state()
        observation_dict["objective"] = objective
        return ClusterObservation(**observation_dict)