from pydantic import BaseModel, Field
from typing import Literal


class DrainNodeAction(BaseModel):
    action_type: Literal["drain_node"] = "drain_node"
    node_name: str = Field(..., description="Node to cordon and drain")
