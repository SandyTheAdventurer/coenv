from pydantic import BaseModel, Field, field_validator
from typing import Literal


class SetHPAAction(BaseModel):
    action_type: Literal["set_hpa"] = "set_hpa"
    deployment: str = Field(..., description="Target deployment name")
    min_replicas: int = Field(..., ge=1, le=20, description="Minimum replicas")
    max_replicas: int = Field(..., ge=1, le=20, description="Maximum replicas")
    cpu_target_percent: int = Field(..., ge=10, le=90, description="Target CPU percentage")

    @field_validator("max_replicas")
    @classmethod
    def max_must_be_gte_min(cls, v, info):
        if "min_replicas" in info.data and v < info.data["min_replicas"]:
            raise ValueError("max_replicas must be >= min_replicas")
        return v
