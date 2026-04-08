# Data Models

Reference documentation for all data models used in COEnv.

## Public Action Model

### CoenvAction

The main action model used by clients:

```python
from models import CoenvAction

action = CoenvAction(
    action_type="scale",
    deployment="frontend",
    replicas=3
)
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `action_type` | Literal | Action type: scale, delete_pod, patch, rollout_restart, set_hpa, drain_node, describe, wait |
| `deployment` | Optional[str] | Target deployment name |
| `replicas` | Optional[int] | Target replica count (1-20) |
| `pod_name` | Optional[str] | Specific pod name |
| `resource_type` | Optional[str] | Resource type: deployment, pod, node, service, configmap, hpa |
| `name` | Optional[str] | Resource name |
| `patch` | Optional[Dict] | Patch data |
| `min_replicas` | Optional[int] | HPA min replicas (1-20) |
| `max_replicas` | Optional[int] | HPA max replicas (1-20) |
| `cpu_target_percent` | Optional[int] | HPA CPU target (10-90) |
| `node_name` | Optional[str] | Node name for drain |

## Public Observation Model

### CoenvObservation

The observation returned by the environment:

```python
from models import CoenvObservation

# After a step
result = client.step(action)
obs = result.observation
print(f"Step: {obs.step}")
print(f"Pods: {len(obs.pods)}")
```

**Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `nodes` | List[NodeStatus] | Cluster nodes |
| `pods` | List[PodStatus] | Cluster pods |
| `deployments` | List[DeploymentStatus] | Deployments |
| `services` | List[ServiceStatus] | Services |
| `configmaps` | List[ConfigMapStatus] | ConfigMaps |
| `hpas` | List[HPAStatus] | Horizontal Pod Autoscalers |
| `events` | List[ClusterEvent] | Cluster events |
| `step` | int | Current simulation step |
| `objective` | str | Current task objective |

## Server-Side Models

### NodeStatus

```python
class NodeStatus(BaseModel):
    name: str
    status: Literal["Ready", "NotReady", "Unknown", "SchedulingDisabled"]
    cpu_capacity: int  # cores
    mem_capacity: int  # MB
    cpu_usage: float  # percentage (0-100)
    mem_usage: float  # percentage (0-100)
    last_updated: str  # ISO timestamp
```

### PodStatus

```python
class PodStatus(BaseModel):
    name: str
    status: Literal["Pending", "Running", "Succeeded", "Failed", "Unknown", "CrashLoopBackOff"]
    node: Optional[str]
    restarts: int = 0
    cpu_request: int  # millicores
    mem_request: int  # MB
    cpu_limit: Optional[int]  # millicores
    mem_limit: Optional[int]  # MB
    deployment: Optional[str]
    last_updated: str  # ISO timestamp
```

### DeploymentStatus

```python
class DeploymentStatus(BaseModel):
    name: str
    desired_replicas: int
    available_replicas: int
    image: str
    last_updated: str  # ISO timestamp
```

### ServiceStatus

```python
class ServiceStatus(BaseModel):
    name: str
    type: Literal["ClusterIP", "NodePort", "LoadBalancer", "ExternalName"]
    ports: List[Dict[str, Any]]
    selector: Optional[Dict[str, str]]
    cluster_ip: Optional[str]
    last_updated: str  # ISO timestamp
```

### ConfigMapStatus

```python
class ConfigMapStatus(BaseModel):
    name: str
    data: Dict[str, str]
    last_updated: str  # ISO timestamp
```

### HPAStatus

```python
class HPAStatus(BaseModel):
    name: str
    min_replicas: int
    max_replicas: int
    current_replicas: int
    cpu_target_percent: int
    last_updated: str  # ISO timestamp
```

### ClusterEvent

```python
class ClusterEvent(BaseModel):
    event_id: str
    timestamp: str  # ISO timestamp
    type: Literal["Normal", "Warning"]
    reason: str
    message: str
    involved_object: str
```

### ClusterObservation

```python
class ClusterObservation(BaseModel):
    nodes: List[NodeStatus]
    pods: List[PodStatus]
    deployments: List[DeploymentStatus]
    services: List[ServiceStatus]
    configmaps: List[ConfigMapStatus]
    hpas: List[HPAStatus]
    events: List[ClusterEvent]
    step: int
    objective: str
```

### ExecutionResult

```python
class ExecutionResult(BaseModel):
    observation: ClusterObservation
    action_applied: str
    tick_advanced: bool
    describe_detail: Optional[Dict[str, Any]] = None
```

## State Model

### CoenvState

```python
class CoenvState(State):
    episode_id: str = ""
    step_count: int = 0
```