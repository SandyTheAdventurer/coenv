# Deployment

Guide for deploying COEnv to various platforms.

## Hugging Face Spaces

### Prerequisites

- Hugging Face account
- Docker installed locally
- `openenv` CLI installed

### Push to Hugging Face

```bash
openenv push
```

This will:
1. Validate the directory is an OpenEnv environment
2. Build Docker image
3. Upload to Hugging Face Spaces

### Options

| Option | Description |
|--------|-------------|
| `--directory`, `-d` | Environment directory (default: current) |
| `--repo-id`, `-r` | Repository ID (format: `org/name`) |
| `--base-image`, `-b` | Base Docker image |
| `--private` | Deploy as private space |

### Examples

```bash
# Push to your personal namespace
openenv push

# Push to specific repo
openenv push --repo-id my-org/my-env

# Push with custom base image
openenv push --base-image ghcr.io/meta-pytorch/openenv-base:latest

# Deploy as private
openenv push --private

# Combine options
openenv push --repo-id my-org/my-env --base-image custom:latest --private
```

### Space Endpoints

After deployment:

| Endpoint | Description |
|----------|-------------|
| `/` | Web interface |
| `/docs` | OpenAPI docs |
| `/health` | Health check |
| `/ws` | WebSocket |

## Docker

### Build Image

```bash
docker build -t coenv-env:latest -f Dockerfile .
```

### Run Locally

```bash
docker run -p 8000:8000 coenv-env:latest
```

### Docker Compose

```yaml
version: '3'
services:
  coenv:
    build: .
    ports:
      - "8000:8000"
```

## Kubernetes

Deploy to an existing Kubernetes cluster:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: coenv
spec:
  selector:
    app: coenv
  ports:
    - port: 80
      targetPort: 8000
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: coenv
spec:
  replicas: 2
  selector:
    matchLabels:
      app: coenv
  template:
    metadata:
      labels:
        app: coenv
    spec:
      containers:
        - name: coenv
          image: coenv-env:latest
          ports:
            - containerPort: 8000
```