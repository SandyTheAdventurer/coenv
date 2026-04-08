from pydantic import BaseModel
from typing import Literal


class WaitAction(BaseModel):
    action_type: Literal["wait"] = "wait"
