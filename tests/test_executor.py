import pytest
from unittest.mock import MagicMock, call
from server.actions import (
    ScaleAction,
    DeletePodAction,
    PatchAction,
    RolloutRestartAction,
    SetHPAAction,
    DrainNodeAction,
    DescribeAction,
)
from server.executor import execute
from server.models import ClusterObservation


class MockWorld:
    def __init__(self):
        self.scale_called_with = None
        self.delete_pod_called_with = None
        self.apply_patch_called_with = None
        self.rollout_restart_called_with = None
        self.set_hpa_called_with = None
        self.drain_node_called_with = None
        self.describe_called_with = None
        self.tick_called = False
        self._observation = ClusterObservation(nodes=[], pods=[], deployments=[], services=[], configmaps=[], hpa=[], events=[], step=0, objective="")
        self._raw_state = {"nodes": [], "pods": [], "deployments": [], "services": [], "configmaps": []}

    def scale(self, deployment, replicas):
        self.scale_called_with = (deployment, replicas)

    def delete_pod(self, pod_name):
        self.delete_pod_called_with = pod_name

    def apply_patch(self, resource_type, name, patch):
        self.apply_patch_called_with = (resource_type, name, patch)

    def rollout_restart(self, deployment):
        self.rollout_restart_called_with = deployment

    def set_hpa(self, deployment, min_replicas, max_replicas, cpu_target_percent):
        self.set_hpa_called_with = (deployment, min_replicas, max_replicas, cpu_target_percent)

    def drain_node(self, node_name):
        self.drain_node_called_with = node_name

    def describe(self, resource_type, name):
        self.describe_called_with = (resource_type, name)
        return {"type": resource_type, "name": name, "detail": "mock detail"}

    def tick(self):
        self.tick_called = True

    def get_observation(self):
        return self._observation

    def get_raw_state(self):
        return self._raw_state


class TestExecutorScale:
    def test_scale_calls_world_scale_and_ticks(self):
        mock_world = MockWorld()
        action = ScaleAction(action_type="scale", deployment="frontend", replicas=3)
        result = execute(action, mock_world)

        assert mock_world.scale_called_with == ("frontend", 3)
        assert mock_world.tick_called is True
        assert result.tick_advanced is True
        assert "Scaled" in result.action_applied

    def test_scale_action_applied_message(self):
        mock_world = MockWorld()
        action = ScaleAction(action_type="scale", deployment="frontend", replicas=5)
        result = execute(action, mock_world)

        assert result.action_applied == "Scaled 'frontend' to 5 replicas"


class TestExecutorDeletePod:
    def test_delete_pod_calls_world_and_ticks(self):
        mock_world = MockWorld()
        action = DeletePodAction(action_type="delete_pod", pod_name="frontend-7d9f-xkp2")
        result = execute(action, mock_world)

        assert mock_world.delete_pod_called_with == "frontend-7d9f-xkp2"
        assert mock_world.tick_called is True
        assert result.tick_advanced is True


class TestExecutorPatch:
    def test_patch_calls_world_and_ticks(self):
        mock_world = MockWorld()
        action = PatchAction(
            action_type="patch",
            resource_type="deployment",
            name="frontend",
            patch={"env": [{"name": "DB_HOST", "value": "db.prod.internal"}]}
        )
        result = execute(action, mock_world)

        assert mock_world.apply_patch_called_with == (
            "deployment",
            "frontend",
            {"env": [{"name": "DB_HOST", "value": "db.prod.internal"}]}
        )
        assert mock_world.tick_called is True
        assert result.tick_advanced is True


class TestExecutorRolloutRestart:
    def test_rollout_restart_calls_world_and_ticks(self):
        mock_world = MockWorld()
        action = RolloutRestartAction(action_type="rollout_restart", deployment="frontend")
        result = execute(action, mock_world)

        assert mock_world.rollout_restart_called_with == "frontend"
        assert mock_world.tick_called is True
        assert result.tick_advanced is True


class TestExecutorSetHPA:
    def test_set_hpa_calls_world_and_ticks(self):
        mock_world = MockWorld()
        action = SetHPAAction(
            action_type="set_hpa",
            deployment="api",
            min_replicas=2,
            max_replicas=10,
            cpu_target_percent=70
        )
        result = execute(action, mock_world)

        assert mock_world.set_hpa_called_with == ("api", 2, 10, 70)
        assert mock_world.tick_called is True
        assert result.tick_advanced is True


class TestExecutorDrainNode:
    def test_drain_node_calls_world_and_ticks(self):
        mock_world = MockWorld()
        action = DrainNodeAction(action_type="drain_node", node_name="node-1")
        result = execute(action, mock_world)

        assert mock_world.drain_node_called_with == "node-1"
        assert mock_world.tick_called is True
        assert result.tick_advanced is True


class TestExecutorDescribe:
    def test_describe_does_not_tick(self):
        mock_world = MockWorld()
        action = DescribeAction(
            action_type="describe",
            resource_type="deployment",
            name="frontend"
        )
        result = execute(action, mock_world)

        assert mock_world.describe_called_with == ("deployment", "frontend")
        assert mock_world.tick_called is False
        assert result.tick_advanced is False

    def test_describe_returns_detail(self):
        mock_world = MockWorld()
        action = DescribeAction(
            action_type="describe",
            resource_type="deployment",
            name="frontend"
        )
        result = execute(action, mock_world)

        assert result.describe_detail is not None
        assert result.describe_detail["type"] == "deployment"
