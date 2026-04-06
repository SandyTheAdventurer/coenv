from pydantic import BaseModel, Field
from typing import Literal


class RolloutRestartAction(BaseModel):
    action_type: Literal["rollout_restart"] = "rollout_restart"
    deployment: str = Field(..., description="Deployment to restart all pods for")
