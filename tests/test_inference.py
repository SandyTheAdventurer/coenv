from inference import _normalize_action


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
