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
  - kubernetes
  - simulation
---

# Coenv Environment

A Kubernetes cluster simulation environment for OpenEnv. Provides a testbed for building and evaluating LLM agents that manage Kubernetes clusters through realistic scenarios.

## Motivation

As organizations increasingly adopt Kubernetes for container orchestration, the need for intelligent automation in cluster management grows. This environment provides a safe, reproducible testbed for developing and evaluating LLM-based agents that can learn to diagnose and resolve common Kubernetes operational issues, from simple pod recoveries to complex multi-service incidents.

Documentation: https://sandytheadventurer.github.io/coenv/

## Features

- **Simulated Kubernetes Cluster**: Full cluster simulation including nodes, pods, deployments, services, ConfigMaps, and HPAs
- **8 Action Types**: scale, patch, delete_pod, rollout_restart, set_hpa, drain_node, describe, wait
- **3 Benchmark Tasks**: pod_recovery, autoscaling, incident
- **Action Validation**: Validate actions before execution
- **Configurable Grading**: Customizable reward functions per task

## Quick Start

```python
import asyncio
from models import CoenvAction
from client import CoEnv

async def main():
    async with CoEnv(base_url="http://localhost:8000") as client:
        # Reset with a task
        result = await client.reset(task="pod_recovery")
        print(f"Objective: {result.observation.objective}")
        print(f"Pods observed: {len(result.observation.pods)}")

        # Example action
        result = await client.step(
            CoenvAction(
                action_type="rollout_restart",
                deployment="frontend",
            )
        )
        print(f"Step: {result.observation.step}")
        print(f"Reward: {result.reward}")
        print(f"Done: {result.done}")

asyncio.run(main())
```

## Benchmark Tasks

| Task | Description | Difficulty | Baseline Score |
|------|-------------|------------|----------------|
| `pod_recovery` | Frontend deployment crash-looping | Easy | 0.75-0.90 |
| `autoscaling` | Traffic spike to backend | Medium | 0.50-0.75 |
| `incident` | Cascading failure across services | Hard | 0.30-0.60 |

### Baseline Scores (Nemotron-3-Super-120B)

The baseline inference script (`inference.py`) produces reproducible scores when run with the free Nemotron model via Hugging Face Inference API.

- **pod_recovery** (Easy): Score ~0.85 - Model consistently recovers pods via rollout_restart
- **autoscaling** (Medium): Score ~0.60 - Model configures HPA but may not optimize properly  
- **incident** (Hard): Score ~0.40 - Complex multi-service failure is challenging for frontier models

Graders produce scores in the range [0.0, 1.0] with efficiency penalties for longer trajectories.

## Building the Docker Image

```bash
docker build -t coenv-env:latest -f Dockerfile .
```

## Deploying to Hugging Face Spaces

```bash
openenv push
```

The `openenv push` command will:
1. Validate that the directory is an OpenEnv environment
2. Build Docker image
3. Upload to Hugging Face Spaces

Options:
- `--repo-id`: Repository ID (format: `org/name`)
- `--private`: Deploy as private space

## Actions

**CoenvAction** supports the following `action_type` values:

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

## Observation Space

The observation space consists of the current state of the simulated Kubernetes cluster:

**CoenvObservation** contains:
- `nodes`: List of node statuses (name, status, CPU/memory capacity and usage)
- `pods`: List of pod statuses (name, status, node, restarts, resource requests/limits)
- `deployments`: List of deployment statuses (name, desired/available replicas, image)
- `services`: List of service statuses (name, type, ports, selector, cluster IP)
- `configmaps`: List of config map statuses (name, data)
- `hpas`: List of HPA statuses (name, min/max/current replicas, CPU target)
- `events`: List of cluster events (event ID, timestamp, type, reason, message)
- `step` (int): Current simulation step
- `objective` (str): Current task objective

With `StepResult` containing:
- `reward` (float): Computed reward for the action (range [0.0, 1.0])
- `done` (bool): Whether the task is complete

## Reward

Reward is task-dependent:
- `pod_recovery`: Fraction of frontend pods in Running state
- `autoscaling`: Backend availability (running ratio, stability, HPA config)
- `incident`: Proportion of key services (auth-service, api-gateway, frontend) restored

## Advanced Usage

### Connect to Existing Server

```python
from models import CoenvAction
from client import CoEnv

async with CoEnv(base_url="http://localhost:8000") as client:
    result = await client.reset(task="incident")
    result = await client.step(
        CoenvAction(action_type="describe", resource_type="deployment", name="api-gateway")
    )
```

### WebSocket Connections

The client uses WebSocket for:
- Lower latency (no HTTP overhead per request)
- Persistent sessions (environment state maintained)
- Efficient for multi-step episodes

## Running Locally

```bash
# Install dependencies
uv sync

# Start server
uv run uvicorn server.app:app --reload --host 0.0.0.0 --port 8000

# Or run inference
uv run python inference.py
```

## Project Structure

```
coenv/
├── docs/                    # Documentation (MkDocs source)
├── server/                  # Server implementation
│   ├── app.py               # FastAPI app entry point
│   ├── simulation_service.py # Environment logic
│   ├── coenv_environment.py # Cluster simulator (World class)
│   ├── executor.py          # Action execution
│   ├── validator.py         # Action validation
│   ├── models.py           # Server-side data models
│   ├── actions/            # Action definitions (scale, patch, delete, etc.)
│   ├── conditions/         # Failure condition injectors (crash_loop, oom_kill, etc.)
│   ├── graders/           # Task grading functions
│   ├── tasks/              # Task definitions (pod_recovery, autoscaling, incident)
│   └── requirements.txt    # Server dependencies
├── tests/                   # Unit tests
├── Dockerfile               # Docker container build
├── models.py                # Public action/observation models
├── client.py                # Python client
├── inference.py             # Example inference script
├── openenv.yaml            # OpenEnv specification
├── pyproject.toml          # Python project config
├── mkdocs.yml              # Documentation config
├── pre-submission.sh       # Pre-submission validation script
└── config.json             # Environment configuration
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | LLM API Endpoint | `https://router.huggingface.co/v1` |
| `MODEL_NAME` | Model identifier | `Qwen/Qwen3-8B` |
| `HF_TOKEN` | API key | Required |

## Building Documentation

This project uses MkDocs with Material theme for documentation.

```bash
# Install dependencies (if not already installed)
uv sync

# Serve documentation locally (with live reload)
mkdocs serve

# Build static documentation
mkdocs build

# Deploy to GitHub Pages
mkdocs gh-deploy
```

For more details, see `mkdocs.yml` configuration.
