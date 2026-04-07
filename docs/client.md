# Client

The COEnv client provides a Python interface to connect to the COEnv server.

## Installation

The client is included with the package:

```bash
uv sync
```

## Basic Usage

### Connect to Running Server

```python
from COEnv import CoenvAction, CoenvEnv

# Connect to existing server
with CoenvEnv(base_url="http://localhost:8000") as env:
    result = env.reset()
    print(result.observation.echoed_message)
    
    result = env.step(CoenvAction(message="Hello!"))
    print(result.observation.echoed_message)
```

### Connect via Docker

```python
from COEnv import CoenvAction, CoenvEnv

# Automatically start container
env = CoenvEnv.from_docker_image("COEnv-env:latest")
try:
    result = env.reset()
    result = env.step(CoenvAction(message="Test"))
finally:
    env.close()
```

## CoenvEnv Class

```python
class CoenvEnv(EnvClient[CoenvAction, CoenvObservation, State]):
```

### Methods

#### `reset() -> StepResult[CoenvObservation]`

Reset the environment and return initial observation.

#### `step(action: CoenvAction) -> StepResult[CoenvObservation]`

Execute an action and return result.

#### `get_state() -> State`

Get current environment state.

### Context Manager

```python
with CoenvEnv(base_url="http://localhost:8000") as env:
    result = env.reset()
    result = env.step(CoenvAction(message="Hello"))
```

Automatically connects on enter and closes on exit.

## WebSocket Connections

The client uses WebSocket for:
- Lower latency (no HTTP overhead per request)
- Persistent sessions (environment state maintained)
- Efficient for multi-step episodes

## Model Exports

Import from the package:

```python
from COEnv import CoenvAction, CoenvObservation, CoenvEnv

action = CoenvAction(message="test")
observation = CoenvObservation(echoed_message="test", message_length=4)
```