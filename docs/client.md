# Client

The coenv client provides a Python interface to connect to the COEnv server via WebSocket.

## Installation

The client is included with the package:

```bash
uv sync
```

## Basic Usage

### Connect to Running Server

```python
import asyncio
from models import CoenvAction
from client import CoEnv

async def main():
    async with CoEnv(base_url="http://localhost:8000") as client:
        # Reset with a specific task
        result = await client.reset(task="pod_recovery")
        print(f"Objective: {result.observation.objective}")
        print(f"Step: {result.observation.step}")
        
        # Execute an action
        action = CoenvAction(
            action_type="rollout_restart",
            deployment="frontend"
        )
        result = await client.step(action)
        
        # Check metadata for action details
        print(result.observation.metadata)

asyncio.run(main())
```

### Using Context Manager

The client automatically handles connection lifecycle:

```python
async with CoEnv(base_url="http://localhost:8000") as client:
    result = await client.reset(task="autoscaling")
    # ... use client ...
# Connection automatically closed
```

## Available Tasks

| Task | Description |
|------|-------------|
| `pod_recovery` | Fix crash-looping frontend pods |
| `autoscaling` | Configure HPA for traffic spike |
| `incident` | Restore cascading failure |

## CoEnv Class

```python
class CoEnv(EnvClient[CoenvAction, CoenvObservation, State]):
```

### Methods

#### `reset(task: str = "pod_recovery") -> StepResult[CoenvObservation]`

Reset the environment and return initial observation.

```python
result = await client.reset(task="pod_recovery")
```

#### `step(action: CoenvAction) -> StepResult[CoenvObservation]`

Execute an action and return the result.

```python
action = CoenvAction(
    action_type="scale",
    deployment="frontend",
    replicas=5
)
result = await client.step(action)
```

#### `state -> CoenvState`

Get current environment state (episode_id, step_count).

```python
state = client.state
print(f"Episode: {state.episode_id}, Step: {state.step_count}")
```

### StepResult Fields

The `StepResult` contains:

- `observation` (`CoenvObservation`): Current cluster state
- `reward` (`float`): Computed reward for the action
- `done` (`bool`): Whether the task is complete

### Observation Metadata

The observation includes metadata with action results:

```python
result = await client.step(action)
metadata = result.observation.metadata

# Possible metadata keys:
# - scaled: deployment name if scale action
# - replicas: new replica count
# - deleted: pod name if delete_pod action
# - patched: resource if patch action
# - restarted: deployment name if rollout_restart
# - drained: node name if drain_node
# - hpa_set: deployment name if set_hpa
# - described: resource if describe action
# - describe_detail: detailed info from describe
# - error: error message if action failed
# - truncated: True if max steps reached
```

## WebSocket Connections

The client uses WebSocket for:
- Lower latency (no HTTP overhead per request)
- Persistent sessions (environment state maintained)
- Efficient for multi-step episodes

## Complete Example

```python
import asyncio
from models import CoenvAction
from client import CoEnv

async def run_episode():
    async with CoEnv(base_url="http://localhost:8000") as client:
        # Reset for pod_recovery task
        result = await client.reset(task="pod_recovery")
        
        for step in range(1, 16):
            if result.done:
                break
            
            # Example: try rollout restart
            action = CoenvAction(
                action_type="rollout_restart",
                deployment="frontend"
            )
            
            result = await client.step(action)
            print(f"Step {step}: reward={result.reward:.2f}, done={result.done}")
            
            if result.observation.metadata.get("error"):
                print(f"Error: {result.observation.metadata['error']}")

asyncio.run(run_episode())
```

## Model Exports

Import models from the package root:

```python
from models import CoenvAction, CoenvObservation
from client import CoEnv
```