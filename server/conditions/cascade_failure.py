"""
CascadeFailureCondition - Simulates multi-service dependency failure
"""

from typing import Dict, Any, Optional
from ..coenv_environment import World


class CascadeFailureCondition:
    """Injects cascading failures across multiple services"""

    def __init__(self, world: World, config: Dict[str, Any]):
        self.world = world
        self.config = config

    def inject(
        self,
        root_cause_service: Optional[str] = None,
        failure_probability: Optional[float] = None,
    ):
        """
        Inject cascading failures starting from a root cause service

        Args:
            root_cause_service: Specific service to start failure (None for random)
            failure_probability: Probability of failure propagating to dependencies (0.0-1.0)
        """
        if failure_probability is None:
            failure_probability = self.config.get("cascade_failure_probability", 0.7)
        else:
            failure_probability = float(failure_probability)

        if root_cause_service is None:
            critical_services = ["auth-service", "database", "api-gateway"]
            deployments = self.world.get_deployments()
            critical_deployments = [
                d for d in deployments if d.name in critical_services
            ]
            if critical_deployments:
                root_cause_service = self.world.rng.choice(critical_deployments).name
            else:
                deployments = self.world.get_deployments()
                root_cause_service = (
                    self.world.rng.choice(deployments).name
                    if deployments
                    else "frontend"
                )

        root_deployment = next(
            (d for d in self.world.get_deployments() if d.name == root_cause_service),
            None,
        )
        if root_deployment:
            from .oom_kill import OOMKillCondition

            oom_condition = OOMKillCondition(self.world, self.config)
            oom_condition.inject(target_deployment=root_cause_service, failure_rate=0.8)

            self._add_cascade_event(
                f"Root cause failure in {root_cause_service}", "Warning"
            )

        deployments = self.world.get_deployments()
        for deployment in deployments:
            if (
                deployment.name != root_cause_service
                and failure_probability is not None
                and float(self.world.rng.random()) < failure_probability
            ):
                failure_type = str(self.world.rng.choice(["crashloop", "oom", "slow"]))

                if failure_type == "crashloop":
                    from .crash_loop import CrashLoopCondition

                    condition = CrashLoopCondition(self.world, self.config)
                    condition.inject(
                        target_deployment=deployment.name, failure_rate=0.6
                    )
                elif failure_type == "oom":
                    from .oom_kill import OOMKillCondition

                    condition = OOMKillCondition(self.world, self.config)
                    condition.inject(
                        target_deployment=deployment.name, failure_rate=0.6
                    )
                else:
                    pods = [
                        p
                        for p in self.world.get_pods()
                        if p.deployment == deployment.name
                    ]
                    for pod in pods[:1]:
                        patch = {
                            "cpu_request": int(pod.cpu_request * 1.5)
                            if pod.cpu_request
                            else 750,
                            "mem_request": int(pod.mem_request * 1.5)
                            if pod.mem_request
                            else 384,
                        }
                        self.world.apply_patch("pod", pod.name, patch)

                self._add_cascade_event(
                    f"Cascading failure detected in {deployment.name}", "Warning"
                )

    def _add_cascade_event(self, message: str, event_type: str):
        """Add a cascade failure event"""
        from ..models import ClusterEvent
        from datetime import datetime

        event = ClusterEvent(
            event_id=f"event-cascade-{int(self.world.rng.integers(1000, 10000))}",
            timestamp=datetime.now().isoformat(),
            type=event_type,
            reason="CascadeFailure",
            message=message,
            involved_object="cluster",
        )
        self.world.events.append(event)
