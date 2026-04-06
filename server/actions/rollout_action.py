"""COEnv Actions - Rollout restart action"""

from pydantic import BaseModel, Field
from typing import Literal


class RolloutRestartAction(BaseModel):
    """Restart a deployment rollout"""
    action_type: Literal["rollout_restart"] = "rollout_restart"
    deployment: str = Field(..., description="Deployment name to restart")
