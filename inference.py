"""
Inference Script Example
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    API_KEY        The API key for the LLM proxy.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Optional local fallback API key.
    LOCAL_IMAGE_NAME The name of the local image to use for the environment if you are using from_docker_image()
                     method

- Defaults are set only for API_BASE_URL and MODEL_NAME
    (and should reflect your active inference setup):
    API_BASE_URL = os.getenv("API_BASE_URL", "<your-active-endpoint>")
    MODEL_NAME = os.getenv("MODEL_NAME", "<your-active-model>")

- The inference script must be named `inference.py` and placed in the root directory of the project
- Participants must use OpenAI Client for all LLM calls using above variables

STDOUT FORMAT
- The script must emit exactly three line types to stdout, in this order:

    [START] task=<task_name> env=<benchmark> model=<model_name>
    [STEP]  step=<n> action=<action_str> reward=<0.00> done=<true|false> error=<msg|null>
    [END]   success=<true|false> steps=<n> score=<score> rewards=<r1,r2,...,rn>

  Rules:
    - One [START] line at episode begin.
    - One [STEP] line per step, immediately after env.step() returns.
    - One [END] line after env.close(), always emitted (even on exception).
    - reward and rewards are formatted to 2 decimal places.
    - done and success are lowercase booleans: true or false.
    - error is the raw last_action_error string, or null if none.
    - All fields on a single line with no newlines within a line.
    - Each task should return score strictly in (0, 1)

  Example:
    [START] task=click-test env=miniwob model=Qwen3-VL-30B
    [STEP] step=1 action=click('123') reward=0.00 done=false error=null
    [STEP] step=2 action=fill('456','text') reward=0.00 done=false error=null
    [STEP] step=3 action=click('789') reward=1.00 done=true error=null
    [END] success=true steps=3 score=1.00 rewards=0.00,0.00,1.00
"""

import asyncio
import json
import math
import os
import websockets
import sys
import textwrap
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from models import CoenvAction
    from client import CoEnv
except ImportError:
    from models import CoenvAction
    from client import CoEnv

if load_dotenv is not None:
    load_dotenv()

ENV_URL = os.getenv("ENV_URL", "https://Nightreigners-COEnv.hf.space")

LLM_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen3-8B")
API_KEY = os.getenv("API_KEY") or os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")
DEBUG = os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

BENCHMARKS = ["POD_RECOVERY", "AUTOSCALING", "INCIDENT"]
TASK_NAMES = ["pod_recovery", "autoscaling", "incident"]

API_DELAY = 0
_model_thinks: Optional[bool] = None
TEMPERATURE = 0.3
MAX_TOKENS = 1024


def _is_thinking_response(message) -> bool:
    """Check if the response actually contained reasoning/thinking tokens."""
    content = message.content

    # Check 1: content is a list of blocks with a reasoning/thinking block
    if isinstance(content, list):
        return any(
            getattr(block, "type", "") in ("reasoning", "thinking") for block in content
        )

    # Check 2: some providers expose reasoning separately
    if getattr(message, "reasoning_content", None):
        return True

    # Check 3: raw <think> tags in string content (HF/Qwen style)
    if isinstance(content, str) and "<think>" in content:
        return True

    return False


SUCCESS_SCORE_THRESHOLD = 0.1  # normalized score in [0, 1]
DEFAULT_MAX_STEPS = 15

SUCCESS_SCORE_THRESHOLD_BY_TASK: Dict[str, float] = {
    "pod_recovery": 0.9,
    "autoscaling": 0.9,
    "security": 0.8,
}

MAX_STALL_REPEATS = 4
REWARD_EPSILON = 1e-9
MAX_TASK_RETRIES_ON_CONNECTION_CLOSE = 1
SCORE_EPSILON = 1e-4

MAX_STEPS_BY_TASK = {
    "pod_recovery": 15,
    "autoscaling": 20,
    "security": 20,
}

