---
title: Coenv Environment Server
emoji: ⏱️
colorFrom: red
colorTo: pink
sdk: docker
pinned: false
app_port: 8000
base_path: /web
tags:
  - openenv
---

# Coenv Environment

A Kubernetes incident-response simulation environment for OpenEnv.

The environment exposes realistic cluster state (nodes, pods, deployments, services, events) and supports operational actions such as scaling, restarting rollouts, patching resources, setting HPA, and draining nodes.

## Quick Start

The simplest way to use the Coenv environment is through the `CoEnv` class:

```python
from coenv import CoenvAction, CoEnv

try:
    # Create environment from Docker image
    coenvenv = CoEnv.from_docker_image("coenv-env:latest")

    # Reset with a task
    result = coenvenv.reset(task="pod_recovery")
    print(f"Objective: {result.observation.objective}")
    print(f"Pods observed: {len(result.observation.pods)}")

    # Example remediation action
    result = coenvenv.step(
        CoenvAction(
            action_type="scale",
            deployment="frontend",
            replicas=3,
        )
    )
    print(f"Step: {result.observation.step}")
    print(f"Reward: {result.reward}")
    print(f"Done: {result.done}")

finally:
    # Always clean up
    coenvenv.close()
```

That's it! The `CoEnv.from_docker_image()` method handles:
- Starting the Docker container
- Waiting for the server to be ready
- Connecting to the environment
- Container cleanup when you call `close()`

## Building the Docker Image

Before using the environment, you need to build the Docker image:

```bash
# From project root
docker build -t coenv-env:latest -f server/Dockerfile .
```

## Deploying to Hugging Face Spaces

You can easily deploy your OpenEnv environment to Hugging Face Spaces using the `openenv push` command:

```bash
# From the environment directory (where openenv.yaml is located)
openenv push

# Or specify options
openenv push --namespace my-org --private
```

The `openenv push` command will:
1. Validate that the directory is an OpenEnv environment (checks for `openenv.yaml`)
2. Prepare a custom build for Hugging Face Docker space (enables web interface)
3. Upload to Hugging Face (ensuring you're logged in)

### Prerequisites

- Authenticate with Hugging Face: The command will prompt for login if not already authenticated

### Options

- `--directory`, `-d`: Directory containing the OpenEnv environment (defaults to current directory)
- `--repo-id`, `-r`: Repository ID in format 'username/repo-name' (defaults to 'username/env-name' from openenv.yaml)
- `--base-image`, `-b`: Base Docker image to use (overrides Dockerfile FROM)
- `--private`: Deploy the space as private (default: public)

### Examples

```bash
# Push to your personal namespace (defaults to username/env-name from openenv.yaml)
openenv push

# Push to a specific repository
openenv push --repo-id my-org/my-env

# Push with a custom base image
openenv push --base-image ghcr.io/meta-pytorch/openenv-base:latest

# Push as a private space
openenv push --private

# Combine options
openenv push --repo-id my-org/my-env --base-image custom-base:latest --private
```

After deployment, your space will be available at:
`https://huggingface.co/spaces/<repo-id>`

The deployed space includes:
- **Web Interface** at `/web` - Interactive UI for exploring the environment
- **API Documentation** at `/docs` - Full OpenAPI/Swagger interface
- **Health Check** at `/health` - Container health monitoring
- **WebSocket** at `/ws` - Persistent session endpoint for low-latency interactions

## Environment Details

### Action
**CoenvAction** supports the following `action_type` values:
- `scale`
- `delete_pod`
- `patch`
- `rollout_restart`
- `set_hpa`
- `drain_node`
- `describe`

Action-specific fields include `deployment`, `replicas`, `pod_name`, `resource_type`, `name`, `patch`, `min_replicas`, `max_replicas`, `cpu_target_percent`, and `node_name`.

### Observation
**CoenvObservation** contains a typed cluster snapshot and episode metadata:
- `nodes`, `pods`, `deployments`, `services`, `configmaps`, `hpas`, `events`
- `step` (int)
- `objective` (str)
- `reward` (float)
- `done` (bool)
- `metadata` (dict)

### Reward
Reward is task-dependent and based on service health progression:
- `pod_recovery`: fraction of frontend pods in Running state
- `autoscaling`: backend availability progress
- `incident`: proportion of key services restored to healthy

## Advanced Usage

### Connecting to an Existing Server

If you already have a Coenv environment server running, you can connect directly:

```python
from coenv import CoenvAction, CoEnv

# Connect to existing server
coenvenv = CoEnv(base_url="<ENV_HTTP_URL_HERE>")

# Use as normal
result = coenvenv.reset(task="incident")
result = coenvenv.step(
    CoenvAction(action_type="describe", resource_type="deployment", name="api-gateway")
)
```

Note: When connecting to an existing server, `coenvenv.close()` will NOT stop the server.

### Using the Context Manager

The client supports context manager usage for automatic connection management:

```python
from coenv import CoenvAction, CoEnv

# Connect with context manager (auto-connects and closes)
with CoEnv(base_url="http://localhost:8000") as env:
    result = env.reset(task="autoscaling")
    print(f"Reset objective: {result.observation.objective}")
    # Multiple steps with low latency
    for replicas in [3, 4, 5]:
        result = env.step(
            CoenvAction(action_type="scale", deployment="backend", replicas=replicas)
        )
        print(f"Replicas set to {replicas}, reward={result.reward}")
```

The client uses WebSocket connections for:
- **Lower latency**: No HTTP connection overhead per request
- **Persistent session**: Server maintains your environment state
- **Efficient for episodes**: Better for many sequential steps

### Concurrent WebSocket Sessions

The server supports multiple concurrent WebSocket connections. To enable this,
modify `server/app.py` to use factory mode:

```python
# In server/app.py - use factory mode for concurrent sessions
app = create_app(
    CoenvEnvironment,  # Pass class, not instance
    CoenvAction,
    CoenvObservation,
    max_concurrent_envs=4,  # Allow 4 concurrent sessions
)
```

Then multiple clients can connect simultaneously:

```python
from coenv import CoenvAction, CoEnv
from concurrent.futures import ThreadPoolExecutor

def run_episode(client_id: int):
    with CoEnv(base_url="http://localhost:8000") as env:
        result = env.reset(task="pod_recovery")
        for i in range(10):
            result = env.step(
                CoenvAction(action_type="describe", resource_type="deployment", name="frontend")
            )
        return client_id, result.observation.step

# Run 4 episodes concurrently
with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(run_episode, range(4)))
```

## Development & Testing

### Direct Environment Testing

Test the environment logic directly without starting the HTTP server:

```bash
# From the server directory
python3 server/coenv_environment.py
```

This verifies that:
- Environment resets correctly
- Step executes actions properly
- State tracking works
- Rewards are calculated correctly

### Running Locally

Run the server locally for development:

```bash
uvicorn server.app:app --reload
```

## Project Structure

```
coenv/
├── .dockerignore         # Docker build exclusions
├── __init__.py            # Module exports
├── README.md              # This file
├── openenv.yaml           # OpenEnv manifest
├── pyproject.toml         # Project metadata and dependencies
├── uv.lock                # Locked dependencies (generated)
├── client.py              # CoEnv client
├── models.py              # Action and Observation models
└── server/
    ├── __init__.py        # Server module exports
    ├── coenv_environment.py  # Core environment logic
    ├── app.py             # FastAPI application (HTTP + WebSocket endpoints)
    └── Dockerfile         # Container image definition
```
