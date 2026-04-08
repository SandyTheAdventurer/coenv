# coenv

A Kubernetes cluster simulation environment for OpenEnv. Provides a testbed for building and evaluating LLM agents that manage Kubernetes clusters.

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

## Next Steps

- [Getting Started](./getting-started.md) - Set up and run
- [Actions](./actions.md) - Available actions
- [Models](./models.md) - Data models
- [Server](./server.md) - Server architecture
- [Client](./client.md) - Python client
- [Deployment](./deployment.md) - Deploy to HF Spaces