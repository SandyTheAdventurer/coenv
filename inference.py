"""
COEnv Inference Script
Used by validators to run episodes with LLMs
MANDATORY: Uses OpenAI Client for LLM calls
"""

import os
import sys
import asyncio
import argparse
import re
from typing import List, Optional

# Try to load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from openai import OpenAI
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen3-8B")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://router.huggingface.co/v1")
HF_TOKEN = os.getenv("HF_TOKEN")

MAX_STEPS = 15
SUCCESS_SCORE_THRESHOLD = 0.5

SYSTEM_PROMPT = """You are a Kubernetes cluster administrator. The environment simulates a Kubernetes cluster.
You need to diagnose and fix issues in the cluster.

Available actions:
1. scale(deployment, replicas) - Scale a deployment to specified replicas
2. delete_pod(pod_name) - Delete a specific pod
3. patch(resource_type, name, patch) - Patch a resource with JSON patch
4. rollout_restart(deployment) - Restart a deployment rollout
5. set_hpa(deployment, min_replicas, max_replicas, cpu_target_percent) - Set HPA for a deployment
6. drain_node(node_name) - Drain a node
7. describe(resource_type, name) - Get details of a resource

Respond with EXACTLY one action in the format: action_type(arguments)
Example: scale('frontend', 3)
Example: describe('deployment', 'frontend')
Example: rollout_restart('frontend')

Do not include any other text in your response."""


def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    print(f"[STEP] step={step} action={action} reward={reward:.2f} done={done_val} error={error_val}", flush=True)


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={str(success).lower()} steps={steps} score={score:.3f} rewards={rewards_str}", flush=True)


def parse_action(response: str) -> dict:
    """Parse LLM response into action dict."""
    response = response.strip()
    
    try:
        if response.startswith("scale("):
            import re
            match = re.search(r"scale\(['\"](.+?)['\"],\s*(\d+)\)", response)
            if match:
                return {"action_type": "scale", "deployment": match.group(1), "replicas": int(match.group(2))}
        
        elif response.startswith("delete_pod("):
            import re
            match = re.search(r"delete_pod\(['\"](.+?)['\"]\)", response)
            if match:
                return {"action_type": "delete_pod", "pod_name": match.group(1)}
        
        elif response.startswith("patch("):
            import re
            match = re.search(r"patch\(['\"](.+?)['\"],\s*['\"](.+?)['\"],\s*(.+)\)", response)
            if match:
                return {"action_type": "patch", "resource_type": match.group(1), "name": match.group(2), "patch": {}}
        
        elif response.startswith("rollout_restart("):
            import re
            match = re.search(r"rollout_restart\(['\"](.+?)['\"]\)", response)
            if match:
                return {"action_type": "rollout_restart", "deployment": match.group(1)}
        
        elif response.startswith("set_hpa("):
            import re
            match = re.search(r"set_hpa\(['\"](.+?)['\"],\s*(\d+),\s*(\d+),\s*(\d+)\)", response)
            if match:
                return {"action_type": "set_hpa", "deployment": match.group(1), "min_replicas": int(match.group(2)), "max_replicas": int(match.group(3)), "cpu_target_percent": int(match.group(4))}
        
        elif response.startswith("drain_node("):
            import re
            match = re.search(r"drain_node\(['\"](.+?)['\"]\)", response)
            if match:
                return {"action_type": "drain_node", "node_name": match.group(1)}
        
        elif response.startswith("describe("):
            import re
            match = re.search(r"describe\(['\"](.+?)['\"],\s*['\"](.+?)['\"]\)", response)
            if match:
                return {"action_type": "describe", "resource_type": match.group(1), "name": match.group(2)}
    except Exception:
        pass
    
    return {"action_type": "describe", "resource_type": "deployment", "name": "frontend"}


def build_user_prompt(observation: dict, step: int) -> str:
    pods = observation.get('pods', [])[:5]
    deployments = observation.get('deployments', [])[:3]
    events = observation.get('events', [])[-3:]
    objective = observation.get('objective', '')
    step_count = observation.get('step', 0)
    
    pods_info = "\n".join([f"- {p.get('name')}: {p.get('status')} (restarts: {p.get('restarts')})" for p in pods])
    deployments_info = "\n".join([f"- {d.get('name')}: {d.get('desired_replicas')}/{d.get('available_replicas')} replicas" for d in deployments])
    events_info = "\n".join([f"- {e.get('reason')}: {e.get('message')}" for e in events]) if events else "No recent events"
    
    return f"""Current cluster state (step {step_count}):
Objective: {objective}

Deployments:
{deployments_info}

Pods:
{pods_info}

Recent Events:
{events_info}

What action should be taken? Respond with exactly one action."""


def get_model_action(client: OpenAI, observation: dict, step: int) -> dict:
    user_prompt = build_user_prompt(observation, step)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=200,
            stream=False,
        )
        response = (completion.choices[0].message.content or "").strip()
        return parse_action(response)
    except Exception as e:
        print(f"[DEBUG] Model request failed: {e}", flush=True)
        return {"action_type": "describe", "resource_type": "deployment", "name": "frontend"}


async def main() -> None:
    parser = argparse.ArgumentParser(description='Run COEnv inference')
    parser.add_argument('--api-base-url', type=str, default=API_BASE_URL, help='Base URL for the COEnv API')
    parser.add_argument('--model-name', type=str, default=MODEL_NAME, help='Name of the model to use')
    parser.add_argument('--hf-token', type=str, default=None, help='Hugging Face token (if needed)')
    parser.add_argument('--task-id', type=str, default='pod_recovery', help='Task ID to run')
    parser.add_argument('--max-steps', type=int, default=MAX_STEPS, help='Maximum steps per episode')
    
    args = parser.parse_args()
    
    env_url = args.api_base_url.rstrip('/')
    model_name = args.model_name
    hf_token = args.hf_token or HF_TOKEN
    task_id = args.task_id
    max_steps = args.max_steps
    
    client = OpenAI(base_url=LLM_BASE_URL, api_key=hf_token)
    
    log_start(task=task_id, env="coenv", model=model_name)
    
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False
    error_msg = None
    
    reset_url = f"{env_url}/reset"
    try:
        response = requests.post(reset_url, json={"task": task_id}, timeout=30)
        response.raise_for_status()
        result = response.json()
        observation = result.get('observation', {})
        reward = result.get('reward', 0.0)
        done = result.get('done', False)
    except Exception as e:
        error_msg = str(e)
        print(f"[ERROR] Failed to reset environment: {e}")
        log_end(success=False, steps=0, score=0.0, rewards=[])
        return
    
    for step in range(1, max_steps + 1):
        if done:
            break
        
        action = get_model_action(client, observation, step)
        
        action_str = str(action)
        
        step_url = f"{env_url}/step"
        try:
            response = requests.post(step_url, json={"action": action}, timeout=30)
            response.raise_for_status()
            result = response.json()
            
            reward = result.get('reward', 0.0)
            done = result.get('done', False)
            observation = result.get('observation', {})
            
            rewards.append(reward)
            steps_taken = step
            
            log_step(step=step, action=action_str, reward=reward, done=done, error=None)
            
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] Failed to step environment: {e}", flush=True)
            log_step(step=step, action=action_str, reward=0.0, done=True, error=error_msg)
            break
    
    score = sum(rewards) / max_steps if rewards else 0.0
    score = min(max(score, 0.0), 1.0)
    success = score >= SUCCESS_SCORE_THRESHOLD
    
    log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


if __name__ == "__main__":
    asyncio.run(main())
