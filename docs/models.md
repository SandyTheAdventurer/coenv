# Data Models

Reference documentation for all data models used in COEnv.

## Action Models

### ScaleAction

```python
class ScaleAction(BaseModel):
    action_type: Literal["scale"]
    deployment: str  # Name of the deployment to scale
    replicas: int   # Target replica count (1-20)
```

### PatchAction

```python
class PatchAction(BaseModel):
    action_type: Literal["patch"]
    resource_type: Literal["deployment", "configmap", "service"]
    name: str
    patch: Dict[str, Any]  # Fields to update
```

### DeletePodAction

```python
class DeletePodAction(BaseModel):
    action_type: Literal["delete_pod"]
    pod_name: str  # Exact name of the pod
```

### RolloutRestartAction

```python
class RolloutRestartAction(BaseModel):
    action_type: Literal["rollout_restart"]
    deployment: str  # Deployment to restart
```

### SetHPAAction

```python
class SetHPAAction(BaseModel):
    action_type: Literal["set_hpa"]
    deployment: str
    min_replicas: int   # 1-20
    max_replicas: int   # 1-20
    cpu_target_percent: int  # 10-90
```

### DrainNodeAction

```python
class DrainNodeAction(BaseModel):
    action_type: Literal["drain_node"]
    node_name: str  # Node to drain
```

### DescribeAction

```python
class DescribeAction(BaseModel):
    action_type: Literal["describe"]
    resource_type: Literal["deployment", "pod", "node", "service", "configmap"]
    name: str
```

## Observation Models

### PodStatus

```python
class PodStatus(BaseModel):
    name: str
    namespace: str = "default"
    status: Literal["Running", "Pending", "CrashLoopBackOff", "OOMKilled", "Terminating", "Unknown"]
    node: Optional[str]
    restarts: int = 0
    cpu_usage: float = 0.0
    mem_usage: float = 0.0
    container_image: str = "nginx:1.21"
    env_vars: Dict[str, str]
    resources: Dict[str, Dict[str, str]]
```

### NodeStatus

```python
class NodeStatus(BaseModel):
    name: str
    status: Literal["Ready", "NotReady", "SchedulingDisabled"] = "Ready"
    cpu_capacity: float = 4.0
    mem_capacity: float = 8192.0
    cpu_usage: float = 0.0
    mem_usage: float = 0.0
    pods: List[str]
```

### DeploymentStatus

```python
class DeploymentStatus(BaseModel):
    name: str
    namespace: str = "default"
    desired_replicas: int = 1
    available_replicas: int = 1
    image: str = "nginx:1.21"
    env_vars: List[Dict[str, str]]
    resources: Dict[str, Dict[str, str]]
    hpa: Optional[Dict[str, Any]]
```

### ServiceStatus

```python
class ServiceStatus(BaseModel):
    name: str
    namespace: str = "default"
    service_type: str = "ClusterIP"
    selector: Dict[str, str]
    ports: List[Dict[str, Any]]
    external_ip: Optional[str]
    error_rate: float = 0.0
    latency_p95: float = 0.0
```

### ConfigMapStatus

```python
class ConfigMapStatus(BaseModel):
    name: str
    namespace: str = "default"
    data: Dict[str, str]
```

### HPAStatus

```python
class HPAStatus(BaseModel):
    name: str
    namespace: str = "default"
    target_deployment: str
    min_replicas: int = 1
    max_replicas: int = 10
    cpu_target_percent: int = 80
    current_replicas: int = 1
```

### ClusterEvent

```python
class ClusterEvent(BaseModel):
    message: str
    reason: str
    type: Literal["Normal", "Warning"] = "Normal"
    involved_object: str
    first_timestamp: Optional[str]
    count: int = 1
```

### ClusterObservation

```python
class ClusterObservation(BaseModel):
    nodes: List[NodeStatus]
    pods: List[PodStatus]
    deployments: List[DeploymentStatus]
    services: List[ServiceStatus]
    configmaps: List[ConfigMapStatus]
    hpa: List[HPAStatus]
    events: List[ClusterEvent]
    step: int = 0
    objective: str = ""
```

## Execution Result

```python
class ExecutionResult(BaseModel):
    observation: ClusterObservation
    action_applied: str
    tick_advanced: bool
    describe_detail: Optional[Dict[str, Any]] = None
```