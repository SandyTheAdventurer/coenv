from pydantic import BaseModel, Field
from typing import Literal, Dict, Any


class PatchAction(BaseModel):
    action_type: Literal["patch"] = "patch"
    resource_type: Literal["deployment", "configmap", "service"] = Field(..., description="One of: deployment, configmap, service")
    name: str = Field(..., description="Resource name")
    patch: Dict[str, Any] = Field(..., description="Fields to update (partial patch)")
