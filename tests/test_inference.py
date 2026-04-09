import pytest

from inference import (
    _clamp_open_unit_interval,
    _normalize_action,
    _safe_json_action,
    _task_fallback_action,
    log_end,
)


def test_normalize_action_maps_set_hpas_to_set_hpa():
    action = _normalize_action({"action_type": "set_hpas", "deployment": "backend"})

    assert action["action_type"] == "set_hpa"
    assert action["deployment"] == "backend"
    assert action["min_replicas"] == 2
    assert action["max_replicas"] == 6
    assert action["cpu_target_percent"] == 70


def test_normalize_action_non_string_type_defaults_to_describe():
    action = _normalize_action({"action_type": ["set_hpa"]})

    assert action["action_type"] == "describe"
    assert action["resource_type"] == "deployment"
    assert action["name"] == "frontend"


def test_normalize_action_maps_horizontalpodautoscaler_resource_type():
    action = _normalize_action(
        {
            "action_type": "describe",
            "resource_type": "horizontalpodautoscaler",
            "name": "backend-hpa",
        }
    )

    assert action["resource_type"] == "hpa"


def test_safe_json_action_handles_truncated_json():
    result = _safe_json_action('{"action_type": "ACK')
    assert result is None


def test_safe_json_action_extracts_valid_json_from_text():
    result = _safe_json_action(
        'We need to identify root cause. {"action_type": "describe", "resource_type": "pod"}'
    )
    assert result is not None
    assert result.get("action_type") == "describe"
    assert result.get("resource_type") == "pod"


def test_safe_json_action_handles_fenced_json():
    result = _safe_json_action(
        '```json\n{"action_type":"wait"}\n```'
    )
    assert result is not None
    assert result.get("action_type") == "wait"


def test_safe_json_action_handles_wrapped_action_object():
    result = _safe_json_action(
        '{"action": {"action_type": "describe", "resource_type": "deployment", "name": "frontend"}}'
    )
    assert result is not None
    assert result.get("action_type") == "describe"
    assert result.get("name") == "frontend"


def test_safe_json_action_handles_tool_call_like_shape():
    result = _safe_json_action(
        '{"name": "set_hpa", "arguments": "{\\"deployment\\": \\"backend\\", \\"min_replicas\\": 2, \\"max_replicas\\": 6, \\"cpu_target_percent\\": 70}"}'
    )
    assert result is not None
    assert result.get("action_type") == "set_hpa"
    assert result.get("deployment") == "backend"


def test_task_fallback_action_autoscaling_targets_backend():
    observation = {
        "deployments": [
            {"name": "frontend", "desired_replicas": 3, "available_replicas": 3},
            {"name": "backend", "desired_replicas": 2, "available_replicas": 1},
        ],
        "pods": [],
    }
    action = _task_fallback_action("autoscaling", step=1, observation=observation)

    assert action["action_type"] == "set_hpa"
    assert action["deployment"] == "backend"


def test_task_fallback_action_pod_recovery_describes_crashloop_pod_first():
    observation = {
        "deployments": [{"name": "frontend", "desired_replicas": 3, "available_replicas": 1}],
        "pods": [
            {"name": "frontend-123", "deployment": "frontend", "status": "CrashLoopBackOff"},
            {"name": "frontend-456", "deployment": "frontend", "status": "Running"},
        ],
    }
    action = _task_fallback_action("pod_recovery", step=1, observation=observation)

    assert action["action_type"] == "describe"
    assert action["resource_type"] == "pod"
    assert action["name"] == "frontend-123"


def test_clamp_open_unit_interval_is_strictly_inside_bounds():
    assert _clamp_open_unit_interval(0.0) == pytest.approx(0.0001)
    assert _clamp_open_unit_interval(1.0) == pytest.approx(0.9999)
    assert _clamp_open_unit_interval(0.42) == pytest.approx(0.42)


def test_log_end_emits_non_boundary_score(capsys):
    log_end(success=True, steps=3, score=1.0, rewards=[0.0, 0.0, 1.0])
    output = capsys.readouterr().out.strip()

    assert "score=0.9999" in output
