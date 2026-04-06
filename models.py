# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

"""
Data models for the Coenv Environment.

These models define the public OpenEnv action/observation schema for the
Kubernetes simulation.
"""

from openenv.core.env_server.types import Action, Observation
from pydantic import Field
from typing import Dict, Any, Optional, Literal, List

try:
    from .server.models import (
        NodeStatus,
        PodStatus,
        DeploymentStatus,
        ServiceStatus,
        ConfigMapStatus,
        HPAStatus,
        ClusterEvent,
    )
except ImportError:
    from server.models import (
        NodeStatus,
        PodStatus,
        DeploymentStatus,
        ServiceStatus,
        ConfigMapStatus,
        HPAStatus,
        ClusterEvent,
    )


class CoenvAction(Action):
    """Action model for the Kubernetes simulator."""

    action_type: Literal[
        "scale",
        "delete_pod",
        "patch",
        "rollout_restart",
        "set_hpa",
        "drain_node",
        "describe",
    ] = Field(..., description="Type of action to execute")

    deployment: Optional[str] = Field(default=None)
    replicas: Optional[int] = Field(default=None)
    pod_name: Optional[str] = Field(default=None)
    resource_type: Optional[Literal["deployment", "pod", "node", "service", "configmap", "hpa"]] = Field(default=None)
    name: Optional[str] = Field(default=None)
    patch: Optional[Dict[str, Any]] = Field(default=None)
    min_replicas: Optional[int] = Field(default=None)
    max_replicas: Optional[int] = Field(default=None)
    cpu_target_percent: Optional[int] = Field(default=None)
    node_name: Optional[str] = Field(default=None)


class CoenvObservation(Observation):
    """Observation model for the Kubernetes simulator."""

    nodes: List[NodeStatus] = Field(default_factory=list)
    pods: List[PodStatus] = Field(default_factory=list)
    deployments: List[DeploymentStatus] = Field(default_factory=list)
    services: List[ServiceStatus] = Field(default_factory=list)
    configmaps: List[ConfigMapStatus] = Field(default_factory=list)
    hpas: List[HPAStatus] = Field(default_factory=list)
    events: List[ClusterEvent] = Field(default_factory=list)
    step: int = Field(default=0)
    objective: str = Field(default="")
