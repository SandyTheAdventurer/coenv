from pydantic import BaseModel
from typing import Literal


class CreateSecretAction(BaseModel):
    action_type: Literal["create_secret"] = "create_secret"
    name: str
    data: dict  # key-value pairs to store in the secret
