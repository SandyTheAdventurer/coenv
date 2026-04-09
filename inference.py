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
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

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

from server.graders.grader_pod_recovery import grade as grade_pod_recovery
from server.graders.grader_autoscaling import grade as grade_autoscaling
from server.graders.grader_incident import grade as grade_incident

if load_dotenv is not None:
    load_dotenv()

ENV_URL = os.getenv("ENV_URL", "https://Nightreigners-COEnv.hf.space")

LLM_BASE_URL = (
    os.getenv("API_BASE_URL")
    or os.getenv("LLM_BASE_URL")
    or "https://router.huggingface.co/v1"
)
MODEL_NAME = os.environ.get("MODEL_NAME", "Qwen/Qwen3-8B")
API_KEY = os.getenv("API_KEY") or os.getenv("HF_TOKEN") or os.getenv("OPENAI_API_KEY")

API_DELAY = 4
BENCHMARKS = ["POD_RECOVERY", "AUTOSCALING", "INCIDENT"]
TASK_NAMES = ["pod_recovery", "autoscaling", "incident"]

TEMPERATURE = 0.3
MAX_TOKENS = 512
SUCCESS_SCORE_THRESHOLD = 0.1  # normalized score in [0, 1]
DEFAULT_MAX_STEPS = 15

SUCCESS_SCORE_THRESHOLD_BY_TASK: Dict[str, float] = {
    "pod_recovery": 0.9,
    "autoscaling": 0.9,
    "incident": 0.8,
}

MAX_STALL_REPEATS = 4
REWARD_EPSILON = 1e-9
MAX_TASK_RETRIES_ON_CONNECTION_CLOSE = 1
SCORE_EPSILON = 1e-4

MAX_STEPS_BY_TASK = {
    "pod_recovery": 15,
    "autoscaling": 20,
    "incident": 20,
}

GRADERS: Dict[str, Callable[[Dict[str, Any], int, int], float]] = {
    "pod_recovery": grade_pod_recovery,
    "autoscaling": grade_autoscaling,
    "incident": grade_incident,
}

SYSTEM_PROMPT = textwrap.dedent(
    """
    You are a Kubernetes incident-response agent. Your reply must be ONLY a JSON object — no preamble, no explanation, no markdown, no code fences, no thinking text.
    Remember that more actions and more dangerous actions taken will reduce the final score, so be efficient and only take necessary actions.

    Valid action_type values: scale, delete_pod, patch, rollout_restart, set_hpa, drain_node, describe, wait

    Action fields:
    - action_type (required)
    - deployment: name of deployment (for scale/rollout_restart/patch/set_hpa)
    - replicas: integer (for scale)
    - pod_name: name of pod (for delete_pod)
    - resource_type: one of deployment, pod, node, service, configmap, hpa (for describe/patch)
    - name: resource name (for describe/patch)
    - patch: JSON patch spec (for patch)
    - min_replicas, max_replicas, cpu_target_percent: integers (for set_hpa)
    - node_name: string (for drain_node)

    EXAMPLE VALID REPLIES:
    {"action_type":"describe","resource_type":"deployment","name":"frontend"}
    {"action_type":"rollout_restart","deployment":"frontend"}
    {"action_type":"delete_pod","pod_name":"frontend-9722-auksc"}

    YOUR REPLY (JSON only, nothing else):
    """
).strip()


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


def _observation_summary(observation: Any) -> str:
    obs = _to_dict(observation)
    pods = obs.get("pods", [])
    deployments = obs.get("deployments", [])
    events = obs.get("events", [])

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

    return textwrap.dedent(
        f"""
        Objective: {obs.get("objective", "")}
        Step: {obs.get("step", 0)}
        Pod status counts: {pod_status_counts}
        Deployments:
        {chr(10).join(deployment_lines) if deployment_lines else "None"}
        Recent events:
        {chr(10).join(recent_events) if recent_events else "None"}
        """
    ).strip()


def build_user_prompt(
    task_name: str, step: int, observation: Any, history: List[str]
) -> str:
    history_block = "\n".join(history[-4:]) if history else "None"
    return textwrap.dedent(
        f"""
        Task: {task_name}
        Step: {step}
        Current cluster summary:
        {_observation_summary(observation)}
        Previous steps:
        {history_block}
        Return one valid next action as pure JSON.
        """
    ).strip()


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
            if isinstance(name_val, str):
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
    try:
        parsed = json.loads(text)
        extracted = _extract_action_dict(parsed)
        return (
            extracted
            if extracted is not None
            else (parsed if isinstance(parsed, dict) else None)
        )
    except json.JSONDecodeError:
        pass

    import re

    patterns = [
        r"\{[^{}]*\}",
        r"\{[^{}]*\{[^{}]*\}[^{}]*\}",
        r"\{[^{}]*\{[^{}]*\{[^{}]*\}[^{}]*\}[^{}]*\}",
    ]
    for pattern in patterns:
        matches = re.findall(pattern, text)
        for match in matches:
            try:
                parsed = json.loads(match)
                extracted = _extract_action_dict(parsed)
                return (
                    extracted
                    if extracted is not None
                    else (parsed if isinstance(parsed, dict) else None)
                )
            except json.JSONDecodeError:
                continue

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            extracted = _extract_action_dict(parsed)
            return (
                extracted
                if extracted is not None
                else (parsed if isinstance(parsed, dict) else None)
            )
        except json.JSONDecodeError:
            pass

    lines = text.split("\n")
    for line in lines:
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                parsed = json.loads(line)
                extracted = _extract_action_dict(parsed)
                return (
                    extracted
                    if extracted is not None
                    else (parsed if isinstance(parsed, dict) else None)
                )
            except json.JSONDecodeError:
                continue

    return None


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


