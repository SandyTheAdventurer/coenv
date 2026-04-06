from pydantic import BaseModel, Field
from typing import Literal


class DescribeAction(BaseModel):
    action_type: Literal["describe"] = "describe"
    resource_type: Literal["deployment", "pod", "node", "service", "configmap"] = Field(..., description="Resource type to inspect")
    name: str = Field(..., description="Resource name to inspect")
