"""
KubeSimEnv Utils - Probability helpers and simulation utilities
Random failure rate generators, latency simulators, resource usage curves.
Makes the simulation feel realistic and non-deterministic in the right ways.
"""

import random
import math
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta


class ProbabilityHelpers:
    """Helpers for generating realistic probabilities and distributions"""
    
    @staticmethod
    def weighted_random_choice(choices: List[Any], weights: List[float]) -> Any:
        """Make a weighted random choice"""
        if not choices or not weights or len(choices) != len(weights):
            return random.choice(choices) if choices else None
        
        # Normalize weights
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(choices)
        
        normalized_weights = [w / total_weight for w in weights]
        
        # Make choice
        r = random.random()
        cumulative_weight = 0
        for choice, weight in zip(choices, normalized_weights):
            cumulative_weight += weight
            if r <= cumulative_weight:
                return choice
        return choices[-1]  # Fallback
    
    @staticmethod
    def exponential_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 60.0) -> float:
        """Calculate exponential backoff delay"""
        delay = base_delay * (2 ** attempt)
        return min(delay, max_delay)
    
    @staticmethod
    def poisson_arrival_rate(lambda_rate: float, time_window: float) -> int:
        """Generate number of events in time window using Poisson distribution"""
        # Simple approximation - in reality would use numpy.random.poisson
        return int(lambda_rate * time_window + random.gauss(0, math.sqrt(lambda_rate * time_window)))
    
    @staticmethod
    def failure_probability_over_time(base_rate: float, time_elapsed: float, 
                                    max_rate: float = 1.0) -> float:
        """Calculate failure probability that increases over time"""
        probability = base_rate * (1 + math.log(1 + time_elapsed))
        return min(probability, max_rate)
    
    @staticmethod
    def random_failure_rate(min_rate: float = 0.1, max_rate: float = 0.9) -> float:
        """Generate a random failure rate within bounds"""
        return random.uniform(min_rate, max_rate)


class LatencySimulator:
    """Simulates network and service latency"""
    
    def __init__(self, base_latency_ms: float = 50.0):
        self.base_latency_ms = base_latency_ms
        self.load_factor = 1.0
        
    def set_load(self, load_factor: float):
        """Set system load factor (1.0 = normal, >1.0 = overloaded)"""
        self.load_factor = max(0.1, load_factor)
        
    def get_latency(self) -> float:
        """Get simulated latency in milliseconds"""
        # Base latency + load-dependent component + random jitter
        load_latency = self.base_latency_ms * (self.load_factor - 1.0) * 2
        jitter = random.gauss(0, self.base_latency_ms * 0.1)
        latency = self.base_latency_ms + max(0, load_latency) + jitter
        return max(1.0, latency)  # Minimum 1ms latency
    
    def get_latency_with_spike(self, spike_probability: float = 0.05, 
                             spike_multiplier: float = 5.0) -> float:
        """Get latency with occasional spikes"""
        latency = self.get_latency()
        if random.random() < spike_probability:
            latency *= spike_multiplier
        return latency


class ResourceUsageSimulator:
    """Simulates realistic CPU and memory usage patterns"""
    
    def __init__(self):
        self.time_offset = random.uniform(0, 2 * math.pi)
        
    def get_cpu_usage(self, base_usage: float = 0.3, 
                     variation: float = 0.2) -> float:
        """Get CPU usage as percentage (0-100)"""
        # Simulate daily patterns with some noise
        time_factor = (datetime.now().timestamp() / 3600) % 24  # Hours in day
        daily_pattern = 0.5 * math.sin(2 * math.pi * time_factor / 24) + 0.5
        
        usage = base_usage + variation * daily_pattern
        usage += random.gauss(0, 0.05)  # Noise
        return max(0.0, min(1.0, usage)) * 100  # Clamp to 0-100%
    
    def get_memory_usage(self, base_usage: float = 0.4,
                        variation: float = 0.15) -> float:
        """Get memory usage as percentage (0-100)"""
        # Memory usage tends to creep up over time (simulate leak)
        time_factor = min((datetime.now().timestamp() / 86400) % 7, 1.0)  # Weekly pattern
        leak_factor = 0.1 * time_factor  # Slow leak over week
        
        usage = base_usage + leak_factor
        usage += random.gauss(0, 0.03)  # Noise
        return max(0.0, min(1.0, usage)) * 100  # Clamp to 0-100%
    
    def get_resource_curve(self, resource_type: str, 
                          time_elapsed: float) -> float:
        """Get resource usage following a specific curve"""
        if resource_type == "cpu":
            # CPU: periodic with bursts
            return 0.3 + 0.4 * math.sin(time_elapsed / 100) + 0.2 * random.random()
        elif resource_type == "memory":
            # Memory: gradual increase with occasional GC drops
            base = 0.2 + 0.6 * (1 - math.exp(-time_elapsed / 1000))
            gc_drop = 0.3 if random.random() < 0.01 else 0  # Occasional GC
            return max(0, base - gc_drop)
        elif resource_type == "disk":
            # Disk: steady growth
            return 0.1 + 0.8 * min(time_elapsed / 10000, 1.0)
        else:
            return 0.5


class NetworkSimulator:
    """Simulates network conditions and partitions"""
    
    def __init__(self):
        self.partition_probability = 0.01
        self.latency_ms = 10.0
        self.bandwidth_mbps = 1000.0
        
    def simulate_partition(self) -> bool:
        """Return True if network partition is simulated"""
        return random.random() < self.partition_probability
    
    def get_latency(self) -> float:
        """Get network latency in milliseconds"""
        # Base latency with occasional spikes
        latency = self.latency_ms + random.gauss(0, self.latency_ms * 0.2)
        if random.random() < 0.05:  # 5% chance of spike
            latency *= random.uniform(2, 10)
        return max(1.0, latency)
    
    def get_bandwidth(self) -> float:
        """Get available bandwidth in Mbps"""
        # Bandwidth varies with usage and conditions
        usage_factor = random.uniform(0.3, 0.9)
        condition_factor = random.uniform(0.8, 1.2)
        return self.bandwidth_mbps * usage_factor * condition_factor


def generate_failure_scenario(config: Dict[str, Any]) -> Dict[str, Any]:
    """Generate a random failure scenario based on config"""
    scenario = {
        "type": random.choice(["crashloop", "oom", "node_failure", "cascade"]),
        "severity": random.uniform(0.3, 0.9),
        "duration": random.randint(30, 300),  # seconds
        "affected_components": []
    }
    
    # Add specific parameters based on type
    if scenario["type"] == "crashloop":
        scenario["failure_rate"] = config.get("crash_loop_failure_rate", 0.7)
    elif scenario["type"] == "oom":
        scenario["failure_rate"] = config.get("oom_kill_failure_rate", 0.6)
    elif scenario["type"] == "node_failure":
        scenario["failure_rate"] = config.get("node_failure_rate", 0.4)
    elif scenario["type"] == "cascade":
        scenario["probability"] = config.get("cascade_failure_probability", 0.5)
    
    return scenario


def apply_realistic_noise(value: float, noise_percent: float = 10.0) -> float:
    """Apply realistic noise to a value"""
    noise = random.gauss(0, value * (noise_percent / 100.0))
    return max(0, value + noise)