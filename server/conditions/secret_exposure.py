"""
SecurityCondition - Simulates exposed secrets in env vars
"""

from typing import Dict, Any, Optional
from ..coenv_environment import World
from datetime import datetime
from ..models import ClusterEvent


class SecurityCondition:
    """Injects security vulnerabilities (exposed secrets)"""

    def __init__(self, world: World, config: Dict[str, Any]):
        self.world = world
        self.config = config

    def inject(
        self,
        target_deployment: Optional[str] = None,
        failure_rate: Optional[float] = None,
    ):
        """Inject exposed secrets into deployment ConfigMaps/env vars"""
        deployments = self.world.cluster_state["deployments"]

        if target_deployment:
            target_deps = [d for d in deployments if d["name"] == target_deployment]
        else:
            target_deps = [self.world.rng.choice(deployments)] if deployments else []

        exposed_secrets = [
            {"key": "API_KEY", "value": "sk_live_abc123xyz"},
            {"key": "DB_PASSWORD", "value": "p@ssw0rd_secret"},
            {"key": "JWT_SECRET", "value": "super_secret_key_123"},
        ]

        for deployment in target_deps:
            configmaps = self.world.cluster_state["configmaps"]
            for cm in configmaps:
                if cm["name"] == f"{deployment['name']}-config":
                    cm["data"].update({s["key"]: s["value"] for s in exposed_secrets})
                    cm["last_updated"] = datetime.now().isoformat()

            self.world.inject_failure_condition(
                deployment["name"], "security_exposed", 1.0
            )

        for svc in ["auth-service", "api-gateway"]:
            found = next((d for d in deployments if d["name"] == svc), None)
            if found:
                self.world.inject_failure_condition(svc, "security_exposed", 1.0)
                break

        event = ClusterEvent(
            event_id=f"event-secscan-{int(self.world.rng.integers(1000, 10000))}",
            timestamp=datetime.now().isoformat(),
            type="Error",
            reason="SecurityAlert",
            message="Security scan found exposed credentials in ConfigMaps",
            involved_object="configmaps",
        )
        self.world.events.append(event)
