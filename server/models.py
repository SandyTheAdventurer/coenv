"""
KubeSimEnv Models - Pydantic models for OpenEnv compliance
All typed models are mandatory for OpenEnv spec compliance.
Every endpoint uses these.
"""

from pydantic import BaseModel, Field, AliasChoices
from typing import List, Dict, Any, Optional, Literal


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
    status: Literal[
        "Pending", "Running", "Succeeded", "Failed", "Unknown", "CrashLoopBackOff"
    ]
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


class SecretStatus(BaseModel):
    """Status of a Kubernetes Secret"""

    name: str
    type: Literal["Opaque", "kubernetes.io/tls", "kubernetes.io/basic-auth"]
    data: Dict[str, str]  # base64 encoded values
    last_updated: str


class IngressStatus(BaseModel):
    """Status of a Kubernetes Ingress"""

    name: str
    namespace: str = "default"
    host: str
    service_name: str
    service_port: int
    tls_enabled: bool = False
    annotations: Dict[str, str] = Field(default_factory=dict)
    last_updated: str


class PVStatus(BaseModel):
    """Status of a PersistentVolume"""

    name: str
    capacity: int  # in MB
    access_modes: List[str]
    reclaim_policy: Literal["Retain", "Delete"]
    status: Literal["Bound", "Available", "Failed"]
    claim_ref: Optional[str] = None
    last_updated: str


class PVCStatus(BaseModel):
    """Status of a PersistentVolumeClaim"""

    name: str
    namespace: str = "default"
    size: int  # in MB
    access_modes: List[str]
    status: Literal["Bound", "Pending", "Lost"]
    volume_name: Optional[str] = None
    last_updated: str


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
    type: Literal["Normal", "Warning", "Error"]
    reason: str
    message: str
    involved_object: str
    node_name: Optional[str] = None
    pod_name: Optional[str] = None


class PodLog(BaseModel):
    """Container log output"""

    pod_name: str
    container_name: str
    log_content: str
    timestamp: str


class ResourceMetric(BaseModel):
    """Resource usage metric"""

    name: str
    type: Literal["cpu", "memory", "storage"]
    usage: float
    capacity: float
    usage_percent: float
    timestamp: str


class ClusterObservation(BaseModel):
    """Main observation model - typed cluster snapshot"""

    nodes: List[NodeStatus]
    pods: List[PodStatus]
    deployments: List[DeploymentStatus]
    services: List[ServiceStatus]
    configmaps: List[ConfigMapStatus]
    secrets: List[SecretStatus] = Field(default_factory=list)
    ingresses: List[IngressStatus] = Field(default_factory=list)
    persistentvolumes: List[PVStatus] = Field(default_factory=list)
    persistentvolumeclaims: List[PVCStatus] = Field(default_factory=list)
    hpas: List[HPAStatus] = Field(
        default_factory=list, validation_alias=AliasChoices("hpa", "hpas")
    )
    events: List[ClusterEvent]
    logs: List[PodLog] = Field(default_factory=list)
    metrics: List[ResourceMetric] = Field(default_factory=list)
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
        "scale",
        "delete_pod",
        "patch",
        "rollout_restart",
        "set_hpa",
        "drain_node",
        "describe",
        "wait",
        "create_secret",
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
