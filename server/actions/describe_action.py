"""COEnv Actions - Describe action"""

from pydantic import BaseModel, Field
from typing import Literal


class DescribeAction(BaseModel):
    """Describe/get details of a resource"""
    action_type: Literal["describe"] = "describe"
    resource_type: Literal["deployment", "pod", "node", "service", "configmap"] = Field(..., description="Resource type")
    name: str = Field(..., description="Resource name")
