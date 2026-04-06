import pytest

from server.COEnv_environment import World
from server.models import ClusterEvent


@pytest.fixture
def world() -> World:
    return World({"num_nodes": 3})


def test_world_seed_makes_initial_state_deterministic():
    config = {"num_nodes": 3}
    world_a = World(config, seed=12345)
    world_b = World(config, seed=12345)

    pod_names_a = [p["name"] for p in world_a.cluster_state["pods"]]
    pod_names_b = [p["name"] for p in world_b.cluster_state["pods"]]

    assert pod_names_a == pod_names_b


def test_get_pods_filters_by_namespace_and_selector(world: World):
    world.cluster_state["pods"].append(
        {
            "name": "custom-frontend-pod",
            "namespace": "staging",
            "status": "Running",
            "node": "node-1",
            "restarts": 0,
            "cpu_request": 100,
            "mem_request": 128,
            "cpu_limit": 200,
            "mem_limit": 256,
            "deployment": "frontend",
            "labels": {"tier": "web", "app": "frontend"},
            "last_updated": "2026-04-06T00:00:00",
        }
    )

    staging_frontend = world.get_pods(namespace="staging", selector={"app": "frontend"})
    assert len(staging_frontend) == 1
    assert staging_frontend[0].name == "custom-frontend-pod"

    by_custom_label = world.get_pods(namespace="staging", selector={"tier": "web"})
    assert len(by_custom_label) == 1
    assert by_custom_label[0].deployment == "frontend"

    no_match = world.get_pods(namespace="prod", selector={"tier": "web"})
    assert no_match == []


def test_set_hpa_updates_existing_and_clamps_deployment_replicas(world: World):
    world.scale("backend", 12)

    updated = world.set_hpa("backend", min_replicas=2, max_replicas=5, cpu_target_percent=65)
    assert updated is True

    backend_dep = next(d for d in world.cluster_state["deployments"] if d["name"] == "backend")
    backend_hpa = next(h for h in world.cluster_state["hpas"] if h["name"] == "backend-hpa")

    assert backend_dep["desired_replicas"] == 5
    assert backend_hpa["min_replicas"] == 2
    assert backend_hpa["max_replicas"] == 5
    assert backend_hpa["cpu_target_percent"] == 65
    assert backend_hpa["current_replicas"] == 5

    hpa_events = [e for e in world.events if e.reason == "HorizontalPodAutoscalerUpdated" and e.involved_object == "backend"]
    assert len(hpa_events) >= 1


def test_drain_node_evicts_and_reassigns_pods(world: World):
    target_node = "node-1"
    pods_on_node_before = [p for p in world.cluster_state["pods"] if p.get("node") == target_node]
    assert len(pods_on_node_before) > 0

    drained = world.drain_node(target_node)
    assert drained is True

    node = next(n for n in world.cluster_state["nodes"] if n["name"] == target_node)
    assert node["status"] == "SchedulingDisabled"

    pods_with_original_names = {
        p["name"] for p in pods_on_node_before
    }
    pods_after = [p for p in world.cluster_state["pods"] if p["name"] in pods_with_original_names]

    assert len(pods_after) == len(pods_on_node_before)
    assert all(p["status"] == "Pending" for p in pods_after)
    assert all(p.get("node") != target_node for p in pods_after)


def test_drain_node_with_no_ready_targets_unassigns_pods(world: World):
    for node in world.cluster_state["nodes"]:
        if node["name"] != "node-1":
            node["status"] = "NotReady"

    pods_on_node_before = [p for p in world.cluster_state["pods"] if p.get("node") == "node-1"]
    assert len(pods_on_node_before) > 0

    drained = world.drain_node("node-1")
    assert drained is True

    names = {p["name"] for p in pods_on_node_before}
    pods_after = [p for p in world.cluster_state["pods"] if p["name"] in names]
    assert all(p.get("node") is None for p in pods_after)
    assert all(p["status"] == "Pending" for p in pods_after)


def test_describe_deployment_includes_related_pods_and_recent_events(world: World):
    for i in range(12):
        world.events.append(
            ClusterEvent(
                event_id=f"event-frontend-{i}",
                timestamp="2026-04-06T00:00:00",
                type="Normal",
                reason="TestEvent",
                message=f"frontend event {i}",
                involved_object="frontend",
            )
        )

    detail = world.describe("deployment", "frontend")

    assert detail["found"] is True
    assert detail["name"] == "frontend"
    assert detail["type"] == "deployment"
    assert all(p.get("deployment") == "frontend" for p in detail["related_pods"])
    assert len(detail["recent_events"]) == 10
    assert all(evt["involved_object"] == "frontend" for evt in detail["recent_events"])


def test_describe_unsupported_or_missing_resource(world: World):
    unsupported = world.describe("secret", "top-secret")
    assert unsupported["found"] is False
    assert "Unsupported resource_type" in unsupported["error"]

    missing = world.describe("service", "does-not-exist")
    assert missing["found"] is False
    assert "not found" in missing["error"]