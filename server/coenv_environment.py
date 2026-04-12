"""
coenv Environment - Cluster Simulator
In-memory dict that holds cluster state: nodes, pods, deployments, services.
Has methods like get_pods(), apply_patch(), tick() to advance time.
This is the brain of the whole project.
"""

from typing import Dict, List, Any, Optional, Literal
from datetime import datetime
import numpy as np

from .models import (
    NodeStatus,
    PodStatus,
    DeploymentStatus,
    ServiceStatus,
    ClusterEvent,
    ClusterObservation,
    ConfigMapStatus,
    HPAStatus,
    SecretStatus,
    IngressStatus,
    PVStatus,
    PVCStatus,
    PodLog,
    ResourceMetric,
)
from .utils import set_random_seed


class World:
    """In-memory Kubernetes cluster simulator"""

    def __init__(self, config: Dict[str, Any], seed: Optional[int] = None):
        self.config = config
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        set_random_seed(seed)
        self.cluster_state = self._initialize_healthy_cluster()
        self.step_count = 0
        self.events = []
        self._event_counter = 0
        self._injected_failures: Dict[str, Dict[str, Any]] = {}

    def _random_suffix(self, length: int = 5) -> str:
        """Generate a random lowercase alphabetic suffix."""
        letters = self.rng.integers(97, 123, size=length)
        return "".join(chr(int(code)) for code in letters)

    def _initialize_healthy_cluster(self) -> Dict[str, List[Dict]]:
        """Initialize a healthy cluster state based on config"""
        nodes = []
        for i in range(self.config.get("num_nodes", 3)):
            nodes.append(
                {
                    "name": f"node-{i + 1}",
                    "status": "Ready",
                    "cpu_capacity": self.config.get("node_cpu_capacity", 4),
                    "mem_capacity": self.config.get("node_mem_capacity", 8192),
                    "cpu_usage": 0.0,
                    "mem_usage": 0.0,
                    "last_updated": datetime.now().isoformat(),
                }
            )

        pods = []
        deployments = []
        services = []
        configmaps = []
        secrets = []
        ingresses = []
        persistentvolumes = []
        persistentvolumeclaims = []
        hpas = []

        # Create some default deployments and their pods
        default_deployments = [
            {"name": "frontend", "image": "nginx:1.21", "replicas": 3},
            {"name": "backend", "image": "python:3.9", "replicas": 2},
            {"name": "database", "image": "postgres:13", "replicas": 1},
            {"name": "auth-service", "image": "auth:latest", "replicas": 2},
            {"name": "api-gateway", "image": "nginx:alpine", "replicas": 2},
        ]

        for dep in default_deployments:
            deployments.append(
                {
                    "name": dep["name"],
                    "desired_replicas": dep["replicas"],
                    "available_replicas": dep["replicas"],
                    "image": dep["image"],
                    "last_updated": datetime.now().isoformat(),
                }
            )

            # Create pods for this deployment
            for j in range(dep["replicas"]):
                pod_name = f"{dep['name']}-{int(self.rng.integers(1000, 10000))}-{self._random_suffix()}"
                pods.append(
                    {
                        "name": pod_name,
                        "status": "Running",
                        "node": nodes[j % len(nodes)]["name"] if nodes else None,
                        "restarts": 0,
                        "cpu_request": self.config.get("pod_cpu_request", 500),
                        "mem_request": self.config.get("pod_mem_request", 256),
                        "cpu_limit": self.config.get("pod_cpu_limit", 1000),
                        "mem_limit": self.config.get("pod_mem_limit", 512),
                        "deployment": dep["name"],
                        "last_updated": datetime.now().isoformat(),
                    }
                )

        # Create some default services
        default_services = [
            {
                "name": "frontend-service",
                "type": "ClusterIP",
                "ports": [{"port": 80, "targetPort": 80}],
            },
            {
                "name": "backend-service",
                "type": "ClusterIP",
                "ports": [{"port": 8080, "targetPort": 8080}],
            },
            {
                "name": "database-service",
                "type": "ClusterIP",
                "ports": [{"port": 5432, "targetPort": 5432}],
            },
            {
                "name": "auth-service-service",
                "type": "ClusterIP",
                "ports": [{"port": 8000, "targetPort": 8000}],
            },
        ]

        for svc in default_services:
            services.append(
                {
                    "name": svc["name"],
                    "type": svc["type"],
                    "ports": svc["ports"],
                    "selector": {"app": svc["name"].replace("-service", "")},
                    "cluster_ip": f"10.96.{len(services) + 1}.{len(services) + 1}",
                    "last_updated": datetime.now().isoformat(),
                }
            )

        # Create some default configmaps
        default_configmaps = [
            {
                "name": "frontend-config",
                "data": {"DB_HOST": "db.prod.internal", "DB_PORT": "5432"},
            },
            {
                "name": "backend-config",
                "data": {"LOG_LEVEL": "info", "CACHE_SIZE": "100"},
            },
            {
                "name": "database-config",
                "data": {"MAX_CONNECTIONS": "100", "TIMEOUT": "30"},
            },
        ]

        for cm in default_configmaps:
            configmaps.append(
                {
                    "name": cm["name"],
                    "data": cm["data"],
                    "last_updated": datetime.now().isoformat(),
                }
            )

        # Create some default HPAs
        default_hpas = [
            {
                "name": "frontend-hpa",
                "min_replicas": 2,
                "max_replicas": 10,
                "cpu_target_percent": 70,
            },
            {
                "name": "backend-hpa",
                "min_replicas": 1,
                "max_replicas": 5,
                "cpu_target_percent": 80,
            },
        ]

        for hpa in default_hpas:
            hpas.append(
                {
                    "name": hpa["name"],
                    "min_replicas": hpa["min_replicas"],
                    "max_replicas": hpa["max_replicas"],
                    "current_replicas": hpa["min_replicas"],
                    "cpu_target_percent": hpa["cpu_target_percent"],
                    "last_updated": datetime.now().isoformat(),
                }
            )

        # Create secrets
        default_secrets = [
            {
                "name": "db-credentials",
                "type": "Opaque",
                "data": {"username": "admin", "password": "c2VjcmV0"},
            },
            {
                "name": "tls-cert",
                "type": "kubernetes.io/tls",
                "data": {"cert": "LS0tLS1CR", "key": "LS0tLS1GSU"},
            },
        ]
        for sec in default_secrets:
            secrets.append(
                {
                    "name": sec["name"],
                    "type": sec["type"],
                    "data": sec["data"],
                    "last_updated": datetime.now().isoformat(),
                }
            )

        # Create ingresses
        default_ingresses = [
            {
                "name": "frontend-ingress",
                "host": "app.example.com",
                "service_name": "frontend-service",
                "service_port": 80,
                "tls_enabled": True,
            },
        ]
        for ing in default_ingresses:
            ingresses.append(
                {
                    "name": ing["name"],
                    "namespace": "default",
                    "host": ing["host"],
                    "service_name": ing["service_name"],
                    "service_port": ing["service_port"],
                    "tls_enabled": ing["tls_enabled"],
                    "annotations": {"ingress.class": "nginx"},
                    "last_updated": datetime.now().isoformat(),
                }
            )

        # Create PVs and PVCs
        pv1 = {
            "name": "pv-database",
            "capacity": 10240,
            "access_modes": ["ReadWriteOnce"],
            "reclaim_policy": "Retain",
            "status": "Bound",
            "claim_ref": "database-pvc",
            "last_updated": datetime.now().isoformat(),
        }
        persistentvolumes.append(pv1)
        pv2 = {
            "name": "pv-logs",
            "capacity": 5120,
            "access_modes": ["ReadWriteMany"],
            "reclaim_policy": "Delete",
            "status": "Available",
            "claim_ref": None,
            "last_updated": datetime.now().isoformat(),
        }
        persistentvolumes.append(pv2)

        pvc1 = {
            "name": "database-pvc",
            "namespace": "default",
            "size": 10240,
            "access_modes": ["ReadWriteOnce"],
            "status": "Bound",
            "volume_name": "pv-database",
            "last_updated": datetime.now().isoformat(),
        }
        persistentvolumeclaims.append(pvc1)

        return {
            "nodes": nodes,
            "pods": pods,
            "deployments": deployments,
            "services": services,
            "configmaps": configmaps,
            "secrets": secrets,
            "ingresses": ingresses,
            "persistentvolumes": persistentvolumes,
            "persistentvolumeclaims": persistentvolumeclaims,
            "hpas": hpas,
        }

    def get_pods(
        self, namespace: Optional[str] = None, selector: Optional[Dict[str, str]] = None
    ) -> List[PodStatus]:
        """Returns filtered pod list (mimics kubectl get pods)"""
        filtered_pods = self.cluster_state["pods"]

        if namespace is not None:
            filtered_pods = [
                pod
                for pod in filtered_pods
                if pod.get("namespace", "default") == namespace
            ]

        if selector:
            for key, value in selector.items():
                if key in {"app", "deployment"}:
                    filtered_pods = [
                        pod for pod in filtered_pods if pod.get("deployment") == value
                    ]
                else:
                    filtered_pods = [
                        pod
                        for pod in filtered_pods
                        if pod.get("labels", {}).get(key) == value
                    ]

        return [PodStatus(**pod) for pod in filtered_pods]

    def get_nodes(self) -> List[NodeStatus]:
        """Get all nodes as Pydantic models"""
        return [NodeStatus(**node) for node in self.cluster_state["nodes"]]

    def get_deployments(self) -> List[DeploymentStatus]:
        """Get all deployments as Pydantic models"""
        return [DeploymentStatus(**dep) for dep in self.cluster_state["deployments"]]

    def get_services(self) -> List[ServiceStatus]:
        """Get all services as Pydantic models"""
        return [ServiceStatus(**svc) for svc in self.cluster_state["services"]]

    def get_configmaps(self) -> List[ConfigMapStatus]:
        """Get all configmaps as Pydantic models"""
        return [ConfigMapStatus(**cm) for cm in self.cluster_state["configmaps"]]

    def get_secrets(self) -> List[SecretStatus]:
        """Get all secrets as Pydantic models"""
        return [SecretStatus(**s) for s in self.cluster_state.get("secrets", [])]

    def get_ingresses(self) -> List[IngressStatus]:
        """Get all ingresses as Pydantic models"""
        return [IngressStatus(**i) for i in self.cluster_state.get("ingresses", [])]

    def get_persistentvolumes(self) -> List[PVStatus]:
        """Get all PVs as Pydantic models"""
        return [
            PVStatus(**pv) for pv in self.cluster_state.get("persistentvolumes", [])
        ]

    def get_persistentvolumeclaims(self) -> List[PVCStatus]:
        """Get all PVCs as Pydantic models"""
        return [
            PVCStatus(**pvc)
            for pvc in self.cluster_state.get("persistentvolumeclaims", [])
        ]

    def get_hpas(self) -> List[HPAStatus]:
        """Get all HPAs as Pydantic models"""
        return [HPAStatus(**hpa) for hpa in self.cluster_state["hpas"]]

    def get_events(self) -> List[ClusterEvent]:
        """Get all events"""
        return self.events.copy()

    def apply_patch(self, resource_type: str, name: str, patch: Dict[str, Any]) -> bool:
        """Apply a patch to a resource"""
        try:
            if resource_type == "deployment":
                for dep in self.cluster_state["deployments"]:
                    if dep["name"] == name:
                        dep.update(patch)
                        dep["last_updated"] = datetime.now().isoformat()
                        if "desired_replicas" in patch or "available_replicas" in patch:
                            self._update_pods_for_deployment(
                                name,
                                dep.get("desired_replicas", dep["desired_replicas"]),
                            )
                        return True

            elif resource_type == "pod":
                for pod in self.cluster_state["pods"]:
                    if pod["name"] == name:
                        pod.update(patch)
                        pod["last_updated"] = datetime.now().isoformat()
                        return True

            elif resource_type == "node":
                for node in self.cluster_state["nodes"]:
                    if node["name"] == name:
                        node.update(patch)
                        node["last_updated"] = datetime.now().isoformat()
                        return True

            elif resource_type == "service":
                for svc in self.cluster_state["services"]:
                    if svc["name"] == name:
                        svc.update(patch)
                        svc["last_updated"] = datetime.now().isoformat()
                        return True

            elif resource_type == "configmap":
                for cm in self.cluster_state["configmaps"]:
                    if cm["name"] == name:
                        cm.update(patch)
                        cm["last_updated"] = datetime.now().isoformat()
                        return True

            elif resource_type == "hpa":
                for hpa in self.cluster_state["hpas"]:
                    if hpa["name"] == name:
                        hpa.update(patch)
                        hpa["last_updated"] = datetime.now().isoformat()
                        return True

            return False
        except Exception as e:
            print(f"Error applying patch: {e}")
            return False

    def _update_pods_for_deployment(self, deployment_name: str, desired_replicas: int):
        """Update pods count for a deployment"""
        current_pods = [
            p
            for p in self.cluster_state["pods"]
            if p.get("deployment") == deployment_name
        ]
        current_count = len(current_pods)

        if desired_replicas > current_count:
            nodes = self.cluster_state["nodes"]
            for i in range(desired_replicas - current_count):
                deployment = next(
                    (
                        d
                        for d in self.cluster_state["deployments"]
                        if d["name"] == deployment_name
                    ),
                    None,
                )
                if deployment:
                    pod_name = f"{deployment_name}-{int(self.rng.integers(1000, 10000))}-{self._random_suffix()}"
                    node = nodes[i % len(nodes)] if nodes else None
                    self.cluster_state["pods"].append(
                        {
                            "name": pod_name,
                            "status": "Pending",
                            "node": node["name"] if node else None,
                            "restarts": 0,
                            "cpu_request": self.config.get("pod_cpu_request", 500),
                            "mem_request": self.config.get("pod_mem_request", 256),
                            "cpu_limit": self.config.get("pod_cpu_limit", 1000),
                            "mem_limit": self.config.get("pod_mem_limit", 512),
                            "deployment": deployment_name,
                            "last_updated": datetime.now().isoformat(),
                        }
                    )
        elif desired_replicas < current_count:
            pods_to_remove = current_pods[desired_replicas:]
            for pod in pods_to_remove:
                self.cluster_state["pods"].remove(pod)

    def scale(self, deployment_name: str, replicas: int) -> bool:
        """Changes replica count"""
        return self.apply_patch(
            "deployment", deployment_name, {"desired_replicas": replicas}
        )

    def delete_pod(self, pod_name: str) -> bool:
        """Removes a pod (it gets recreated by the deployment controller on next tick)"""
        pod_index = None
        for i, pod in enumerate(self.cluster_state["pods"]):
            if pod["name"] == pod_name:
                pod_index = i
                break

        if pod_index is not None:
            del self.cluster_state["pods"][pod_index]

            event_type: Literal["Normal"] = "Normal"  # type: ignore
            event = ClusterEvent(
                event_id=f"event-delpod-{int(self.rng.integers(1000, 10000))}",
                timestamp=datetime.now().isoformat(),
                type=event_type,
                reason="UserDeleted",
                message=f"pod/{pod_name} deleted by user",
                involved_object=pod_name,
            )
            self.events.append(event)

            return True
        return False

    def rollout_restart(self, deployment: str) -> bool:
        """Restart a deployment rollout"""
        pods_to_delete = [
            p for p in self.cluster_state["pods"] if p.get("deployment") == deployment
        ]

        for pod in pods_to_delete:
            event_type: Literal["Normal"] = "Normal"  # type: ignore
            event = ClusterEvent(
                event_id=f"event-restart-{int(self.rng.integers(1000, 10000))}",
                timestamp=datetime.now().isoformat(),
                type=event_type,
                reason="RolledOut",
                message=f"Deployment {deployment} rollout restart triggered",
                involved_object=deployment,
            )
            self.events.append(event)

        self.cluster_state["pods"] = [
            p for p in self.cluster_state["pods"] if p.get("deployment") != deployment
        ]

        self._clear_failure_conditions(deployment)

        return True

    def _clear_failure_conditions(self, deployment: str):
        """Clear any injected failure conditions for a deployment after recovery action."""
        if deployment in self._injected_failures:
            del self._injected_failures[deployment]

    def inject_failure_condition(
        self, deployment: str, failure_type: str, failure_rate: float
    ):
        """Track an injected failure condition for a deployment."""
        self._injected_failures[deployment] = {
            "failure_type": failure_type,
            "failure_rate": failure_rate,
        }

    def set_hpa(
        self,
        deployment: str,
        min_replicas: int,
        max_replicas: int,
        cpu_target_percent: int,
    ) -> bool:
        """Create or update an HPA configuration for a deployment."""
        target_deployment = next(
            (d for d in self.cluster_state["deployments"] if d["name"] == deployment),
            None,
        )
        if target_deployment is None:
            return False

        hpa_name = f"{deployment}-hpa"
        now = datetime.now().isoformat()

        existing_hpa = next(
            (h for h in self.cluster_state["hpas"] if h.get("name") == hpa_name), None
        )
        if existing_hpa is None:
            self.cluster_state["hpas"].append(
                {
                    "name": hpa_name,
                    "min_replicas": min_replicas,
                    "max_replicas": max_replicas,
                    "current_replicas": max(
                        min_replicas,
                        min(target_deployment["desired_replicas"], max_replicas),
                    ),
                    "cpu_target_percent": cpu_target_percent,
                    "last_updated": now,
                }
            )
        else:
            existing_hpa.update(
                {
                    "min_replicas": min_replicas,
                    "max_replicas": max_replicas,
                    "cpu_target_percent": cpu_target_percent,
                    "current_replicas": max(
                        min_replicas,
                        min(target_deployment["desired_replicas"], max_replicas),
                    ),
                    "last_updated": now,
                }
            )

        # Keep the deployment desired replicas within configured HPA bounds.
        bounded_replicas = max(
            min_replicas, min(target_deployment["desired_replicas"], max_replicas)
        )
        target_deployment["desired_replicas"] = bounded_replicas
        target_deployment["last_updated"] = now

        event_type: Literal["Normal"] = "Normal"  # type: ignore
        self.events.append(
            ClusterEvent(
                event_id=f"event-hpa-{int(self.rng.integers(1000, 10000))}",
                timestamp=now,
                type=event_type,
                reason="HorizontalPodAutoscalerUpdated",
                message=(
                    f"HPA configured for deployment/{deployment}: "
                    f"min={min_replicas}, max={max_replicas}, cpu_target={cpu_target_percent}%"
                ),
                involved_object=deployment,
            )
        )

        return True

    def drain_node(self, node_name: str) -> bool:
        """Mark a node unschedulable and evict/reschedule pods currently on it."""
        node = next(
            (n for n in self.cluster_state["nodes"] if n["name"] == node_name), None
        )
        if node is None:
            return False

        node["status"] = "SchedulingDisabled"
        node["last_updated"] = datetime.now().isoformat()

        candidate_nodes = [
            n
            for n in self.cluster_state["nodes"]
            if n["name"] != node_name and n.get("status") == "Ready"
        ]

        pods_on_node = [
            p for p in self.cluster_state["pods"] if p.get("node") == node_name
        ]
        for i, pod in enumerate(pods_on_node):
            replacement = (
                candidate_nodes[i % len(candidate_nodes)] if candidate_nodes else None
            )
            pod["node"] = replacement["name"] if replacement else None
            pod["status"] = "Pending"
            pod["last_updated"] = datetime.now().isoformat()

            event_type: Literal["Normal"] = "Normal"  # type: ignore
            self.events.append(
                ClusterEvent(
                    event_id=f"event-evict-{int(self.rng.integers(1000, 10000))}",
                    timestamp=datetime.now().isoformat(),
                    type=event_type,
                    reason="Evicted",
                    message=f"pod/{pod['name']} evicted from drained node/{node_name}",
                    involved_object=pod["name"],
                )
            )

        event_type: Literal["Normal"] = "Normal"  # type: ignore
        self.events.append(
            ClusterEvent(
                event_id=f"event-drain-{int(self.rng.integers(1000, 10000))}",
                timestamp=datetime.now().isoformat(),
                type=event_type,
                reason="NodeDrained",
                message=f"node/{node_name} cordoned and drained",
                involved_object=node_name,
            )
        )

        return True

    def describe(self, resource_type: str, name: str) -> Dict[str, Any]:
        """Return kubectl-describe style details for a specific resource."""
        collection_map = {
            "deployment": "deployments",
            "pod": "pods",
            "node": "nodes",
            "service": "services",
            "configmap": "configmaps",
            "hpa": "hpas",
        }

        collection_name = collection_map.get(resource_type)
        if collection_name is None:
            return {
                "type": resource_type,
                "name": name,
                "found": False,
                "error": f"Unsupported resource_type: {resource_type}",
            }

        resource = next(
            (
                item
                for item in self.cluster_state.get(collection_name, [])
                if item.get("name") == name
            ),
            None,
        )
        if resource is None:
            return {
                "type": resource_type,
                "name": name,
                "found": False,
                "error": f"{resource_type} '{name}' not found",
            }

        related_pods = []
        if resource_type == "deployment":
            related_pods = [
                p for p in self.cluster_state["pods"] if p.get("deployment") == name
            ]
        elif resource_type == "node":
            related_pods = [
                p for p in self.cluster_state["pods"] if p.get("node") == name
            ]
        elif resource_type == "service":
            selector_app = resource.get("selector", {}).get("app")
            if selector_app:
                related_pods = [
                    p
                    for p in self.cluster_state["pods"]
                    if p.get("deployment") == selector_app
                ]

        related_events = [
            e.model_dump()
            for e in self.events
            if e.involved_object in {name, resource_type}
        ]

        return {
            "type": resource_type,
            "name": name,
            "found": True,
            "resource": dict(resource),
            "related_pods": related_pods,
            "recent_events": related_events[-10:],
            "step": self.step_count,
            "timestamp": datetime.now().isoformat(),
        }

    def tick(self):
        """Advances simulated time by one step. Pods in CrashLoopBackOff increment their restart counter. Pending pods on ready nodes eventually transition to Running. Dead nodes stay dead unless drained."""
        self.step_count += 1

        # Simulate some natural changes in resource usage
        for node in self.cluster_state["nodes"]:
            node["cpu_usage"] = max(
                0, min(100, node["cpu_usage"] + float(self.rng.uniform(-5, 5)))
            )
            node["mem_usage"] = max(
                0, min(100, node["mem_usage"] + float(self.rng.uniform(-5, 5)))
            )
            node["last_updated"] = datetime.now().isoformat()

        # Update pod statuses based on node status
        for pod in self.cluster_state["pods"]:
            node_name = pod.get("node")
            if node_name:
                node = next(
                    (n for n in self.cluster_state["nodes"] if n["name"] == node_name),
                    None,
                )
                if node and node["status"] != "Ready":
                    if pod["status"] == "Running":
                        pod["status"] = "Unknown"
                    elif pod["status"] == "Pending":
                        pod["status"] = "Unknown"
                elif node and node["status"] == "Ready" and pod["status"] == "Pending":
                    if float(self.rng.random()) > 0.7:
                        pod["status"] = "Running"
            pod["last_updated"] = datetime.now().isoformat()

        # Update deployment available replicas based on running pods
        for deployment in self.cluster_state["deployments"]:
            running_pods = [
                p
                for p in self.cluster_state["pods"]
                if p.get("deployment") == deployment["name"]
                and p["status"] == "Running"
            ]
            deployment["available_replicas"] = len(running_pods)
            deployment["last_updated"] = datetime.now().isoformat()

        # Re-create pods for deployments that need them
        for deployment in self.cluster_state["deployments"]:
            desired = deployment.get("desired_replicas", 0)
            current_pods = [
                p
                for p in self.cluster_state["pods"]
                if p.get("deployment") == deployment["name"]
            ]
            current_count = len(current_pods)

            if current_count < desired:
                nodes = self.cluster_state["nodes"]
                for i in range(desired - current_count):
                    pod_name = f"{deployment['name']}-{int(self.rng.integers(1000, 10000))}-{self._random_suffix()}"
                    node = nodes[i % len(nodes)] if nodes else None

                    pod_status = "Running"
                    restarts = 0
                    if deployment["name"] in self._injected_failures:
                        failure = self._injected_failures[deployment["name"]]
                        if failure.get("failure_type") == "crashloop" and float(
                            self.rng.random()
                        ) < failure.get("failure_rate", 0.8):
                            pod_status = "CrashLoopBackOff"
                            restarts = int(self.rng.integers(5, 21))
                        elif failure.get("failure_type") == "oom" and float(
                            self.rng.random()
                        ) < failure.get("failure_rate", 0.6):
                            pod_status = "CrashLoopBackOff"
                            restarts = int(self.rng.integers(10, 31))

                    self.cluster_state["pods"].append(
                        {
                            "name": pod_name,
                            "status": pod_status,
                            "node": node["name"] if node else None,
                            "restarts": restarts,
                            "cpu_request": self.config.get("pod_cpu_request", 500),
                            "mem_request": self.config.get("pod_mem_request", 256),
                            "cpu_limit": self.config.get("pod_cpu_limit", 1000),
                            "mem_limit": self.config.get("pod_mem_limit", 512),
                            "deployment": deployment["name"],
                            "last_updated": datetime.now().isoformat(),
                        }
                    )

        # Generate occasional events
        if float(self.rng.random()) < 0.3:
            self._generate_event()

    def _generate_event(self):
        """Generate a realistic cluster event"""
        event_types = [
            {
                "type": "Normal",
                "reason": "Scheduled",
                "message": "Successfully assigned node",
            },
            {
                "type": "Warning",
                "reason": "FailedScheduling",
                "message": "0/3 nodes are available: 3 Insufficient cpu.",
            },
            {
                "type": "Normal",
                "reason": "Pulling",
                "message": 'Pulling image "nginx:1.21"',
            },
            {
                "type": "Normal",
                "reason": "Pulled",
                "message": 'Successfully pulled image "nginx:1.21"',
            },
            {"type": "Normal", "reason": "Created", "message": "Created container"},
            {"type": "Normal", "reason": "Started", "message": "Started container"},
            {
                "type": "Warning",
                "reason": "BackOff",
                "message": "Back-off restarting failed container",
            },
            {"type": "Normal", "reason": "Killing", "message": "Stopping container"},
        ]

        event = self.rng.choice(event_types)
        involved_objects = []
        involved_objects.extend([p["name"] for p in self.cluster_state["pods"][:3]])
        involved_objects.extend(
            [d["name"] for d in self.cluster_state["deployments"][:3]]
        )
        involved_objects.extend([n["name"] for n in self.cluster_state["nodes"][:3]])

        if not involved_objects:
            involved_objects = ["cluster"]

        event_type: Literal["Normal", "Warning"] = event["type"]  # type: ignore
        self.events.append(
            ClusterEvent(
                event_id=f"event-{self._event_counter:04d}",
                timestamp=datetime.now().isoformat(),
                type=event_type,
                reason=event["reason"],
                message=event["message"],
                involved_object=str(self.rng.choice(involved_objects)),
            )
        )
        self._event_counter += 1

        if len(self.events) > 100:
            self.events = self.events[-50:]

    def get_logs(self, deployment: str) -> List[PodLog]:
        """Get logs for pods in a deployment"""
        pods = self.get_pods(selector={"deployment": deployment})
        logs = []
        for pod in pods[:3]:
            log_messages = [
                f"[{pod.name}] Starting application...",
                f"[{pod.name}] Server listening on port 8080",
                f"[{pod.name}] Health check passed",
                f"[{pod.name}] Processing request id={self.rng.integers(1000, 9999)}",
            ]
            logs.append(
                PodLog(
                    pod_name=pod.name,
                    container_name="main",
                    log_content="\n".join(log_messages[: self.rng.integers(2, 4)]),
                    timestamp=datetime.now().isoformat(),
                )
            )
        return logs

    def get_metrics(self) -> List[ResourceMetric]:
        """Get cluster resource metrics"""
        metrics = []
        nodes = self.cluster_state["nodes"]
        for node in nodes:
            metrics.append(
                ResourceMetric(
                    name=node["name"],
                    type="cpu",
                    usage=float(node.get("cpu_usage", 0)),
                    capacity=float(node.get("cpu_capacity", 4)),
                    usage_percent=float(node.get("cpu_usage", 0)),
                    timestamp=datetime.now().isoformat(),
                )
            )
            metrics.append(
                ResourceMetric(
                    name=node["name"],
                    type="memory",
                    usage=float(node.get("mem_usage", 0)),
                    capacity=float(node.get("mem_capacity", 8192)),
                    usage_percent=float(node.get("mem_usage", 0)),
                    timestamp=datetime.now().isoformat(),
                )
            )
        return metrics

    def get_full_state(self) -> Dict[str, Any]:
        """Get the full cluster state for debugging"""
        return {
            "nodes": self.get_nodes(),
            "pods": self.get_pods(),
            "deployments": self.get_deployments(),
            "services": self.get_services(),
            "configmaps": self.get_configmaps(),
            "secrets": self.get_secrets(),
            "ingresses": self.get_ingresses(),
            "persistentvolumes": self.get_persistentvolumes(),
            "persistentvolumeclaims": self.get_persistentvolumeclaims(),
            "hpas": self.get_hpas(),
            "events": self.get_events(),
            "step": self.step_count,
        }

    def reset_to_healthy(self):
        """Reset cluster to healthy state"""
        self.cluster_state = self._initialize_healthy_cluster()
        self.step_count = 0
        self.events = []
        self._event_counter = 0

    def reset(self, condition=None):
        """Reset the world state and optionally inject a failure condition"""
        self.reset_to_healthy()
        if condition:
            condition.inject()
        return self.get_observation()

    def get_observation(self, objective: str = "Maintain cluster health"):
        """Serialises the current state into a ClusterObservation Pydantic model"""
        observation_dict = self.get_full_state()
        observation_dict["objective"] = objective
        observation_dict["logs"] = self.get_logs("frontend") + self.get_logs("backend")
        observation_dict["metrics"] = self.get_metrics()
        return ClusterObservation(**observation_dict)
