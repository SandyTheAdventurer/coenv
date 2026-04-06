"""COEnv Actions - Delete pod action"""

from pydantic import BaseModel, Field
from typing import Literal


class DeletePodAction(BaseModel):
    """Delete a specific pod"""
    action_type: Literal["delete_pod"] = "delete_pod"
    pod_name: str = Field(..., description="Pod name to delete")
