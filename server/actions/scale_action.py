from pydantic import BaseModel, Field
from typing import Literal


class ScaleAction(BaseModel):
    action_type: Literal["scale"] = "scale"
    deployment: str = Field(..., description="Name of the deployment to scale")
    replicas: int = Field(..., ge=1, le=20, description="Target replica count (1-20)")
