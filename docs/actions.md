# Actions

The COEnv environment supports various Kubernetes cluster management actions.

## Action Types

| Action | Description | Tick Advances |
|--------|-------------|---------------|
| `scale` | Scale deployment replica count | Yes |
| `patch` | Patch deployment, configmap, service, hpa, pod, node | Yes |
| `delete_pod` | Delete a specific pod | Yes |
| `rollout_restart` | Restart all pods in a deployment | Yes |
| `set_hpa` | Configure Horizontal Pod Autoscaler | Yes |
| `drain_node` | Cordon and drain a node | Yes |
| `describe` | Get detailed info about a resource | No |
| `wait` | Wait one simulation tick | Yes |

## Using Actions

Actions can be created using the `CoenvAction` model:

```python
from models import CoenvAction

# Scale action
action = CoenvAction(
    action_type="scale",
    deployment="frontend",
    replicas=3
)

# Patch action
action = CoenvAction(
    action_type="patch",
    resource_type="deployment",
    name="frontend",
    patch={"spec": {"replicas": 5}}
)

# Describe action
action = CoenvAction(
    action_type="describe",
    resource_type="deployment",
    name="frontend"
)
```

## Action Details

### Scale Action

Scale a deployment to a specific number of replicas.

```python
action = CoenvAction(
    action_type="scale",
    deployment="frontend",
    replicas=3
)
```

**Parameters:**
- `deployment` (str): Name of the deployment to scale
- `replicas` (int): Target replica count (1-20)

### Patch Action

Apply a partial patch to a resource.

```python
action = CoenvAction(
    action_type="patch",
    resource_type="deployment",
    name="my-deployment",
    patch={"spec": {"replicas": 5}}
)
```

**Parameters:**
- `resource_type` (str): One of `deployment`, `pod`, `node`, `service`, `configmap`, `hpa`
- `name` (str): Resource name
- `patch` (dict): Fields to update

### Delete Pod Action

Delete a specific pod. The deployment controller will recreate it on the next tick.

```python
action = CoenvAction(
    action_type="delete_pod",
    pod_name="my-pod-abc123"
)
```

**Parameters:**
- `pod_name` (str): Exact name of the pod to delete

### Rollout Restart Action

Delete all pods in a deployment to trigger a new rollout. This clears any injected failure conditions.

```python
action = CoenvAction(
    action_type="rollout_restart",
    deployment="frontend"
)
```

**Parameters:**
- `deployment` (str): Deployment to restart

### Set HPA Action

Configure horizontal pod autoscaling for a deployment.

```python
action = CoenvAction(
    action_type="set_hpa",
    deployment="backend",
    min_replicas=2,
    max_replicas=10,
    cpu_target_percent=80
)
```

**Parameters:**
- `deployment` (str): Target deployment name
- `min_replicas` (int): Minimum replicas (1-20)
- `max_replicas` (int): Maximum replicas (1-20)
- `cpu_target_percent` (int): Target CPU percentage (10-90)

### Drain Node Action

Cordon a node and evict all pods from it.

```python
action = CoenvAction(
    action_type="drain_node",
    node_name="node-1"
)
```

**Parameters:**
- `node_name` (str): Node to drain

**Note:** Cannot drain the last healthy node in the cluster.

### Describe Action

Get detailed information about a resource without advancing simulation time.

```python
action = CoenvAction(
    action_type="describe",
    resource_type="deployment",
    name="frontend"
)
```

**Parameters:**
- `resource_type` (str): One of `deployment`, `pod`, `node`, `service`, `configmap`, `hpa`
- `name` (str): Resource name

The response includes:
- `resource`: Full resource details
- `related_pods`: Pods related to this resource
- `recent_events`: Recent events involving this resource

### Wait Action

Advance simulation by one tick without making any changes. Useful for waiting for pods to transition from Pending to Running.

```python
action = CoenvAction(
    action_type="wait"
)
```

## Action Validation

Actions are validated before execution. Invalid actions return an error in the observation metadata:

```python
result = client.step(action)
if result.observation.metadata.get("error"):
    print(f"Action error: {result.observation.metadata['error']}")
```

Validation rules:
- Scale: deployment must exist, replicas 1-20
- DeletePod: pod must exist
- Patch: resource must exist
- RolloutRestart: deployment must exist
- SetHPA: deployment must exist, max >= min, cpu_target 10-90
- DrainNode: node must exist, cannot drain last healthy node
- Describe: resource must exist