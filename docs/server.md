# Server

The coenv server provides the OpenEnv environment adapter for the Kubernetes cluster simulation.

## Architecture

```
coenv/server/
├── app.py                     # FastAPI application entry point
├── simulation_service.py      # OpenEnv Environment adapter (CoenvEnvironment class)
├── coenv_environment.py       # Cluster simulator (World class)
├── executor.py               # Action execution logic
├── validator.py              # Action validation
├── worker.py                 # Episode runner
├── models.py                 # Server-side data models
├── utils.py                  # Utility functions (RNG, latency sim, etc.)
├── actions/                  # Action model definitions
│   ├── __init__.py
│   ├── scale_action.py
│   ├── patch_action.py
│   ├── delete_pod_action.py
│   ├── rollout_action.py
│   ├── hpa_action.py
│   ├── drain_action.py
│   ├── describe_action.py
│   └── wait_action.py
├── conditions/               # Failure condition injectors
│   ├── crash_loop.py        # CrashLoopBackOff injection
│   ├── oom_kill.py          # OOM kill injection
│   ├── node_failure.py      # Node failure injection
│   └── cascade_failure.py   # Cascading failure injection
└── graders/                # Task grading functions
    ├── grader_pod_recovery.py
    ├── grader_autoscaling.py
    └── grader_incident.py
```

## Core Components

### World Class (`coenv_environment.py`)

The `World` class is the in-memory Kubernetes cluster simulator. It maintains:
- Nodes, pods, deployments, services, ConfigMaps, HPAs
- Simulation time (step count)
- Events history

Key methods:
- `reset(condition=None)`: Reset to healthy state with optional failure injection
- `tick()`: Advance simulation by one step
- `scale(deployment, replicas)`: Scale a deployment
- `rollout_restart(deployment)`: Restart all pods in a deployment
- `set_hpa(deployment, min, max, cpu_target)`: Configure HPA
- `drain_node(node_name)`: Cordon and drain a node
- `describe(resource_type, name)`: Get detailed resource info

### CoenvEnvironment (`simulation_service.py`)

Implements the OpenEnv `Environment` interface:

```python
from server.simulation_service import CoenvEnvironment

env = CoenvEnvironment()
observation = env.reset(task="pod_recovery")
observation = env.step(action)
state = env.state  # Current episode state
```

Tasks:
- `pod_recovery`: Frontend crash-looping scenario
- `autoscaling`: Backend overload scenario
- `incident`: Cascading failure scenario

### Executor (`executor.py`)

Executes actions against the World:

```python
from server.executor import execute, ExecutionResult

result = execute(action, world)
# result.observation, result.action_applied, result.tick_advanced
```

### Validator (`validator.py`)

Validates actions before execution:

```python
from server.validator import validate

error = validate(action, world_state)
# Returns error message or None if valid
```

## Server Endpoints

The server exposes OpenEnv-compatible endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Reset environment with optional task |
| `/step` | POST | Execute an action |
| `/state` | GET | Get current episode state |
| `/schema` | GET | Get action/observation schemas |
| `/health` | GET | Health check |
| `/docs` | GET | OpenAPI documentation |

## Creating the Server App

```python
from openenv.core.env_server import create_app
from server.simulation_service import CoenvEnvironment
from models import CoenvAction, CoenvObservation

app = create_app(
    CoenvEnvironment,
    CoenvAction,
    CoenvObservation,
    env_name="coenv"
)
```

## Running the Server

```bash
# Development
uv run uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

# Production
uv run uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4
```

## Configuration

Configuration is loaded from `config.json`:

```json
{
  "num_nodes": 5,
  "node_cpu_capacity": 4,
  "node_mem_capacity": 8192,
  "pod_cpu_request": 250,
  "pod_mem_request": 128,
  "crash_loop_failure_rate": 0.7,
  "oom_kill_failure_rate": 0.6,
  "node_failure_rate": 0.3,
  "cascade_failure_probability": 0.5
}
```