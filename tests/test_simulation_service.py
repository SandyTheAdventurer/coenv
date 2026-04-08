import pytest

from server.simulation_service import (
    CoenvEnvironment,
    calculate_reward,
    check_task_complete,
    get_objective_for_task,
)
from models import CoenvAction


class StubPod:
    def __init__(self, deployment: str, status: str, restarts: int = 0):
        self.deployment = deployment
        self.status = status
        self.restarts = restarts


class StubHPA:
    def __init__(self, name: str, min_replicas: int, max_replicas: int, cpu_target_percent: int):
        self.name = name
        self.min_replicas = min_replicas
        self.max_replicas = max_replicas
        self.cpu_target_percent = cpu_target_percent


class StubWorld:
    def __init__(self, pods, hpas=None):
        self._pods = pods
        self._hpas = hpas or []

    def get_pods(self):
        return self._pods

    def get_hpas(self):
        return self._hpas


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

    reward = calculate_reward(world, "pod_recovery")
    assert reward == pytest.approx(2 / 3)


def test_calculate_reward_autoscaling_rewards_stability_and_hpa_policy():
    healthy_world = StubWorld(
        [
            StubPod("backend", "Running", restarts=0),
            StubPod("backend", "Running", restarts=0),
        ],
        hpas=[StubHPA("backend-hpa", min_replicas=2, max_replicas=6, cpu_target_percent=70)],
    )

    unstable_world = StubWorld(
        [
            StubPod("backend", "Running", restarts=10),
            StubPod("backend", "Running", restarts=9),
        ],
        hpas=[StubHPA("backend-hpa", min_replicas=2, max_replicas=6, cpu_target_percent=70)],
    )

    no_hpa_world = StubWorld(
        [
            StubPod("backend", "Running", restarts=0),
            StubPod("backend", "Running", restarts=0),
        ],
        hpas=[],
    )

    healthy_reward = calculate_reward(healthy_world, "autoscaling")
    unstable_reward = calculate_reward(unstable_world, "autoscaling")
    no_hpa_reward = calculate_reward(no_hpa_world, "autoscaling")

    assert healthy_reward == pytest.approx(1.0)
    assert unstable_reward < healthy_reward
    assert no_hpa_reward < healthy_reward


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