def get_model_action(
    client: OpenAI, task_name: str, step: int, observation: Any, history: List[str]
) -> Dict[str, Any]:
    user_prompt = build_user_prompt(task_name, step, observation, history)

    for attempt in range(5):  # retry once with stronger prompt
        try:
            prompt = (
                user_prompt
                if attempt == 0
                else (
                    user_prompt
                    + "\n\nCRITICAL: Reply with ONLY a JSON object. No other text whatsoever."
                )
            )
            completion = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=TEMPERATURE if attempt == 0 else 0.0,
                max_tokens=MAX_TOKENS,
                stream=False,
            )
            text = (completion.choices[0].message.content or "").strip()
            parsed = _safe_json_action(text)
            if isinstance(parsed, dict):
                return _normalize_action(parsed)
        except Exception as exc:
            print(f"Model request failed: {exc}", file=sys.stderr, flush=True)
            if attempt == 1:
                raise exc

    # If both attempts failed, fall back to a useful task-aware action.
    return _normalize_action(_task_fallback_action(task_name, step, observation))


async def main() -> None:
    if not API_KEY:
        raise RuntimeError(
            "Missing API_KEY (or fallback HF_TOKEN/OPENAI_API_KEY) for OpenAI client."
        )
    for TASK_NAME, BENCHMARK in zip(TASK_NAMES, BENCHMARKS):
        retries_left = MAX_TASK_RETRIES_ON_CONNECTION_CLOSE

        while True:
            client = OpenAI(base_url=LLM_BASE_URL, api_key=API_KEY)
            max_steps = MAX_STEPS_BY_TASK.get(TASK_NAME, DEFAULT_MAX_STEPS)
            grader = GRADERS.get(TASK_NAME, grade_pod_recovery)

            history: List[str] = []
            rewards: List[float] = []
            steps_taken = 0
            score = 0.0
            success = False
            final_obs: Optional[Any] = None
            episode_done = False
            stalled = False
            should_retry_task = False

            log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

            try:
                async with CoEnv(base_url=ENV_URL) as env:
                    result = await env.reset(task=TASK_NAME)
                    final_obs = result.observation

                    for step in range(1, max_steps + 1):
                        if API_DELAY > 0:
                            await asyncio.sleep(API_DELAY)
                        if result.done:
                            log_step(
                                step=step,
                                action="",
                                reward=result.reward or 0.0,
                                done=True,
                                error=None,
                            )
                            break

                        action_payload = get_model_action(
                            client, TASK_NAME, step, final_obs, history
                        )
                        action = CoenvAction(**action_payload)

                        result = await env.step(action)
                        obs = result.observation
                        final_obs = obs

                        reward = result.reward or 0.0
                        done = result.done
                        error = (
                            (obs.metadata or {}).get("error")
                            if hasattr(obs, "metadata")
                            else None
                        )

                        rewards.append(reward)
                        steps_taken = step
                        episode_done = bool(done)

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
            except websockets.exceptions.ConnectionClosedError:
                print(
                    f"Connection closed unexpectedly for task={TASK_NAME}",
                    file=sys.stderr,
                    flush=True,
                )
                stalled = True
                should_retry_task = retries_left > 0
                if should_retry_task:
                    print(
                        f"Retrying task={TASK_NAME} ({MAX_TASK_RETRIES_ON_CONNECTION_CLOSE - retries_left + 1}/{MAX_TASK_RETRIES_ON_CONNECTION_CLOSE})",
                        file=sys.stderr,
                        flush=True,
                    )
            except Exception as exc:
                print(
                    f"Episode failed for task={TASK_NAME}: {exc}",
                    file=sys.stderr,
                    flush=True,
                )
                stalled = True

            finally:
                score = sum(rewards) / len(rewards) if rewards else 0.0
                score = _clamp_open_unit_interval(score, eps=1e-6)
                success = score >= SUCCESS_SCORE_THRESHOLD

                log_end(
                    success=success, steps=steps_taken, score=score, rewards=rewards
                )

            if should_retry_task:
                retries_left -= 1
                continue
            break


if __name__ == "__main__":
    asyncio.run(main())
