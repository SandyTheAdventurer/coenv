# Server

The coenv server provides a FastAPI application for the Kubernetes cluster simulation.

## Architecture

```
coenv/
├── server/
│   ├── app.py                    # FastAPI application entry point
│   ├── COEnv_environment.py     # Environment implementation
│   ├── executor.py            # Action execution logic
│   ├── validator.py           # Action validation
│   ├── worker.py              # Episode runner
│   ├── models.py             # Server-side data models
│   ├── actions/              # Action definitions
│   │   ├── scale_action.py
│   │   ├── patch_action.py
│   │   ├── delete_pod_action.py
│   │   ├── rollout_action.py
│   │   ├── hpa_action.py
│   │   ├── drain_action.py
│   │   └── describe_action.py
│   ├── graders/              # Grader functions
│   ├── conditions/           # Done condition logic
│   └── tasks/                # Task definitions
```

## Server Endpoints

The server exposes the following endpoints via `openenv-core`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/reset` | POST | Reset the environment |
| `/step` | POST | Execute an action |
| `/state` | GET | Get current state |
| `/schema` | GET | Get action/observation schemas |
| `/docs` | GET | OpenAPI documentation |
| `/health` | GET | Health check |
| `/web` | GET | Web interface |

## WebSocket

Persistent sessions via WebSocket for low-latency interactions:

```
WS /ws
```

## Executor

The `executor.py` module handles action execution:

```python
from server.executor import execute, ExecutionResult

result = execute(action, world)
```

Returns `ExecutionResult` with:
- `observation`: Updated cluster state
- `action_applied`: Description of action
- `tick_advanced`: Whether time progressed
- `describe_detail`: Detail from describe actions

## Validator

Validate actions before execution:

```python
from server.validator import validate

error = validate(action, world_state)
# Returns error message or None if valid
```

## Worker

Run episodes with the Worker class:

```python
from server.worker import Worker, EpisodeResult

worker = Worker()
result = worker.run_episode(
    task_id="task-1",
    world=world,
    get_action=get_action,
    max_steps=50,
    grader=grader
)
```

## Creating the App

```python
from openenv.core.env_server.http_server import create_app
from server.COEnv_environment import CoenvEnvironment
from models import CoenvAction, CoenvObservation

app = create_app(
    CoenvEnvironment,
    CoenvAction,
    CoenvObservation,
    env_name="coenv",
    max_concurrent_envs=1
)
```

Run with uvicorn:
```bash
uvicorn server.app:app --host 0.0.0.0 --port 8000
```