import pytest

from server.simulation_service import (
    CoenvEnvironment,
    calculate_reward,
    check_task_complete,
    get_objective_for_task,
    shape_reward,
)
from models import CoenvAction


class StubPod:
    def __init__(self, deployment: str, status: str, restarts: int = 0):
        self.deployment = deployment
        self.status = status
        self.restarts = restarts


class StubDeployment:
    def __init__(self, name: str, desired_replicas: int, available_replicas: int):
        self.name = name
        self.desired_replicas = desired_replicas
        self.available_replicas = available_replicas


class StubHPA:
    def __init__(
        self, name: str, min_replicas: int, max_replicas: int, cpu_target_percent: int
    ):
        self.name = name
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.cpu_target_percent = cpu_target_percent


class StubWorld:
    def __init__(self, pods, deployments=None, hpas=None):
        self._pods = pods
        self._deployments = deployments or [
            StubDeployment("frontend", 3, 3),
            StubDeployment("backend", 2, 2),
        ]
        self._hpas = hpas or []
        self._step_count = 1

    def get_pods(self):
        return self._pods

    def get_deployments(self):
        return self._deployments

    def get_hpas(self):
        return self._hpas

    def get_full_state(self):
        return {
            "pods": [
                {"deployment": p.deployment, "status": p.status, "restarts": p.restarts}
                for p in self._pods
            ],
            "deployments": [
                {
                    "name": d.name,
                    "desired_replicas": d.desired_replicas,
                    "available_replicas": d.available_replicas,
                }
                for d in self._deployments
            ],
            "hpas": [
                {
                    "name": h.name,
                    "min_replicas": h.min_replicas,
                    "max_replicas": h.max_replicas,
                    "cpu_target_percent": h.cpu_target_percent,
                }
                for h in self._hpas
            ],
        }


def test_get_objective_for_task_known_and_unknown():
    known = get_objective_for_task("pod_recovery")
    unknown = get_objective_for_task("unknown-task")

    assert "crash-looping" in known
    assert unknown == "Maintain cluster health"


def test_calculate_reward_pod_recovery():
    world = StubWorld(
        [
            StubPod("frontend", "Running"),
            StubPod("frontend", "Running"),
            StubPod("frontend", "CrashLoopBackOff"),
        ]
    )

    reward = calculate_reward(world, "pod_recovery", step=0, max_steps=15)
    assert 0.32 < reward < 0.35


def test_calculate_reward_autoscaling_rewards_stability_and_hpa_policy():
    healthy_world = StubWorld(
        [
            StubPod("backend", "Running", restarts=0),
            StubPod("backend", "Running", restarts=0),
        ],
        deployments=[
            StubDeployment("backend", desired_replicas=2, available_replicas=2),
            StubDeployment("frontend", desired_replicas=3, available_replicas=3),
        ],
        hpas=[
            StubHPA(
                "backend-hpa", min_replicas=2, max_replicas=6, cpu_target_percent=70
            )
        ],
    )

    unstable_world = StubWorld(
        [
            StubPod("backend", "Running", restarts=10),
            StubPod("backend", "Running", restarts=9),
        ],
        deployments=[
            StubDeployment("backend", desired_replicas=2, available_replicas=2),
            StubDeployment("frontend", desired_replicas=3, available_replicas=3),
        ],
        hpas=[
            StubHPA(
                "backend-hpa", min_replicas=2, max_replicas=6, cpu_target_percent=70
            )
        ],
    )

    no_hpa_world = StubWorld(
        [
            StubPod("backend", "Running", restarts=0),
            StubPod("backend", "Running", restarts=0),
        ],
        deployments=[
            StubDeployment("backend", desired_replicas=2, available_replicas=2),
            StubDeployment("frontend", desired_replicas=3, available_replicas=3),
        ],
        hpas=[],
    )

    healthy_reward = calculate_reward(
        healthy_world, "autoscaling", step=1, max_steps=20
    )
    unstable_reward = calculate_reward(
        unstable_world, "autoscaling", step=1, max_steps=20
    )
    no_hpa_reward = calculate_reward(no_hpa_world, "autoscaling", step=1, max_steps=20)

    assert healthy_reward >= 0.7
    assert unstable_reward < healthy_reward
    assert no_hpa_reward < healthy_reward


