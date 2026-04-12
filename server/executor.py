from pydantic import BaseModel
from typing import Any, Dict, Optional
from server.actions import (
    KubeAction,
    ScaleAction,
    DeletePodAction,
    PatchAction,
    RolloutRestartAction,
    SetHPAAction,
    DrainNodeAction,
    DescribeAction,
    WaitAction,
    CreateSecretAction,
)
from server.models import ClusterObservation


class ExecutionResult(BaseModel):
    observation: ClusterObservation
    action_applied: str
    tick_advanced: bool
    describe_detail: Optional[Dict[str, Any]] = None


def execute(action: KubeAction, world) -> ExecutionResult:
    if isinstance(action, ScaleAction):
        return _execute_scale(action, world)
    elif isinstance(action, DeletePodAction):
        return _execute_delete_pod(action, world)
    elif isinstance(action, PatchAction):
        return _execute_patch(action, world)
    elif isinstance(action, RolloutRestartAction):
        return _execute_rollout_restart(action, world)
    elif isinstance(action, SetHPAAction):
        return _execute_set_hpa(action, world)
    elif isinstance(action, DrainNodeAction):
        return _execute_drain_node(action, world)
    elif isinstance(action, DescribeAction):
        return _execute_describe(action, world)
    elif isinstance(action, WaitAction):
        return _execute_wait(world)
    elif isinstance(action, CreateSecretAction):
        return _execute_create_secret(action, world)
    else:
        raise ValueError(f"Unknown action type: {type(action)}")


def _execute_scale(action: ScaleAction, world) -> ExecutionResult:
    world.scale(action.deployment, action.replicas)
    world.tick()
    return ExecutionResult(
        observation=world.get_observation(),
        action_applied=f"Scaled '{action.deployment}' to {action.replicas} replicas",
        tick_advanced=True,
    )


def _execute_delete_pod(action: DeletePodAction, world) -> ExecutionResult:
    world.delete_pod(action.pod_name)
    world.tick()
    return ExecutionResult(
        observation=world.get_observation(),
        action_applied=f"Deleted pod '{action.pod_name}'",
        tick_advanced=True,
    )


def _execute_patch(action: PatchAction, world) -> ExecutionResult:
    world.apply_patch(action.resource_type, action.name, action.patch)
    world.tick()
    return ExecutionResult(
        observation=world.get_observation(),
        action_applied=f"Patched {action.resource_type} '{action.name}'",
        tick_advanced=True,
    )


def _execute_rollout_restart(action: RolloutRestartAction, world) -> ExecutionResult:
    world.rollout_restart(action.deployment)
    world.tick()
    return ExecutionResult(
        observation=world.get_observation(),
        action_applied=f"Rollout restarted '{action.deployment}'",
        tick_advanced=True,
    )


def _execute_set_hpa(action: SetHPAAction, world) -> ExecutionResult:
    world.set_hpa(
        action.deployment,
        action.min_replicas,
        action.max_replicas,
        action.cpu_target_percent,
    )
    world.tick()
    return ExecutionResult(
        observation=world.get_observation(),
        action_applied=f"Set HPA for '{action.deployment}': {action.min_replicas}-{action.max_replicas} replicas, {action.cpu_target_percent}% CPU",
        tick_advanced=True,
    )


def _execute_drain_node(action: DrainNodeAction, world) -> ExecutionResult:
    world.drain_node(action.node_name)
    world.tick()
    return ExecutionResult(
        observation=world.get_observation(),
        action_applied=f"Drained node '{action.node_name}'",
        tick_advanced=True,
    )


def _execute_describe(action: DescribeAction, world) -> ExecutionResult:
    detail = world.describe(action.resource_type, action.name)
    world.tick()  # Describe advances time - gathering info costs resources
    obs = world.get_observation()
    return ExecutionResult(
        observation=obs,
        action_applied=f"Described {action.resource_type} '{action.name}'",
        tick_advanced=True,
        describe_detail=detail,
    )


def _execute_wait(world) -> ExecutionResult:
    world.tick()
    return ExecutionResult(
        observation=world.get_observation(),
        action_applied="Waited one simulation tick",
        tick_advanced=True,
    )


def _execute_create_secret(action: CreateSecretAction, world) -> ExecutionResult:
    new_secret = {
        "name": action.name,
        "data": action.data,
        "type": "Opaque",
        "created_at": world.get_observation().step,
    }
    world.cluster_state["secrets"].append(new_secret)
    world.tick()
    return ExecutionResult(
        observation=world.get_observation(),
        action_applied=f"Created Secret '{action.name}'",
        tick_advanced=True,
    )
