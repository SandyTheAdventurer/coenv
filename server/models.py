from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field


class PodStatus(BaseModel):
    name: str
    namespace: str = "default"
    status: Literal["Running", "Pending", "CrashLoopBackOff", "OOMKilled", "Terminating", "Unknown"]
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
