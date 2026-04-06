"""COEnv Actions - Scale action"""

from pydantic import BaseModel, Field
from typing import Literal


class ScaleAction(BaseModel):
    """Scale a deployment to a specific replica count"""
    action_type: Literal["scale"] = "scale"
    deployment: str = Field(..., description="Deployment name to scale")
    replicas: int = Field(..., ge=0, le=100, description="Number of replicas")
