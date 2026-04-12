# coenv

A Kubernetes cluster simulation environment for OpenEnv. Provides a testbed for building and evaluating LLM agents that manage Kubernetes clusters.

## Motivation

As organizations increasingly adopt Kubernetes for container orchestration, the need for intelligent automation in cluster management grows. This environment provides a safe, reproducible testbed for developing and evaluating LLM-based agents that can learn to diagnose and resolve common Kubernetes operational issues, from simple pod recoveries to complex multi-service incidents.

## Features

- **Simulated Kubernetes Cluster**: Full cluster simulation including nodes, pods, deployments, services, ConfigMaps, and HPAs
- **8 Action Types**: scale, patch, delete_pod, rollout_restart, set_hpa, drain_node, describe, wait
- **3 Benchmark Tasks**: pod_recovery, autoscaling, incident
- **Action Validation**: Validate actions before execution
- **Configurable Grading**: Customizable reward functions per task

## Quick Example

```python
from models import CoenvAction
from client import CoEnv

# Connect to server
with CoEnv(base_url="http://localhost:8000") as client:
    result = client.reset(task="pod_recovery")
    
    # Execute actions
    action = CoenvAction(
        action_type="rollout_restart",
        deployment="frontend"
    )
    result = client.step(action)
    print(result.observation.objective)
```

## Architecture

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

## Benchmark Tasks

| Task | Description | Objective |
|------|-------------|-----------|
| `pod_recovery` | Frontend deployment crash-looping | Fix root cause, restore all pods to Running |
| `autoscaling` | Traffic spike to backend | Configure HPA, ensure latency < 500ms |
| `incident` | Cascading failure across services | Identify root cause, restore all services |

### Baseline Scores (Nemotron-3-Super-120B)

The baseline inference script (`inference.py`) produces reproducible scores when run with the free Nemotron model via Hugging Face Inference API.

- **pod_recovery** (Easy): Score ~0.85 - Model consistently recovers pods via rollout_restart
- **autoscaling** (Medium): Score ~0.60 - Model configures HPA but may not optimize properly  
- **incident** (Hard): Score ~0.40 - Complex multi-service failure is challenging for frontier models

Graders produce scores in the range [0.0, 1.0] with efficiency penalties for longer trajectories.

## Next Steps

- [Getting Started](./getting-started.md) - Set up and run
- [Actions](./actions.md) - Available actions
- [Models](./models.md) - Data models
- [Server](./server.md) - Server architecture
- [Client](./client.md) - Python client
- [Deployment](./deployment.md) - Deploy to HF Spaces