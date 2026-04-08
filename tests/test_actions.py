import pytest
from pydantic import ValidationError
from server.actions import (
    ScaleAction,
    PatchAction,
    DeletePodAction,
    RolloutRestartAction,
    SetHPAAction,
    DrainNodeAction,
    DescribeAction,
    WaitAction,
    parse_action,
)


class TestScaleAction:
    def test_valid_scale_action(self):
        action = ScaleAction(action_type="scale", deployment="frontend", replicas=3)
        assert action.deployment == "frontend"
        assert action.replicas == 3

    def test_scale_action_rejects_zero_replicas(self):
        with pytest.raises(ValidationError):
            ScaleAction(action_type="scale", deployment="frontend", replicas=0)

    def test_scale_action_rejects_negative_replicas(self):
        with pytest.raises(ValidationError):
            ScaleAction(action_type="scale", deployment="frontend", replicas=-1)

    def test_scale_action_rejects_too_many_replicas(self):
        with pytest.raises(ValidationError):
            ScaleAction(action_type="scale", deployment="frontend", replicas=21)

    def test_scale_action_accepts_boundary_values(self):
        action_min = ScaleAction(action_type="scale", deployment="frontend", replicas=1)
        action_max = ScaleAction(action_type="scale", deployment="frontend", replicas=20)
        assert action_min.replicas == 1
        assert action_max.replicas == 20


class TestPatchAction:
    def test_valid_patch_action(self):
        action = PatchAction(
            action_type="patch",
            resource_type="deployment",
            name="frontend",
            patch={"env": [{"name": "DB_HOST", "value": "db.prod.internal"}]}
        )
        assert action.resource_type == "deployment"
        assert action.name == "frontend"

    def test_patch_action_rejects_invalid_resource_type(self):
        with pytest.raises(ValidationError):
            PatchAction(
                action_type="patch",
                resource_type="invalid",
                name="frontend",
                patch={}
            )


class TestDeletePodAction:
    def test_valid_delete_pod_action(self):
        action = DeletePodAction(action_type="delete_pod", pod_name="frontend-7d9f-xkp2")
        assert action.pod_name == "frontend-7d9f-xkp2"


class TestRolloutRestartAction:
    def test_valid_rollout_restart_action(self):
        action = RolloutRestartAction(action_type="rollout_restart", deployment="frontend")
        assert action.deployment == "frontend"


class TestSetHPAAction:
    def test_valid_hpa_action(self):
        action = SetHPAAction(
            action_type="set_hpa",
            deployment="api",
            min_replicas=2,
            max_replicas=10,
            cpu_target_percent=70
        )
        assert action.deployment == "api"
        assert action.min_replicas == 2
        assert action.max_replicas == 10

    def test_hpa_action_rejects_max_less_than_min(self):
        with pytest.raises(ValidationError):
            SetHPAAction(
                action_type="set_hpa",
                deployment="api",
                min_replicas=5,
                max_replicas=2,
                cpu_target_percent=60
            )

    def test_hpa_action_rejects_invalid_cpu_target(self):
        with pytest.raises(ValidationError):
            SetHPAAction(
                action_type="set_hpa",
                deployment="api",
                min_replicas=1,
                max_replicas=10,
                cpu_target_percent=5
            )

    def test_hpa_action_accepts_boundary_cpu_target(self):
        action_min = SetHPAAction(
            action_type="set_hpa",
            deployment="api",
            min_replicas=1,
            max_replicas=10,
            cpu_target_percent=10
        )
        action_max = SetHPAAction(
            action_type="set_hpa",
            deployment="api",
            min_replicas=1,
            max_replicas=10,
            cpu_target_percent=90
        )
        assert action_min.cpu_target_percent == 10
        assert action_max.cpu_target_percent == 90


class TestDrainNodeAction:
    def test_valid_drain_node_action(self):
        action = DrainNodeAction(action_type="drain_node", node_name="node-1")
        assert action.node_name == "node-1"


class TestDescribeAction:
    def test_valid_describe_action(self):
        action = DescribeAction(
            action_type="describe",
            resource_type="deployment",
            name="frontend"
        )
        assert action.resource_type == "deployment"
        assert action.name == "frontend"

    def test_describe_action_rejects_invalid_resource_type(self):
        with pytest.raises(ValidationError):
            DescribeAction(
                action_type="describe",
                resource_type="invalid",
                name="frontend"
            )


class TestParseAction:
    def test_parse_scale_action(self):
        raw = {"action_type": "scale", "deployment": "frontend", "replicas": 3}
        action = parse_action(raw)
        assert isinstance(action, ScaleAction)
        assert action.deployment == "frontend"
        assert action.replicas == 3

    def test_parse_delete_pod_action(self):
        raw = {"action_type": "delete_pod", "pod_name": "frontend-7d9f-xkp2"}
        action = parse_action(raw)
        assert isinstance(action, DeletePodAction)
        assert action.pod_name == "frontend-7d9f-xkp2"

    def test_parse_patch_action(self):
        raw = {
            "action_type": "patch",
            "resource_type": "deployment",
            "name": "frontend",
            "patch": {"env": [{"name": "DB_HOST", "value": "db.prod.internal"}]}
        }
        action = parse_action(raw)
        assert isinstance(action, PatchAction)
        assert action.name == "frontend"

    def test_parse_rollout_restart_action(self):
        raw = {"action_type": "rollout_restart", "deployment": "frontend"}
        action = parse_action(raw)
        assert isinstance(action, RolloutRestartAction)
        assert action.deployment == "frontend"

    def test_parse_hpa_action(self):
        raw = {
            "action_type": "set_hpa",
            "deployment": "api",
            "min_replicas": 2,
            "max_replicas": 10,
            "cpu_target_percent": 70
        }
        action = parse_action(raw)
        assert isinstance(action, SetHPAAction)
        assert action.deployment == "api"

    def test_parse_drain_node_action(self):
        raw = {"action_type": "drain_node", "node_name": "node-1"}
        action = parse_action(raw)
        assert isinstance(action, DrainNodeAction)
        assert action.node_name == "node-1"

    def test_parse_describe_action(self):
        raw = {"action_type": "describe", "resource_type": "deployment", "name": "frontend"}
        action = parse_action(raw)
        assert isinstance(action, DescribeAction)
        assert action.name == "frontend"

    def test_parse_wait_action(self):
        raw = {"action_type": "wait"}
        action = parse_action(raw)
        assert isinstance(action, WaitAction)

    def test_parse_unknown_action_type(self):
        with pytest.raises(ValueError, match="Unknown action_type"):
            parse_action({"action_type": "unknown_action"})

    def test_parse_missing_action_type(self):
        with pytest.raises(ValueError, match="Missing 'action_type'"):
            parse_action({"deployment": "frontend"})
