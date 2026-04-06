"""COEnv Actions - HPA action"""

from pydantic import BaseModel, Field
from typing import Literal


class SetHPAAction(BaseModel):
    """Set HorizontalPodAutoscaler for a deployment"""
    action_type: Literal["set_hpa"] = "set_hpa"
    deployment: str = Field(..., description="Deployment name")
    min_replicas: int = Field(..., ge=1, le=50, description="Minimum replicas")
    max_replicas: int = Field(..., ge=1, le=100, description="Maximum replicas")
    cpu_target_percent: int = Field(..., ge=1, le=100, description="CPU target percentage")
