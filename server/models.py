from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class PodStatus(BaseModel):
    name: str
    namespace: str = "default"
    status: Literal["Running", "Pending", "CrashLoopBackOff", "OOMKilled", "Terminating", "Unknown", "Failed", "Succeeded"]
    node: Optional[str] = None
    restarts: int = 0
    cpu_usage: float = 0.0
    mem_usage: float = 0.0
    container_image: str = "nginx:1.21"
    env_vars: Dict[str, str] = Field(default_factory=dict)
    resources: Dict[str, Dict[str, str]] = Field(default_factory=lambda: {"limits": {}, "requests": {}})


class NodeStatus(BaseModel):
    name: str
    status: Literal["Ready", "NotReady", "SchedulingDisabled"] = "Ready"
    cpu_capacity: float = 4.0
    mem_capacity: float = 8192.0
    cpu_usage: float = 0.0
    mem_usage: float = 0.0
    pods: List[str] = Field(default_factory=list)


class DeploymentStatus(BaseModel):
    name: str
    namespace: str = "default"
    desired_replicas: int = 1
    available_replicas: int = 1
    image: str = "nginx:1.21"
    env_vars: List[Dict[str, str]] = Field(default_factory=list)
    resources: Dict[str, Dict[str, str]] = Field(default_factory=lambda: {"limits": {}, "requests": {}})
    hpa: Optional[Dict[str, Any]] = None


class ServiceStatus(BaseModel):
    name: str
    namespace: str = "default"
    service_type: str = "ClusterIP"
    selector: Dict[str, str] = Field(default_factory=dict)
    ports: List[Dict[str, Any]] = Field(default_factory=lambda: [{"port": 80, "targetPort": 80}])
    external_ip: Optional[str] = None
    error_rate: float = 0.0
    latency_p95: float = 0.0


class ConfigMapStatus(BaseModel):
    name: str
    namespace: str = "default"
    data: Dict[str, str] = Field(default_factory=dict)


class HPAStatus(BaseModel):
    name: str
    namespace: str = "default"
    target_deployment: str
    min_replicas: int = 1
    max_replicas: int = 10
    cpu_target_percent: int = 80
    current_replicas: int = 1


class ClusterEvent(BaseModel):
    message: str
    reason: str
    type: Literal["Normal", "Warning"] = "Normal"
    involved_object: str = ""
    first_timestamp: Optional[str] = None
    count: int = 1


class ClusterObservation(BaseModel):
    nodes: List[NodeStatus] = Field(default_factory=list)
    pods: List[PodStatus] = Field(default_factory=list)
    deployments: List[DeploymentStatus] = Field(default_factory=list)
    services: List[ServiceStatus] = Field(default_factory=list)
    configmaps: List[ConfigMapStatus] = Field(default_factory=list)
    hpa: List[HPAStatus] = Field(default_factory=list)
    events: List[ClusterEvent] = Field(default_factory=list)
    step: int = 0
    objective: str = ""
"""
KubeSimEnv Models - Pydantic models for OpenEnv compliance
All typed models are mandatory for OpenEnv spec compliance.
Every endpoint uses these.
"""

from pydantic import BaseModel, Field, AliasChoices
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime


class NodeStatus(BaseModel):
    """Status of a Kubernetes node"""
    name: str
    status: Literal["Ready", "NotReady", "Unknown", "SchedulingDisabled"]
    cpu_capacity: int  # in cores
    mem_capacity: int  # in MB
    cpu_usage: float = Field(ge=0, le=100)  # percentage
    mem_usage: float = Field(ge=0, le=100)  # percentage
    last_updated: str  # ISO timestamp


class PodStatus(BaseModel):
    """Status of a Kubernetes pod"""
    name: str
    status: Literal["Pending", "Running", "Succeeded", "Failed", "Unknown", "CrashLoopBackOff", "OOMKilled", "Terminating"]
    node: Optional[str] = None
    restarts: int = 0
    cpu_request: int = Field(default=0)  # in millicores
    mem_request: int = Field(default=0)  # in MB
    cpu_limit: Optional[int] = Field(default=None)  # in millicores
    mem_limit: Optional[int] = Field(default=None)  # in MB
    deployment: Optional[str] = None
    last_updated: str  # ISO timestamp


class DeploymentStatus(BaseModel):
    """Status of a Kubernetes deployment"""
    name: str
    desired_replicas: int
    available_replicas: int
    image: str
    last_updated: str  # ISO timestamp


class ServiceStatus(BaseModel):
    """Status of a Kubernetes service"""
    name: str
    type: Literal["ClusterIP", "NodePort", "LoadBalancer", "ExternalName"]
    ports: List[Dict[str, Any]]
    selector: Optional[Dict[str, str]] = None
    cluster_ip: Optional[str] = None
    last_updated: str  # ISO timestamp


class ConfigMapStatus(BaseModel):
    """Status of a Kubernetes ConfigMap"""
    name: str
    data: Dict[str, str]
    last_updated: str  # ISO timestamp


class HPAStatus(BaseModel):
    """Status of a HorizontalPodAutoscaler"""
    name: str
    min_replicas: int
    max_replicas: int
    current_replicas: int
    cpu_target_percent: int
    last_updated: str  # ISO timestamp


class ClusterEvent(BaseModel):
    """Kubernetes-style event"""
    event_id: str
    timestamp: str  # ISO timestamp
    type: Literal["Normal", "Warning"]
    reason: str
    message: str
    involved_object: str


class ClusterObservation(BaseModel):
    """Main observation model - typed cluster snapshot"""
    nodes: List[NodeStatus]
    pods: List[PodStatus]
    deployments: List[DeploymentStatus]
    services: List[ServiceStatus]
    configmaps: List[ConfigMapStatus]
    hpas: List[HPAStatus] = Field(
        default_factory=list,
        validation_alias=AliasChoices("hpa", "hpas")
    )
    events: List[ClusterEvent]
    step: int
    objective: str


class RewardSignal(BaseModel):
    """Reward signal returned by step()"""
    reward: float
    done: bool
    info: Dict[str, Any] = Field(default_factory=dict)


# Action Models - These represent the structured action space
class KubeAction(BaseModel):
    """Base action model"""
    action_type: Literal[
        "scale", "delete_pod", "patch", "rollout_restart", 
        "set_hpa", "drain_node", "describe"
    ]


class ScaleAction(KubeAction):
    """Scale a deployment to a specific replica count"""
    deployment: str
    replicas: int


class DeletePodAction(KubeAction):
    """Delete a specific pod"""
    pod_name: str


class PatchAction(KubeAction):
    """Patch a resource with specific changes"""
    resource_type: Literal["deployment", "pod", "node", "service"]
    name: str
    patch: Dict[str, Any]


class RolloutRestartAction(KubeAction):
    """Restart a deployment rollout"""
    deployment: str


class SetHPAAction(KubeAction):
    """Set HorizontalPodAutoscaler for a deployment"""
    deployment: str
    min_replicas: int
    max_replicas: int
    cpu_target_percent: int


class DrainNodeAction(KubeAction):
    """Drain a node (evict all pods)"""
    node_name: str


class DescribeAction(KubeAction):
    """Describe/get details of a resource"""
    resource_type: Literal["deployment", "pod", "node", "service"]
    name: str