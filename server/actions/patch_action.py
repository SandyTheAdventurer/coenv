"""COEnv Actions - Patch action"""

from pydantic import BaseModel, Field
from typing import Literal, Dict, Any


class PatchAction(BaseModel):
    """Patch a resource with specific changes"""
    action_type: Literal["patch"] = "patch"
    resource_type: Literal["deployment", "pod", "node", "service", "configmap"] = Field(..., description="Resource type")
    name: str = Field(..., description="Resource name")
    patch: Dict[str, Any] = Field(..., description="Patch to apply")
