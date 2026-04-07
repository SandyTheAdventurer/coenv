"""
coenv OpenEnv Application
Uses OpenEnv's create_app factory.
"""

from typing import Dict
import uvicorn

from openenv.core.env_server import create_app

try:
    from ..models import CoenvAction, CoenvObservation
except ImportError:
    from models import CoenvAction, CoenvObservation
try:
    from .simulation_service import CoenvEnvironment
except ImportError:
    from simulation_service import CoenvEnvironment


app = create_app(CoenvEnvironment, CoenvAction, CoenvObservation, env_name="coenv")


@app.get("/health")
async def health() -> Dict[str, str]:
    """Health endpoint used by Docker health checks."""
    return {"status": "ok"}


def main() -> None:
    """Application entrypoint for local execution."""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()