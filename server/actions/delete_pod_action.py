from pydantic import BaseModel, Field
from typing import Literal


class DeletePodAction(BaseModel):
    action_type: Literal["delete_pod"] = "delete_pod"
    pod_name: str = Field(..., description="Exact name of the pod to delete")