SENSITIVE_KEYS = {"API_KEY", "DB_PASSWORD", "JWT_SECRET", "SECRET", "PASSWORD"}
SENSITIVE_KEY_HINTS = ("SECRET", "PASSWORD", "TOKEN", "API_KEY")
SENSITIVE_VALUE_HINTS = ("sk_live", "p@ss", "secret", "token", "password")

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are an expert Kubernetes cluster operator and incident-response agent.

    ## OUTPUT FORMAT
    Your response must be ONLY a valid JSON object — no preamble, no explanation, no markdown, no code fences, no thinking text.
    Always use lowercase for action_type and keys.

    ## SCORING
    - Higher scores for faster resolution (fewer steps = higher bonus)
    - Unnecessary actions reduce your score
    - Dangerous actions (delete_pod, drain_node) should be last resort only

    ## AVAILABLE ACTIONS

    | Action | When to Use | Required Fields |
    |--------|-----------|----------------|
    | rollout_restart | RECOMMENDED for CrashLoopBackOff, ImagePullBackOff, OOMKill - triggers rolling update | deployment |
    | scale | Scale replicas up/down | deployment, replicas |
    | set_hpa | Configure autoscaling for traffic spikes | deployment, min_replicas, max_replicas, cpu_target_percent |
    | describe | Inspect resources for diagnosis (use sparingly) | resource_type, name |
    | delete_pod | LAST RESORT - only when no other option | pod_name |
    | wait | Let the system settle | (none) |
    | patch | Modify configmaps/secrets/services | resource_type, name, patch |
    | create_secret | Create a new Kubernetes Secret (for security task) | name, data |
    | drain_node | Evacuate pods before node maintenance | node_name |

    ## ACTION FIELDS
    - action_type: (required) which action to perform
    - deployment: name of deployment (frontend, backend, auth-service, api-gateway, database)
    - replicas: integer 1-20 (for scale)
    - pod_name: exact pod name to delete
    - resource_type: deployment|pod|node|service|configmap|hpa|secret
    - name: resource name to describe/patch
    - patch: JSON object with changes
    - min_replicas: 1-10 (for set_hpa)
    - max_replicas: 1-20 (for set_hpa)
    - cpu_target_percent: 10-90 (for set_hpa)
    - node_name: node-X to drain
    - data: key-value pairs for create_secret (e.g., {"API_KEY": "value", "DB_PASSWORD": "value"})

    ## SECURITY TASK
    When fixing exposed credentials in ConfigMaps:
    1. Describe configmaps to find exposed keys (API_KEY, DB_PASSWORD, JWT_SECRET, etc.)
    2. Use create_secret to create a Secret with those credentials
    3. Use patch to remove sensitive keys from ConfigMap data using patch.data, e.g. {"data":{"API_KEY":null}}
    Create secrets BEFORE removing from ConfigMaps to avoid data loss.

    ## DECISION TREE
    Standard troubleshooting best practices apply, but here are some common scenarios:
    If pods are CrashLoopBackOff or ImagePullBackOff:
        → rollout_restart the deployment

    If traffic spike / high CPU / pods pending:
        → set_hpa with min=2-4, max=6-10, cpu_target=70

    If pod stuck in non-recoverable state:
        → delete_pod (deployment will recreate)

    If you need info:
        → describe once, then act

    If all looks good:
        → wait or scale as needed

    ## EXAMPLE RESPONSES

    {"action_type":"rollout_restart","deployment":"frontend"}
    {"action_type":"set_hpa","deployment":"backend","min_replicas":2,"max_replicas":8,"cpu_target_percent":70}
    {"action_type":"describe","resource_type":"deployment","name":"frontend"}
    {"action_type":"scale","deployment":"backend","replicas":4}
    {"action_type":"describe","resource_type":"pod","name":"frontend-xyz-abc"}
    {"action_type":"wait"}
    {"action_type":"create_secret","name":"frontend-secret","data":{"API_KEY":"sk_live_xxx","DB_PASSWORD":"secret"}}

    Your reply (JSON only):
    """
).strip()


def debug_log(message: str) -> None:
    if DEBUG:
        print(f"[DEBUG] {message}", file=sys.stderr, flush=True)


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(
    step: int, action: str, reward: float, done: bool, error: Optional[str]
) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(
        f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def _clamp_open_unit_interval(value: float, eps: float = SCORE_EPSILON) -> float:
    """Clamp a score strictly inside (0, 1) with a small safety margin."""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.5

    if not math.isfinite(numeric):
        return 0.5

    return min(max(numeric, eps), 1.0 - eps)


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    score = _clamp_open_unit_interval(score)
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.4f} rewards={rewards_str}",
        flush=True,
    )


def _to_dict(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if isinstance(obj, dict):
        return obj
    return vars(obj)


def _is_sensitive_entry(key: Any, value: Any) -> bool:
    if not isinstance(key, str):
        return False

    key_upper = key.upper()
    if key_upper in SENSITIVE_KEYS or any(hint in key_upper for hint in SENSITIVE_KEY_HINTS):
        return True

    value_lower = str(value).lower()
    return any(hint in value_lower for hint in SENSITIVE_VALUE_HINTS)


def _find_security_exposures(observation: Any) -> List[Dict[str, Any]]:
    obs = _to_dict(observation)
    exposures: List[Dict[str, Any]] = []

    for configmap in obs.get("configmaps", []):
        if not isinstance(configmap, dict):
            continue
        name = configmap.get("name")
        data = configmap.get("data")
        if not isinstance(name, str) or not isinstance(data, dict):
            continue

        exposed_keys: List[str] = []
        exposed_values: Dict[str, str] = {}
        for key, value in data.items():
            if _is_sensitive_entry(key, value):
                exposed_keys.append(key)
                if value is not None:
                    exposed_values[key] = value if isinstance(value, str) else str(value)

        if exposed_keys:
            exposures.append(
                {
                    "name": name,
                    "keys": sorted(set(exposed_keys)),
                    "values": exposed_values,
                }
            )

    return exposures


def _secret_name_for_configmap(configmap_name: str) -> str:
    if configmap_name.endswith("-config"):
        return f"{configmap_name[:-7]}-secret"
    return f"{configmap_name}-secret"


def _security_deterministic_action(observation: Any) -> Dict[str, Any]:
    obs = _to_dict(observation)
    secret_names = {
        s.get("name")
        for s in obs.get("secrets", [])
        if isinstance(s, dict) and isinstance(s.get("name"), str)
    }

    exposures = _find_security_exposures(obs)
    for exposure in exposures:
        configmap_name = exposure["name"]
        secret_name = _secret_name_for_configmap(configmap_name)
        secret_data = exposure.get("values", {})
        if secret_name not in secret_names and secret_data:
            return {
                "action_type": "create_secret",
                "name": secret_name,
                "data": secret_data,
            }

        return {
            "action_type": "patch",
            "resource_type": "configmap",
            "name": configmap_name,
            "patch": {"data": {key: None for key in exposure.get("keys", [])}},
        }

    return {"action_type": "wait"}


def _summarize_describe_detail(describe_detail: Any) -> Optional[str]:
    if not isinstance(describe_detail, dict):
        return None

    resource_type = describe_detail.get("type")
    name = describe_detail.get("name")
    resource = describe_detail.get("resource")

    if resource_type != "configmap" or not isinstance(name, str) or not isinstance(resource, dict):
        return None

    data = resource.get("data")
    if not isinstance(data, dict):
        return f"Describe configmap/{name}: data=none"

    exposed_keys = [key for key, value in data.items() if _is_sensitive_entry(key, value)]
    if exposed_keys:
        return f"Describe configmap/{name}: exposed_keys={','.join(sorted(set(exposed_keys)))}"
    return f"Describe configmap/{name}: exposed_keys=none"


def _observation_summary(observation: Any) -> str:
    obs = _to_dict(observation)
    pods = obs.get("pods", [])
    deployments = obs.get("deployments", [])
    events = obs.get("events", [])
    exposures = _find_security_exposures(obs)
    secret_names = [
        s.get("name")
        for s in obs.get("secrets", [])
        if isinstance(s, dict) and isinstance(s.get("name"), str)
    ]

    pod_status_counts: Dict[str, int] = {}
    for pod in pods:
        status = pod.get("status", "Unknown")
        pod_status_counts[status] = pod_status_counts.get(status, 0) + 1

    deployment_lines = []
    for dep in deployments:
        deployment_lines.append(
            f"{dep.get('name')}: desired={dep.get('desired_replicas', 0)} available={dep.get('available_replicas', 0)}"
        )

    recent_events = [
        f"{e.get('type', 'Normal')}/{e.get('reason', '')}: {e.get('message', '')}"
        for e in events[-5:]
    ]

    exposure_lines = [f"{entry['name']}: {','.join(entry['keys'])}" for entry in exposures]

    return textwrap.dedent(
        f"""
        Objective: {obs.get("objective", "")}
        Step: {obs.get("step", 0)}
        Pod status counts: {pod_status_counts}
        Deployments:
        {chr(10).join(deployment_lines) if deployment_lines else "None"}
        Security findings (configmaps with exposed keys):
        {chr(10).join(exposure_lines) if exposure_lines else "None"}
        Secrets present:
        {', '.join(secret_names) if secret_names else "None"}
        Recent events:
        {chr(10).join(recent_events) if recent_events else "None"}
        """
    ).strip()


def build_user_prompt(
    task_name: str, step: int, observation: Any, history: List[str]
) -> str:
    history_block = "\n".join(history[-4:]) if history else "None"
    task_hint = ""
    if task_name == "security":
        task_hint = textwrap.dedent(
            """
            Security hint:
            - Do not repeat describe on the same configmaps.
            - After creating a Secret, patch the ConfigMap using patch.data with null values for sensitive keys.
            - If no exposed keys remain, return {"action_type":"wait"}.
            """
        ).strip()

    return textwrap.dedent(
        f"""
        Task: {task_name}
        Step: {step}
        Current cluster summary:
        {_observation_summary(observation)}
        {task_hint}
        Previous steps:
        {history_block}
        Return one valid next action as pure JSON.
        """
    ).strip()


def _extract_visible_text(message) -> str:
    """
    Pull only the assistant's visible text, skipping reasoning/thinking blocks.
    Handles:
      - message.content as a list of blocks (OpenAI-style tool/reasoning blocks)
      - message.reasoning_content  (some providers surface this separately)
      - Raw string content
    """
    content = message.content

    # Case 1: list of content blocks (e.g. from extended thinking APIs)
    if isinstance(content, list):
        parts = []
        for block in content:
            block_type = getattr(block, "type", None)
            if block_type in ("text", None):  # keep text blocks
                parts.append(getattr(block, "text", "") or "")
            # skip "reasoning", "thinking", "tool_use", etc.
        return "".join(parts).strip()

    # Case 2: plain string — strip any <think>…</think> wrappers some models emit
    if isinstance(content, str):
        import re

        cleaned = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
        return cleaned.strip()

    return ""


def _safe_json_action(text: str) -> Optional[Dict[str, Any]]:
    def _extract_action_dict(parsed: Any) -> Optional[Dict[str, Any]]:
        if isinstance(parsed, dict):
            if "action_type" in parsed:
                return parsed

            nested = parsed.get("action")
            if isinstance(nested, dict) and "action_type" in nested:
                return nested

            name_val = parsed.get("name")
            arguments = parsed.get("arguments")
            # Treat name+arguments as function-call style only when arguments is present.
            # Otherwise regular action payloads like {"name": "backend", ...} can be misread.
            if isinstance(name_val, str) and "arguments" in parsed:
                if isinstance(arguments, str):
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                if not isinstance(arguments, dict):
                    arguments = {}
                action = dict(arguments)
                action["action_type"] = name_val
                return action

        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict) and "action_type" in item:
                    return item
        return None

    text = text.strip()
    if not text:
        return None

    def _parse_candidate(
        candidate: str, first_generic: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        try:
            parsed = json.loads(candidate)
            extracted = _extract_action_dict(parsed)
            if extracted is not None:
                return extracted
            if first_generic is None and isinstance(parsed, dict):
                return parsed
            return first_generic
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            for idx, ch in enumerate(candidate):
                if ch not in "[{":
                    continue
                try:
                    parsed, _ = decoder.raw_decode(candidate[idx:])
                except json.JSONDecodeError:
                    continue

                extracted = _extract_action_dict(parsed)
                if extracted is not None:
                    return extracted
                if first_generic is None and isinstance(parsed, dict):
                    first_generic = parsed

            return first_generic

    first_generic: Optional[Dict[str, Any]] = None

    parsed = _parse_candidate(text, first_generic)
    if parsed is not None:
        extracted = _extract_action_dict(parsed)
        if extracted is not None:
            return extracted
        if isinstance(parsed, dict):
            first_generic = parsed

    fence = "```"
    cursor = 0
    while True:
        start = text.find(fence, cursor)
        if start == -1:
            break
        end = text.find(fence, start + len(fence))
        if end == -1:
            break

        block = text[start + len(fence) : end].strip()
        if block.lower().startswith("json"):
            block = block[4:].strip()

        parsed = _parse_candidate(block, first_generic)
        if parsed is not None:
            extracted = _extract_action_dict(parsed)
            if extracted is not None:
                return extracted
            if first_generic is None and isinstance(parsed, dict):
                first_generic = parsed

        cursor = end + len(fence)

    return first_generic


def _normalize_action(action: Dict[str, Any]) -> Dict[str, Any]:
    action_type = action.get("action_type", "describe")
    if isinstance(action_type, str):
        action_type = {
            "set_hpas": "set_hpa",
            "hpa": "set_hpa",
            "restart_rollout": "rollout_restart",
            "noop": "wait",
            "no_op": "wait",
            "pause": "wait",
            "sleep": "wait",
        }.get(action_type.strip().lower(), action_type.strip().lower())
    else:
        action_type = "describe"

    valid_action_types = {
        "scale",
        "delete_pod",
        "patch",
        "rollout_restart",
        "set_hpa",
        "drain_node",
        "describe",
        "wait",
        "create_secret",
    }
    if action_type not in valid_action_types:
        # Recover from malformed outputs (e.g., action_type="backend").
        if any(
            k in action for k in ("min_replicas", "max_replicas", "cpu_target_percent")
        ):
            inferred_action_type = "set_hpa"
        elif "replicas" in action:
            inferred_action_type = "scale"
        elif "pod_name" in action:
            inferred_action_type = "delete_pod"
        elif "node_name" in action:
            inferred_action_type = "drain_node"
        elif "patch" in action:
            inferred_action_type = "patch"
        elif "resource_type" in action or "name" in action:
            inferred_action_type = "describe"
        elif "deployment" in action:
            inferred_action_type = "rollout_restart"
        else:
            inferred_action_type = "describe"

        debug_log(
            f"Invalid action_type={action_type!r}; inferred action_type={inferred_action_type!r}."
        )
        action_type = inferred_action_type

    normalized: Dict[str, Any] = {"action_type": action_type}

    valid_resource_types = {
        "deployment",
        "pod",
        "node",
        "service",
        "configmap",
        "hpa",
        "secret",
        "ingress",
        "pvc",
    }
    resource_type_aliases = {
        "horizontalpodautoscaler": "hpa",
        "horizontal_pod_autoscaler": "hpa",
        "hpas": "hpa",
        "deploy": "deployment",
        "deployments": "deployment",
        "pods": "pod",
        "nodes": "node",
        "services": "service",
        "configmaps": "configmap",
        "secrets": "secret",
        "ingresses": "ingress",
        "persistentvolumeclaim": "pvc",
        "persistentvolumeclaims": "pvc",
    }

    allowed_fields = {
        "deployment",
        "replicas",
        "pod_name",
        "resource_type",
        "name",
        "patch",
        "min_replicas",
        "max_replicas",
        "cpu_target_percent",
        "node_name",
        "data",
    }
    for field in allowed_fields:
        if field in action and action[field] is not None:
            normalized[field] = action[field]

    if "resource_type" in normalized:
        rt_value = normalized.get("resource_type")
        if isinstance(rt_value, str):
            rt = rt_value.strip().lower().replace("-", "_")
            rt = resource_type_aliases.get(rt, rt)
            if rt in valid_resource_types:
                normalized["resource_type"] = rt
            else:
                normalized.pop("resource_type", None)
        else:
            normalized.pop("resource_type", None)

    if action_type in {
        "set_hpa",
        "scale",
        "rollout_restart",
        "delete_pod",
        "drain_node",
        "wait",
    }:
        normalized.pop("resource_type", None)
        normalized.pop("name", None)
        if action_type != "patch":
            normalized.pop("patch", None)

    if action_type == "create_secret":
        normalized.pop("resource_type", None)
        normalized.pop("patch", None)

    defaults_by_type = {
        "describe": {"resource_type": "deployment", "name": "frontend"},
        "scale": {"deployment": "frontend", "replicas": 3},
        "rollout_restart": {"deployment": "frontend"},
        "delete_pod": {"pod_name": "frontend-unknown"},
        "drain_node": {"node_name": "node-1"},
        "patch": {"resource_type": "deployment", "name": "frontend", "patch": {}},
        "set_hpa": {
            "deployment": "backend",
            "min_replicas": 2,
            "max_replicas": 6,
            "cpu_target_percent": 70,
        },
        "wait": {},
        "create_secret": {"name": "new-secret", "data": {}},
    }
    for k, v in defaults_by_type.get(action_type, {}).items():
        normalized.setdefault(k, v)

    return normalized


def _find_deployment_name(observation: Dict[str, Any], preferred: str) -> Optional[str]:
    deployments = observation.get("deployments", [])
    names = [d.get("name") for d in deployments if d.get("name")]
    if preferred in names:
        return preferred
    return names[0] if names else None


def _find_resource_name(
    observation: Any, resource_type: str, preferred: str
) -> Optional[str]:
    obs = _to_dict(observation)
    collection_by_type = {
        "deployment": "deployments",
        "pod": "pods",
        "node": "nodes",
        "service": "services",
        "configmap": "configmaps",
        "secret": "secrets",
        "hpa": "hpas",
        "ingress": "ingresses",
        "pvc": "persistentvolumeclaims",
    }
    collection = collection_by_type.get(resource_type)
    if not collection:
        return preferred

    names: List[str] = []
    for item in obs.get(collection, []):
        if isinstance(item, dict):
            name = item.get("name")
        else:
            name = getattr(item, "name", None)
        if isinstance(name, str) and name:
            names.append(name)

    if preferred in names:
        return preferred
    return names[0] if names else preferred


def _repair_action_for_server(
    action: Dict[str, Any], task_name: str, observation: Any
) -> Dict[str, Any]:
    repaired = _normalize_action(action)
    action_type = repaired.get("action_type", "describe")

    if action_type == "create_secret":
        name = repaired.get("name")
        if isinstance(name, str):
            name = name.strip()
        if not name:
            name = "app-secret"
        repaired["name"] = name

        raw_data = repaired.get("data")
        sanitized_data: Dict[str, str] = {}
        if isinstance(raw_data, dict):
            for key, value in raw_data.items():
                if not isinstance(key, str):
                    continue
                if value is None:
                    continue
                sanitized_data[key] = value if isinstance(value, str) else str(value)

        repaired["data"] = sanitized_data

        # Some providers emit an empty create_secret call; gather more context instead.
        if task_name == "security" and not sanitized_data:
            preferred = _find_resource_name(
                observation, "configmap", preferred="frontend-config"
            )
            return _normalize_action(
                {
                    "action_type": "describe",
                    "resource_type": "configmap",
                    "name": preferred,
                }
            )

    if repaired.get("action_type") == "describe":
        allowed_resource_types = {
            "deployment",
            "pod",
            "node",
            "service",
            "configmap",
            "secret",
        }
        resource_type = repaired.get("resource_type")
        if resource_type not in allowed_resource_types:
            resource_type = "configmap" if task_name == "security" else "deployment"
            repaired["resource_type"] = resource_type

        preferred_name = "frontend"
        if resource_type == "configmap":
            preferred_name = "frontend-config"
        elif resource_type == "secret":
            preferred_name = "frontend-secret"

        name = repaired.get("name")
        if not isinstance(name, str) or not name.strip():
            repaired["name"] = _find_resource_name(
                observation, resource_type, preferred=preferred_name
            )

    if (
        task_name == "security"
        and repaired.get("action_type") == "patch"
        and repaired.get("resource_type") == "configmap"
    ):
        configmap_name = repaired.get("name")
        if not isinstance(configmap_name, str) or not configmap_name.strip():
            configmap_name = _find_resource_name(
                observation, "configmap", preferred="frontend-config"
            )
            repaired["name"] = configmap_name

        raw_patch = repaired.get("patch")
        patch = raw_patch if isinstance(raw_patch, dict) else {}
        data_patch = patch.get("data")

        if isinstance(data_patch, dict):
            normalized_data_patch = data_patch
        else:
            normalized_data_patch = {
                key: value for key, value in patch.items() if key != "data"
            }

        if not normalized_data_patch:
            exposures_by_cm = {
                entry["name"]: entry["keys"] for entry in _find_security_exposures(observation)
            }
            keys_to_remove = exposures_by_cm.get(configmap_name, [])
            normalized_data_patch = {key: None for key in keys_to_remove}

        repaired["patch"] = {"data": normalized_data_patch}

    return repaired


def _task_fallback_action(
    task_name: str, step: int, observation: Any
) -> Dict[str, Any]:
    obs = _to_dict(observation)
    pods = obs.get("pods", [])

    if task_name == "autoscaling":
        deployment = _find_deployment_name(obs, "backend") or "frontend"
        return {
            "action_type": "set_hpa",
            "deployment": deployment,
            "min_replicas": 2,
            "max_replicas": 8,
            "cpu_target_percent": 60,
        }

    if task_name == "pod_recovery":
        crashing_frontend = [
            p
            for p in pods
            if p.get("deployment") == "frontend"
            and p.get("status") == "CrashLoopBackOff"
        ]
        if step == 1 and crashing_frontend:
            return {
                "action_type": "describe",
                "resource_type": "pod",
                "name": crashing_frontend[0].get("name", "frontend"),
            }
        deployment = _find_deployment_name(obs, "frontend") or "frontend"
        return {"action_type": "rollout_restart", "deployment": deployment}

    if task_name == "incident":
        deployment = _find_deployment_name(obs, "auth-service") or "frontend"
        return {"action_type": "rollout_restart", "deployment": deployment}

    return {
        "action_type": "describe",
        "resource_type": "deployment",
        "name": "frontend",
    }


async def get_model_action(
    client: AsyncOpenAI, task_name: str, step: int, observation: Any, history: List[str]
) -> Dict[str, Any]:
    user_prompt = build_user_prompt(task_name, step, observation, history)
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            prompt = (
                user_prompt
                if attempt == 0
                else user_prompt + "\n\nCRITICAL: Reply with ONLY a JSON object."
            )

            completion = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                temperature=TEMPERATURE,
                max_tokens=MAX_TOKENS,
            )

            choice = completion.choices[0]
            message = choice.message

            text = _extract_visible_text(message)

            if not text:
                debug_log(
                    f"Empty visible text (thinking model produced reasoning only?) "
                    f"task={task_name} step={step} attempt={attempt + 1}/{max_attempts}"
                )
                continue

            parsed = _safe_json_action(text)
            if isinstance(parsed, dict):
                repaired = _repair_action_for_server(parsed, task_name, observation)
                if task_name == "security" and repaired.get("action_type") == "describe":
                    recent_describes = sum(
                        1 for entry in history[-4:] if '"action_type":"describe"' in entry
                    )
                    if recent_describes >= 3:
                        fallback_security_action = _security_deterministic_action(observation)
                        if fallback_security_action.get("action_type") != "wait":
                            debug_log(
                                "Security anti-stall triggered; replacing repeated describe with deterministic action"
                            )
                            return _repair_action_for_server(
                                fallback_security_action, task_name, observation
                            )
                return repaired

            debug_log(
                f"JSON parse failed task={task_name} step={step} "
                f"attempt={attempt + 1}/{max_attempts} preview={text[:240]!r}"
            )

        except Exception as exc:
            debug_log(f"Model request failed: {exc}")
            if attempt == max_attempts - 1:
                raise

    fallback_candidate = (
        _security_deterministic_action(observation)
        if task_name == "security"
        else _task_fallback_action(task_name, step, observation)
    )
    fallback = _repair_action_for_server(
        fallback_candidate,
        task_name,
        observation,
    )
    debug_log(
        f"Using fallback action task={task_name} step={step}: {json.dumps(fallback, separators=(',', ':'))}"
    )
    return fallback


async def main() -> None:
    if not API_KEY:
        raise RuntimeError(
            "Missing API_KEY (or fallback HF_TOKEN/OPENAI_API_KEY) for OpenAI client."
        )
    client = AsyncOpenAI(base_url=LLM_BASE_URL, api_key=API_KEY)

    for TASK_NAME, BENCHMARK in zip(TASK_NAMES, BENCHMARKS):
        retries_left = MAX_TASK_RETRIES_ON_CONNECTION_CLOSE

        while True:
            max_steps = MAX_STEPS_BY_TASK.get(TASK_NAME, DEFAULT_MAX_STEPS)

            history: List[str] = []
            rewards: List[float] = []
            steps_taken = 0
            score = 0.0
            success = False
            final_obs: Optional[Any] = None
            should_retry_task = False
            episode_done = False
            episode_truncated = False

            log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

            try:
                async with CoEnv(base_url=ENV_URL) as env:
                    result = await env.reset(task=TASK_NAME)
                    final_obs = result.observation

                    for step in range(1, max_steps + 1):
                        if API_DELAY > 0:
                            await asyncio.sleep(API_DELAY)
                        if result.done:
                            episode_done = True
                            log_step(
                                step=step,
                                action="",
                                reward=result.reward or 0.0,
                                done=True,
                                error=None,
                            )
                            break

                        action_payload = await get_model_action(
                            client, TASK_NAME, step, final_obs, history
                        )
                        action = CoenvAction(**action_payload)
                        try:
                            result = await env.step(action)
                        except Exception as step_exc:
                            step_error = str(step_exc)
                            if (
                                "VALIDATION_ERROR" not in step_error
                                and "Invalid message" not in step_error
                            ):
                                raise

                            debug_log(
                                "Step rejected by server validation "
                                f"task={TASK_NAME} step={step} action={json.dumps(action_payload, separators=(',', ':'))} "
                                f"error={step_error}"
                            )

                            retry_candidates: List[Dict[str, Any]] = [
                                _repair_action_for_server(
                                    _task_fallback_action(TASK_NAME, step, final_obs),
                                    TASK_NAME,
                                    final_obs,
                                ),
                                {"action_type": "wait"},
                            ]
                            recovered = False

                            for candidate in retry_candidates:
                                if candidate == action_payload:
                                    continue
                                try:
                                    fallback_action = CoenvAction(**candidate)
                                    result = await env.step(fallback_action)
                                    action_payload = candidate
                                    action = fallback_action
                                    recovered = True
                                    debug_log(
                                        "Recovered with fallback action "
                                        f"task={TASK_NAME} step={step} action={json.dumps(candidate, separators=(',', ':'))}"
                                    )
                                    break
                                except Exception as retry_exc:
                                    debug_log(
                                        "Fallback action also failed "
                                        f"task={TASK_NAME} step={step} error={retry_exc}"
                                    )

                            if not recovered:
                                raise

                        obs = result.observation
                        final_obs = obs

                        reward = result.reward or 0.0
                        done = result.done
                        metadata = (
                            (obs.metadata or {}) if hasattr(obs, "metadata") else {}
                        )
                        error = metadata.get("error")
                        if metadata.get("truncated"):
                            episode_truncated = True
                        episode_done = done

                        describe_note = _summarize_describe_detail(
                            metadata.get("describe_detail")
                        )
                        if describe_note:
                            history.append(describe_note)

                        rewards.append(reward)
                        steps_taken = step

                        action_str = json.dumps(action_payload, separators=(",", ":"))
                        log_step(
                            step=step,
                            action=action_str,
                            reward=reward,
                            done=done,
                            error=error,
                        )
                        history.append(
                            f"Step {step}: {action_str} -> reward {reward:+.2f}"
                        )

                        if done:
                            break
            except websockets.exceptions.ConnectionClosedError as exc:
                debug_log(f"Connection closed unexpectedly for task={TASK_NAME}: {exc}")
                should_retry_task = retries_left > 0
                if should_retry_task:
                    debug_log(
                        f"Retrying task={TASK_NAME} ({MAX_TASK_RETRIES_ON_CONNECTION_CLOSE - retries_left + 1}/{MAX_TASK_RETRIES_ON_CONNECTION_CLOSE})"
                    )
            except Exception as exc:
                debug_log(
                    f"Episode failed for task={TASK_NAME}: {exc}",
                )

            finally:
                score = rewards[-1] if rewards else 0.0
                score = _clamp_open_unit_interval(score, eps=1e-6)
                score_threshold = SUCCESS_SCORE_THRESHOLD_BY_TASK.get(
                    TASK_NAME, SUCCESS_SCORE_THRESHOLD
                )
                success = (
                    episode_done and not episode_truncated and score >= score_threshold
                )

                log_end(
                    success=success, steps=steps_taken, score=score, rewards=rewards
                )

            if should_retry_task:
                retries_left -= 1
                continue
            break


if __name__ == "__main__":
    asyncio.run(main())
