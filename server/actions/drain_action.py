"""COEnv Actions - Drain action"""

from pydantic import BaseModel, Field
from typing import Literal


class DrainNodeAction(BaseModel):
    """Drain a node (evict all pods)"""
    action_type: Literal["drain_node"] = "drain_node"
    node_name: str = Field(..., description="Node name to drain")
