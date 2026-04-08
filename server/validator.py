from typing import Optional, Dict, Any
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
)


def validate(action: KubeAction, world_state: Dict[str, Any]) -> Optional[str]:
    if isinstance(action, ScaleAction):
        return _validate_scale(action, world_state)
    elif isinstance(action, DeletePodAction):
        return _validate_delete_pod(action, world_state)
    elif isinstance(action, PatchAction):
        return _validate_patch(action, world_state)
    elif isinstance(action, RolloutRestartAction):
        return _validate_rollout_restart(action, world_state)
    elif isinstance(action, SetHPAAction):
        return _validate_set_hpa(action, world_state)
    elif isinstance(action, DrainNodeAction):
        return _validate_drain_node(action, world_state)
    elif isinstance(action, DescribeAction):
        return _validate_describe(action, world_state)
    elif isinstance(action, WaitAction):
        return None
    return None


def _validate_scale(action: ScaleAction, world_state: Dict[str, Any]) -> Optional[str]:
    deployments = world_state.get("deployments", [])
    deployment_names = [d.get("name") for d in deployments]

    if action.deployment not in deployment_names:
        return (
            f"Deployment '{action.deployment}' not found. Available: {deployment_names}"
        )

    if action.replicas < 1 or action.replicas > 20:
        return f"Replica count must be between 1 and 20, got {action.replicas}"

    return None


def _validate_delete_pod(
    action: DeletePodAction, world_state: Dict[str, Any]
) -> Optional[str]:
    pods = world_state.get("pods", [])
    pod_names = [p.get("name") for p in pods]

    if action.pod_name not in pod_names:
        return f"Pod '{action.pod_name}' not found in cluster. Available: {pod_names}"

    pod = next((p for p in pods if p.get("name") == action.pod_name), None)
    if pod and pod.get("status") == "Terminating":
        return f"Pod '{action.pod_name}' is already terminating"

    return None


def _validate_patch(action: PatchAction, world_state: Dict[str, Any]) -> Optional[str]:
    resource_type = action.resource_type
    name = action.name

    if resource_type == "deployment":
        deployments = world_state.get("deployments", [])
        deployment_names = [d.get("name") for d in deployments]
        if name not in deployment_names:
            return f"Deployment '{name}' not found. Available: {deployment_names}"

    elif resource_type == "configmap":
        configmaps = world_state.get("configmaps", [])
        configmap_names = [c.get("name") for c in configmaps]
        if name not in configmap_names:
            return f"ConfigMap '{name}' not found. Available: {configmap_names}"

    elif resource_type == "service":
        services = world_state.get("services", [])
        service_names = [s.get("name") for s in services]
        if name not in service_names:
            return f"Service '{name}' not found. Available: {service_names}"

    else:
        return f"Invalid resource_type: {resource_type}. Must be one of: deployment, configmap, service"

    return None


def _validate_rollout_restart(
    action: RolloutRestartAction, world_state: Dict[str, Any]
) -> Optional[str]:
    deployments = world_state.get("deployments", [])
    deployment_names = [d.get("name") for d in deployments]

    if action.deployment not in deployment_names:
        return (
            f"Deployment '{action.deployment}' not found. Available: {deployment_names}"
        )

    return None


def _validate_set_hpa(
    action: SetHPAAction, world_state: Dict[str, Any]
) -> Optional[str]:
    deployments = world_state.get("deployments", [])
    deployment_names = [d.get("name") for d in deployments]

    if action.deployment not in deployment_names:
        return (
            f"Deployment '{action.deployment}' not found. Available: {deployment_names}"
        )

    if action.max_replicas < action.min_replicas:
        return f"max_replicas ({action.max_replicas}) must be >= min_replicas ({action.min_replicas})"

    if action.cpu_target_percent < 10 or action.cpu_target_percent > 90:
        return f"cpu_target_percent must be between 10 and 90, got {action.cpu_target_percent}"

    return None


def _validate_drain_node(
    action: DrainNodeAction, world_state: Dict[str, Any]
) -> Optional[str]:
    nodes = world_state.get("nodes", [])
    node_names = [n.get("name") for n in nodes]

    if action.node_name not in node_names:
        return f"Node '{action.node_name}' not found. Available: {node_names}"

    node = next((n for n in nodes if n.get("name") == action.node_name), None)
    if node and node.get("status") == "SchedulingDisabled":
        return f"Node '{action.node_name}' is already drained (SchedulingDisabled)"

    ready_nodes = [n for n in nodes if n.get("status") == "Ready"]
    if len(ready_nodes) <= 1 and node and node.get("status") == "Ready":
        return "Cannot drain last healthy node — cluster would lose all capacity"

    return None


def _validate_describe(
    action: DescribeAction, world_state: Dict[str, Any]
) -> Optional[str]:
    resource_type = action.resource_type
    name = action.name

    if resource_type == "deployment":
        deployments = world_state.get("deployments", [])
        deployment_names = [d.get("name") for d in deployments]
        if name not in deployment_names:
            return f"Deployment '{name}' not found. Available: {deployment_names}"

    elif resource_type == "pod":
        pods = world_state.get("pods", [])
        pod_names = [p.get("name") for p in pods]
        if name not in pod_names:
            return f"Pod '{name}' not found. Available: {pod_names}"

    elif resource_type == "node":
        nodes = world_state.get("nodes", [])
        node_names = [n.get("name") for n in nodes]
        if name not in node_names:
            return f"Node '{name}' not found. Available: {node_names}"

    elif resource_type == "service":
        services = world_state.get("services", [])
        service_names = [s.get("name") for s in services]
        if name not in service_names:
            return f"Service '{name}' not found. Available: {service_names}"

    elif resource_type == "configmap":
        configmaps = world_state.get("configmaps", [])
        configmap_names = [c.get("name") for c in configmaps]
        if name not in configmap_names:
            return f"ConfigMap '{name}' not found. Available: {configmap_names}"

    else:
        return f"Invalid resource_type: {resource_type}. Must be one of: deployment, pod, node, service, configmap"

    return None
