from .scale_action import ScaleAction
from .patch_action import PatchAction
from .delete_pod_action import DeletePodAction
from .rollout_action import RolloutRestartAction
from .hpa_action import SetHPAAction
from .drain_action import DrainNodeAction
from .describe_action import DescribeAction
from .wait_action import WaitAction
from .secret_action import CreateSecretAction
from typing import Union, Any, Dict, Literal

KubeAction = Union[
    ScaleAction,
    PatchAction,
    DeletePodAction,
    RolloutRestartAction,
    SetHPAAction,
    DrainNodeAction,
    DescribeAction,
    WaitAction,
    CreateSecretAction,
]

ActionType = Literal[
    "scale",
    "patch",
    "delete_pod",
    "rollout_restart",
    "set_hpa",
    "drain_node",
    "describe",
    "wait",
    "create_secret",
]


def parse_action(data: Dict[str, Any]) -> KubeAction:
    if not isinstance(data, dict):
        raise ValueError(f"Expected dict, got {type(data)}")

    action_type = data.get("action_type")
    if not action_type:
        raise ValueError("Missing 'action_type' field")

    action_map = {
        "scale": ScaleAction,
        "patch": PatchAction,
        "delete_pod": DeletePodAction,
        "rollout_restart": RolloutRestartAction,
        "set_hpa": SetHPAAction,
        "drain_node": DrainNodeAction,
        "describe": DescribeAction,
        "wait": WaitAction,
        "create_secret": CreateSecretAction,
    }

    action_class = action_map.get(action_type)
    if not action_class:
        raise ValueError(f"Unknown action_type: {action_type}")

    return action_class(**data)


__all__ = [
    "ScaleAction",
    "PatchAction",
    "DeletePodAction",
    "RolloutRestartAction",
    "SetHPAAction",
    "DrainNodeAction",
    "DescribeAction",
    "WaitAction",
    "CreateSecretAction",
    "KubeAction",
    "parse_action",
]
