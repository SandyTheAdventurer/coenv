# Actions

The COEnv environment supports various Kubernetes cluster management actions.

## Action Types

| Action | Description |
|--------|-------------|
| `scale` | Scale deployment replica count |
| `patch` | Patch deployment, configmap, or service |
| `delete_pod` | Delete a specific pod |
| `rollout_restart` | Restart all pods in a deployment |
| `set_hpa` | Configure Horizontal Pod Autoscaler |
| `drain_node` | Cordon and drain a node |
| `describe` | Get detailed info about a resource |

## Scale Action

Scale a deployment to a specific number of replicas.

```python
from server.actions import ScaleAction

action = ScaleAction(
    deployment="my-deployment",
    replicas=3
)
```

**Parameters:**
- `deployment` (str): Name of the deployment to scale
- `replicas` (int): Target replica count (1-20)

## Patch Action

Apply a partial patch to a resource.

```python
from server.actions import PatchAction

action = PatchAction(
    resource_type="deployment",
    name="my-deployment",
    patch={"spec": {"replicas": 5}}
)
```

**Parameters:**
- `resource_type` (str): One of `deployment`, `configmap`, `service`
- `name` (str): Resource name
- `patch` (dict): Fields to update

## Delete Pod Action

Delete a specific pod.

```python
from server.actions import DeletePodAction

action = DeletePodAction(
    pod_name="my-pod-abc123"
)
```

**Parameters:**
- `pod_name` (str): Exact name of the pod to delete

## Rollout Restart Action

Restart all pods in a deployment.

```python
from server.actions import RolloutRestartAction

action = RolloutRestartAction(
    deployment="my-deployment"
)
```

**Parameters:**
- `deployment` (str): Deployment to restart

## Set HPA Action

Configure horizontal pod autoscaling.

```python
from server.actions import SetHPAAction

action = SetHPAAction(
    deployment="my-deployment",
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

## Drain Node Action

Cordon and drain a node.

```python
from server.actions import DrainNodeAction

action = DrainNodeAction(
    node_name="node-1"
)
```

**Parameters:**
- `node_name` (str): Node to drain

## Describe Action

Get detailed information about a resource.

```python
from server.actions import DescribeAction

action = DescribeAction(
    resource_type="deployment",
    name="my-deployment"
)
```

**Parameters:**
- `resource_type` (str): One of `deployment`, `pod`, `node`, `service`, `configmap`
- `name` (str): Resource name

## Parsing Actions

Use `parse_action` to convert a dictionary to an action object:

```python
from server.actions import parse_action

data = {
    "action_type": "scale",
    "deployment": "my-app",
    "replicas": 3
}
action = parse_action(data)
```