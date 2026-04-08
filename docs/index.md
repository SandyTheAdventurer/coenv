# coenv

A Kubernetes cluster simulation environment for OpenEnv. Provides a testbed for building and evaluating LLM agents that manage Kubernetes clusters.

## Features

- **Simulated Kubernetes Cluster**: Full cluster simulation including pods, nodes, deployments, services, ConfigMaps, and HPA
- **7 Action Types**: Scale, patch, delete pods, rollout restart, set HPA, drain nodes, describe resources
- **HTTP + WebSocket API**: Built on openenv-core with FastAPI server
- **Action Validation**: Validate actions before execution
- **Grader Support**: Customizable reward functions

## Quick Example

```python
from coenv import CoenvAction, CoenvEnv

# Connect to server
with CoenvEnv(base_url="http://localhost:8000") as env:
    result = env.reset()
    
    # Execute actions
    result = env.step(CoenvAction(message="Hello"))
    print(result.observation.echoed_message)
```

## Architecture

```
COEnv/
├── docs/                    # Documentation
├── server/                 # Server implementation
│   ├── app.py            # FastAPI app
│   ├── executor.py       # Action execution
│   ├── validator.py     # Action validation
│   └── actions/        # Action definitions
├── models.py            # Action/Observation models
├── client.py            # Python client
└── openenv.yaml       # OpenEnv manifest
```

## Next Steps

- [Getting Started](./getting-started.md) - Set up and run
- [Actions](./actions.md) - Available actions
- [Models](./models.md) - Data models
- [Server](./server.md) - Server architecture
- [Client](./client.md) - Python client
- [Deployment](./deployment.md) - Deploy to HF Spaces