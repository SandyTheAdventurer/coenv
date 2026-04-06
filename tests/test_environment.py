"""
Test - Environment (from test_world.py)
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'server'))

from COEnv_environment import World


def test_world_initialization():
    """Test that the world initializes correctly"""
    config = {
        "num_nodes": 2,
        "node_cpu_capacity": 4,
        "node_mem_capacity": 8192,
        "pod_cpu_request": 250,
        "pod_mem_request": 128,
        "pod_cpu_limit": 500,
        "pod_mem_limit": 256,
    }
    
    world = World(config)
    print("World initialized successfully")
    
    nodes = world.get_nodes()
    pods = world.get_pods()
    deployments = world.get_deployments()
    services = world.get_services()
    
    print(f"Nodes: {len(nodes)}")
    print(f"Pods: {len(pods)}")
    print(f"Deployments: {len(deployments)}")
    print(f"Services: {len(services)}")
    
    assert len(nodes) == 2
    assert len(pods) > 0
    assert len(deployments) > 0
    assert len(services) > 0
    
    print("All tests passed!")


if __name__ == "__main__":
    test_world_initialization()
