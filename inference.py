"""
Inference Script Example
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.
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
    - Each tasks should return score in [0, 1]

  Example:
    [START] task=click-test env=miniwob model=Qwen3-VL-30B
    [STEP] step=1 action=click('123') reward=0.00 done=false error=null
    [STEP] step=2 action=fill('456','text') reward=0.00 done=false error=null
    [STEP] step=3 action=click('789') reward=1.00 done=true error=null
    [END] success=true steps=3 score=1.00 rewards=0.00,0.00,1.00
"""

import asyncio
import json
import os
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

LLM_BASE_URL = os.getenv("OPENROUTER_API_BASE_URL") or os.getenv(
    "LLM_BASE_URL", "https://router.huggingface.co/v1"
)
ENV_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
API_DELAY = float(os.getenv("API_DELAY", "0"))

MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen3-8B")
API_KEY = os.getenv("OPENROUTER_API_KEY") or os.getenv("HF_TOKEN")

BENCHMARKS = ["POD_RECOVERY", "AUTOSCALING", "INCIDENT"]
TASK_NAMES = ["pod_recovery", "autoscaling", "incident"]

TEMPERATURE = 0.7
MAX_TOKENS = 150
SUCCESS_SCORE_THRESHOLD = 0.1  # normalized score in [0, 1]
DEFAULT_MAX_STEPS = 15

SUCCESS_SCORE_THRESHOLD_BY_TASK: Dict[str, float] = {
    "pod_recovery": 0.9,
    "autoscaling": 0.9,
    "incident": 0.8,
}

MAX_STALL_REPEATS = 4
REWARD_EPSILON = 1e-9

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
    You are a Kubernetes incident-response agent.
    Return ONLY valid JSON for one action with this schema:
    {
            "action_type": "scale|delete_pod|patch|rollout_restart|set_hpa|drain_node|describe|wait",
      "deployment": "... optional ...",
      "replicas": 1,
      "pod_name": "...",
      "resource_type": "deployment|pod|node|service|configmap|hpa",
      "name": "...",
      "patch": {},
      "min_replicas": 1,
      "max_replicas": 5,
      "cpu_target_percent": 70,
      "node_name": "..."
    }
    Do not include markdown, prose, or code fences.
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


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}",
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
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return None
    return None


def _heuristic_action(
    task_name: str,
    observation: Any,
    history: Optional[List[str]] = None,
) -> Dict[str, Any]:
    obs = _to_dict(observation)
    pods = obs.get("pods", [])
    history = history or []

    if task_name == "pod_recovery":
        crashloop = [
            p
            for p in pods
            if p.get("deployment") == "frontend"
            and p.get("status") == "CrashLoopBackOff"
        ]
        if crashloop:
            return {"action_type": "rollout_restart", "deployment": "frontend"}
        running = [
            p
            for p in pods
            if p.get("deployment") == "frontend" and p.get("status") == "Running"
        ]
        if running:
            return {"action_type": "wait"}
        return {
            "action_type": "describe",
            "resource_type": "deployment",
            "name": "frontend",
        }

    if task_name == "autoscaling":
        backend_pods = [p for p in pods if p.get("deployment") == "backend"]
        running_backends = [p for p in backend_pods if p.get("status") == "Running"]
        hpas = obs.get("hpas", [])
        backend_hpa = next((h for h in hpas if h.get("name") == "backend-hpa"), None)

        if len(running_backends) < len(backend_pods) * 0.5:
            return {"action_type": "rollout_restart", "deployment": "backend"}

        if not backend_hpa:
            return {
                "action_type": "set_hpa",
                "deployment": "backend",
                "min_replicas": 2,
                "max_replicas": 6,
                "cpu_target_percent": 70,
            }

        if len(running_backends) >= len(backend_pods) * 0.8:
            return {"action_type": "wait"}

        return {"action_type": "rollout_restart", "deployment": "backend"}

    key_services = ["auth-service", "api-gateway", "frontend"]
    unhealthy = []
    for svc in key_services:
        svc_pods = [p for p in pods if p.get("deployment") == svc]
        running = [p for p in svc_pods if p.get("status") == "Running"]
        if not running or len(running) < len(svc_pods):
            unhealthy.append(svc)

    if unhealthy:
        return {"action_type": "rollout_restart", "deployment": unhealthy[0]}

    return {"action_type": "wait"}

    return {"action_type": "rollout_restart", "deployment": "auth-service"}


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


def get_model_action(
    client: OpenAI, task_name: str, step: int, observation: Any, history: List[str]
) -> Dict[str, Any]:
    user_prompt = build_user_prompt(task_name, step, observation, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        text = (completion.choices[0].message.content or "").strip()
        parsed = _safe_json_action(text)
        if isinstance(parsed, dict):
            return _normalize_action(parsed)
        return _heuristic_action(task_name, observation, history)
    except Exception as exc:
        print(f"[DEBUG] Model request failed: {exc}", flush=True)
        return _heuristic_action(task_name, observation, history)


async def main() -> None:
    if not API_KEY:
        raise RuntimeError("Missing HF_TOKEN/API_KEY for OpenAI client.")
    for TASK_NAME, BENCHMARK in zip(TASK_NAMES, BENCHMARKS):
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

                    history.append(f"Step {step}: {action_str} -> reward {reward:+.2f}")

                    if done:
                        break

            world_state = _to_dict(final_obs) if final_obs is not None else {}
            score = grader(world_state, steps_taken, max_steps)
            score = min(max(score, 0.0), 1.0)
            success = episode_done and not stalled and steps_taken > 0

        finally:
            log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


if __name__ == "__main__":
    asyncio.run(main())
