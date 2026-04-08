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
uv run --project . server
python -m coenv.server.app
```

## Docker Deployment

Build the Docker image:
```bash
docker build -t coenv-env:latest -f server/Dockerfile .
```

Run the container:
```bash
docker run -p 8000:8000 coenv-env:latest
```

## Deploy to Hugging Face Spaces

```bash
openenv push
```

See [Deployment](./deployment.md) for more options.

## Quick Test

Test the environment locally:
```bash
python3 server/coenv_environment.py
```