def test_shape_reward_boosts_improvement_and_penalizes_regression():
    improved = shape_reward(
        base_reward=0.70,
        previous_base_reward=0.40,
        action_type="scale",
    )
    regressed = shape_reward(
        base_reward=0.40,
        previous_base_reward=0.70,
        action_type="scale",
    )

    assert improved > 0.70
    assert regressed < 0.40


def test_shape_reward_penalizes_passive_invalid_and_error_actions():
    valid_reward = shape_reward(
        base_reward=0.60,
        previous_base_reward=0.60,
        action_type="scale",
    )
    passive_reward = shape_reward(
        base_reward=0.60,
        previous_base_reward=0.60,
        action_type="wait",
    )
    invalid_reward = shape_reward(
        base_reward=0.60,
        previous_base_reward=0.60,
        action_type="scale",
        invalid_action=True,
    )
    error_reward = shape_reward(
        base_reward=0.60,
        previous_base_reward=0.60,
        action_type="scale",
        had_error=True,
    )

    assert passive_reward < valid_reward
    assert invalid_reward < passive_reward
    assert error_reward < valid_reward


def test_shape_reward_can_be_negative_for_severe_regression():
    severe_penalty = shape_reward(
        base_reward=0.05,
        previous_base_reward=0.95,
        action_type="wait",
        invalid_action=True,
        had_error=True,
    )

    assert severe_penalty < 0.0


def test_check_task_complete_incident_true_and_false():
    healthy_world = StubWorld(
        [
            StubPod("auth-service", "Running"),
            StubPod("api-gateway", "Running"),
            StubPod("frontend", "Running"),
        ]
    )
    unhealthy_world = StubWorld(
        [
            StubPod("auth-service", "Running"),
            StubPod("api-gateway", "CrashLoopBackOff"),
            StubPod("frontend", "Running"),
        ]
    )

    assert check_task_complete(healthy_world, "incident") is True
    assert check_task_complete(unhealthy_world, "incident") is False


def test_environment_reset_sets_task_and_returns_observation():
    env = CoenvEnvironment()

    obs = env.reset(task="autoscaling")

    assert env.current_task == "autoscaling"
    assert obs.objective == env.current_objective
    assert obs.done is False
    assert obs.reward == 0.0
    assert "task" in obs.metadata


def test_environment_step_scale_and_describe_paths():
    env = CoenvEnvironment()
    env.reset(task="pod_recovery")

    scale_obs = env.step(
        CoenvAction(action_type="scale", deployment="frontend", replicas=4)
    )
    assert "scaled" in scale_obs.metadata
    assert scale_obs.step >= 1

    describe_obs = env.step(
        CoenvAction(action_type="describe", resource_type="deployment", name="frontend")
    )
    assert "described" in describe_obs.metadata
    assert "describe_detail" in describe_obs.metadata

    wait_obs = env.step(CoenvAction(action_type="wait"))
    assert wait_obs.metadata.get("waited") is True


def test_environment_step_exception_is_captured_in_metadata(monkeypatch):
    env = CoenvEnvironment()
    env.reset(task="pod_recovery")

    def _boom(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(env.world, "scale", _boom)

    action = CoenvAction(action_type="scale", deployment="frontend", replicas=2)

    obs = env.step(action)
    assert "error" in obs.metadata
    assert "forced failure" in obs.metadata["error"]


def test_environment_invalid_action_advances_step_and_sets_metadata():
    env = CoenvEnvironment()
    env.reset(task="pod_recovery")

    initial_step = env.world.step_count
    obs = env.step(
        CoenvAction(action_type="describe", resource_type="pod", name="missing-pod")
    )

    assert obs.metadata.get("invalid_action") is True
    assert "error" in obs.metadata
    assert "not found" in obs.metadata["error"]
    assert env.world.step_count == initial_step + 1
    assert obs.step == initial_step + 1
