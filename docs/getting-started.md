# Getting Started

This guide will help you set up and run the COEnv Kubernetes cluster simulation environment.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager

## Installation

1. Clone the repository:
```bash
git clone https://github.com/SandyTheAdventurer/coenv
cd coenv
```

2. Install dependencies:
```bash
uv sync
```

## Running the Server

### Development Mode

Start the server with auto-reload:
```bash
uv run uvicorn server.app:app --reload --host 0.0.0.0 --port 8000
```

### Production Mode

```bash
uv run uvicorn server.app:app --host 0.0.0.0 --port 8000 --workers 4
```

Or use the direct entry point:
```bash
python -m server.app
```

## Quick Test

Test the environment locally using Python:
```python
from server.coenv_environment import World
from server.simulation_service import load_config

config = load_config()
world = World(config, seed=42)

# Reset with a specific task
obs = world.reset(condition=None)
print(f"Step: {obs.step}")
print(f"Pods: {len(obs.pods)}")
print(f"Deployments: {len(obs.deployments)}")
```

## Docker Deployment

Build the Docker image:
```bash
docker build -t coenv-env:latest -f Dockerfile .
```

Run the container:
```bash
docker run -p 8000:8000 coenv-env:latest
```

## Testing Your Setup

Run the tests to verify the setup:
```bash
uv run pytest tests/
```

Run the inference script:
```bash
uv run python inference.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_BASE_URL` | Server URL | `http://localhost:8000` |
| `LLM_BASE_URL` | LLM API endpoint | `https://router.huggingface.co/v1` |
| `MODEL_NAME` | Model identifier | `Qwen/Qwen3-8B` |
| `HF_TOKEN` / `OPENROUTER_API_KEY` | API key | Required |

## Next Steps

- [Actions](./actions.md) - Available actions
- [Models](./models.md) - Data models
- [Client](./client.md) - Python client
- [Deployment](./deployment.md) - Deploy to HuggingFace Spaces