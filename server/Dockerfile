# Multi-stage build using openenv-base
# This Dockerfile is flexible and works for both:
# - In-repo environments (with local src/core)
# - Standalone environments (with openenv from pip)

ARG BASE_IMAGE=ghcr.io/meta-pytorch/openenv-base:latest
FROM ${BASE_IMAGE} AS builder

WORKDIR /app

# Build arguments for OpenEnv build pipeline compatibility.
ARG BUILD_MODE=in-repo
ARG ENV_NAME=coenv

# Copy environment code from the build context root.
COPY . /app/env

WORKDIR /app/env

# Install dependencies with uv.
# Use pyproject/uv.lock when present, otherwise fall back to requirements.txt
# because submission validators often build from server/ as context.
RUN --mount=type=cache,target=/root/.cache/uv \
	if [ -f pyproject.toml ]; then \
		if [ -f uv.lock ]; then \
			uv sync --frozen --no-install-project --no-editable; \
		else \
			uv sync --no-install-project --no-editable; \
		fi; \
	elif [ -f requirements.txt ]; then \
		uv venv .venv; \
		uv pip install --python .venv/bin/python -r requirements.txt; \
	else \
		echo "No pyproject.toml or requirements.txt found in build context" >&2; \
		exit 2; \
	fi

RUN --mount=type=cache,target=/root/.cache/uv \
	if [ -f pyproject.toml ]; then \
		if [ -f uv.lock ]; then \
			uv sync --frozen --no-editable; \
		else \
			uv sync --no-editable; \
		fi; \
	else \
		true; \
	fi

FROM ${BASE_IMAGE}

WORKDIR /app

# Copy runtime virtualenv and environment code from builder.
COPY --from=builder /app/env/.venv /app/.venv
COPY --from=builder /app/env /app/env

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/env:$PYTHONPATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
	CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "cd /app/env && uvicorn server.app:app --host 0.0.0.0 --port 8000"]