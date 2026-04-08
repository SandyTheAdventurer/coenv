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

## Features

- **Simulated Kubernetes Cluster**: Full cluster simulation including nodes, pods, deployments, services, ConfigMaps, Secrets, Ingresses, PersistentVolumes/PVCs, and HPAs
- **8 Action Types**: scale, patch, delete_pod, rollout_restart, set_hpa, drain_node, describe, wait
- **6 Benchmark Tasks**: pod_recovery, autoscaling, incident, security, backup_recovery, resource_optimization
- **Extended Observation**: Container logs, resource metrics (CPU/memory), cluster events
- **Action Validation**: Validate actions before execution
- **Configurable Grading**: Multi-component rewards with partial credit per task

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

| Task | Description | Objective |
|------|-------------|-----------|
| `pod_recovery` | Frontend deployment crash-looping | Fix root cause, restore all pods to Running |
| `autoscaling` | Traffic spike to backend | Configure HPA, ensure p95 latency < 500ms |
| `incident` | Cascading failure across services | Identify root cause, restore all services |
| `security` | Exposed credentials in ConfigMaps | Rotate secrets, migrate to K8s Secrets |
| `backup_recovery` | PVC in Lost state | Restore PVC binding and database pod |
| `resource_optimization` | Over-provisioned cluster | Downscale to optimal replica count |

## Building the Docker Image

```bash
docker build -t coenv-env:latest -f server/Dockerfile .
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

## Observation

**CoenvObservation** contains:

- `nodes`, `pods`, `deployments`, `services`, `configmaps`, `secrets`, `ingresses`
- `persistentvolumes`, `persistentvolumeclaims`, `hpas`, `events`
- `logs` (container log output for debugging)
- `metrics` (CPU/memory usage per node)
- `step` (int): Current simulation step
- `objective` (str): Current task objective

With `StepResult` containing:
- `reward` (float): Computed reward for the action
- `done` (bool): Whether the task is complete

## Reward

Reward is task-dependent:
- `pod_recovery`: Fraction of frontend pods in Running state
- `autoscaling`: Backend availability (running ratio, stability, HPA config)
- `incident`: Proportion of key services restored (partial credit for 1/3, 2/3)
- `security`: No exposed credentials + K8s Secrets used (0.4 CM + 0.6 secrets)
- `backup_recovery`: PVC bound + PV bound + database ready (0.3 + 0.3 + 0.4)
- `resource_optimization`: Optimal CPU/memory usage + reduced replicas

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
├── docs/                    # Documentation
├── server/                  # Server implementation
│   ├── app.py               # FastAPI app entry point
│   ├── simulation_service.py # Environment logic
│   ├── coenv_environment.py # Cluster simulator (World class)
│   ├── executor.py          # Action execution
│   ├── validator.py         # Action validation
│   ├── models.py           # Server-side data models
│   ├── actions/            # Action definitions
│   ├── conditions/         # Failure condition injectors
│   └── graders/            # Task grading functions
├── models.py                # Public action/observation models
├── client.py                # Python client
└── inference.py             # Example inference script
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | Server URL | `http://localhost:8000` |
| `LLM_BASE_URL` | LLM API endpoint | `https://router.huggingface.co/v1` |
| `MODEL_NAME` | Model identifier | `Qwen/Qwen3-8B` |
| `HF_TOKEN` / `OPENROUTER_API_KEY` | API key | Required |