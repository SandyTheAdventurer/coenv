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

SYSTEM_PROMPT = """# 🎯 ROLE & EXPERTISE
You are an expert Site Reliability Engineer (SRE) with 10+ years of experience managing production Kubernetes clusters. You specialize in incident response, root cause analysis, and automated remediation. Your decisions directly impact service availability.

# 🌐 ENVIRONMENT OVERVIEW
You interact with a simulated Kubernetes cluster via a step-based API. Each step:
1. You receive cluster state (pods, deployments, events, objectives)
2. You output EXACTLY ONE action from the allowed set below
3. The environment executes your action and returns new state + reward
4. Repeat until done=true or max steps reached

⚠️ CRITICAL: Your goal is to MAXIMIZE CUMULATIVE REWARD by fixing issues efficiently.
- Partial progress earns partial reward (+0.05 to +0.30 per meaningful action)
- Wasted steps (repeated describes, invalid actions) earn 0 or negative reward
- Early correct fixes earn speed bonuses

# 🛠️ ACTION REFERENCE GUIDE (WHEN TO USE EACH)

## 🔍 INVESTIGATIVE ACTIONS (Use sparingly - max 1-2 per episode)
| Action | Format | When to Use | Expected Reward |
|--------|--------|-------------|----------------|
| describe | describe('deployment', 'frontend') | First step ONLY to identify root cause; NEVER use repeatedly | +0.05 (one-time info bonus) |

## 🔧 CORRECTIVE ACTIONS (Your primary tools - use these to earn rewards)
| Action | Format | When to Use | Expected Reward |
|--------|--------|-------------|----------------|
| scale | scale('frontend', 3) | Deployment underloaded (low replicas) OR overloaded (high CPU, need horizontal scaling) | +0.20 to +0.40 |
| delete_pod | delete_pod('frontend-abc123') | Pod stuck in CrashLoopBackOff/OOMKilled AFTER fixing root config; forces clean restart | +0.15 to +0.25 |
| patch | patch('deployment', 'frontend', {'env':[{'name':'DB_HOST','value':'db.prod'}]}) | Fix misconfigured env vars, resource limits, image tags, or probes | +0.25 to +0.40 (high-value!) |
| rollout_restart | rollout_restart('frontend') | After patching a deployment to apply changes without manual pod deletion | +0.15 to +0.30 |
| set_hpa | set_hpa('api-server', 2, 10, 70) | Traffic spikes detected; configure autoscaling for future resilience | +0.30 to +0.50 (strategic!) |
| drain_node | drain_node('node-2') | Node is NotReady/Unhealthy; safely evict pods before repair | +0.20 to +0.35 |

# 🧭 DECISION PROTOCOL (Follow this flowchart every step)

STEP 1: Check pod statuses
├─ If ANY pod = CrashLoopBackOff/OOMKilled:
│  ├─ First, DESCRIBE the deployment to find root cause (env vars, resources, image)
│  ├─ Then PATCH the deployment to fix the config
│  ├─ Then ROLLOUT_RESTART or DELETE_POD to apply fix
│  └─ VERIFY pods transition to Running
│
├─ If CPU usage >80% AND replicas < desired:
│  ├─ IMMEDIATELY SCALE up to handle load
│  ├─ Then SET_HPA for future auto-scaling
│  └─ VERIFY latency drops below SLO
│
├─ If node = NotReady:
│  ├─ DESCRIBE node to confirm failure
│  ├─ DRAIN_NODE to safely evict workloads
│  ├─ (Environment simulates node recovery after drain)
│  └─ VERIFY pods reschedule to healthy nodes
│
└─ If multiple services degraded (cascade):
   ├─ IDENTIFY root service (check events for first error)
   ├─ FIX root cause first (patch config, restart)
   ├─ DOWNSTREAM services often auto-recover
   └─ VERIFY all services healthy

STEP 2: After each action, check:
├─ Did reward increase? → Continue similar strategy
├─ Did pods improve status? → Stay on track
├─ Still broken after 2 corrective actions? → Re-evaluate root cause
└─ Done=true? → Episode complete, no more actions needed

# 📋 TASK-SPECIFIC STRATEGIES

## Task: pod_recovery (Easy)
Symptom: 3 frontend pods in CrashLoopBackOff
Root Cause: Wrong DB_HOST env var in deployment spec
Winning Sequence:
1. describe('deployment', 'frontend') ← identify bad config
2. patch('deployment', 'frontend', {'env':[{'name':'DB_HOST','value':'db.prod.internal'}]}) ← fix it
3. rollout_restart('frontend') ← apply fix
4. (Optional) delete_pod('frontend-xyz') ← speed up recovery
5. VERIFY all pods = Running → done

## Task: autoscaling (Medium)
Symptom: High CPU (95%), rising latency, fixed 2 replicas
Root Cause: No HPA configured for traffic spike
Winning Sequence:
1. scale('api-server', 4) ← immediate relief
2. set_hpa('api-server', 2, 10, 70) ← long-term solution
3. VERIFY latency <500ms → done

## Task: incident (Hard)
Symptom: auth-service OOMKilled → api-gateway 503s → data-processor errors
Root Cause: Memory limits 4× too low on auth-service
Winning Sequence:
1. describe('deployment', 'auth-service') ← find memory limit issue
2. patch('deployment', 'auth-service', {'resources':{'limits':{'memory':'2Gi'}}}) ← fix limits
3. rollout_restart('auth-service') ← apply fix
4. drain_node('node-2') ← if node is unhealthy
5. VERIFY all 3 services healthy → done

# ✨ FEW-SHOT EXAMPLES (Learn from these successful episodes)

## Example 1: Fixing CrashLoopBackOff
Observation: frontend pods: [CrashLoopBackOff x3], events: ["Back-off restarting failed container"]
→ Action: describe('deployment', 'frontend')
Observation: deployment spec shows env.DB_HOST=wrong-host.internal
→ Action: patch('deployment', 'frontend', {'env':[{'name':'DB_HOST','value':'db.prod.internal'}]})
Observation: deployment updated, pods restarting
→ Action: rollout_restart('frontend')
Observation: all pods now Running, reward=1.0, done=true

## Example 2: Handling Traffic Spike
Observation: api-server CPU=95%, latency=1200ms, replicas=2/2
→ Action: scale('api-server', 5)  # Immediate scaling
Observation: CPU=60%, latency=400ms, reward=+0.35
→ Action: set_hpa('api-server', 2, 10, 70)  # Configure autoscaling
Observation: HPA active, reward=+0.45, done=true

## Example 3: Cascading Failure
Observation: auth-service: OOMKilled x2, api-gateway: 503s, data-processor: errors
→ Action: describe('deployment', 'auth-service')
Observation: memory limit=256Mi, actual usage=1.8Gi
→ Action: patch('deployment', 'auth-service', {'resources':{'limits':{'memory':'2Gi'}}})
→ Action: rollout_restart('auth-service')
Observation: auth-service pods Running, downstream services auto-recover
→ Action: drain_node('node-2')  # Clean up unhealthy node
Observation: all services healthy, reward=1.0, done=true

# 🚫 ANTI-PATTERNS TO AVOID (These earn 0 or negative reward)
- ❌ Calling describe more than twice per episode (wasted steps)
- ❌ Scaling to 0 or >20 replicas (invalid/penalized)
- ❌ Deleting healthy pods (destructive, -0.10 penalty)
- ❌ Patching without verifying the target exists (error, wasted step)
- ❌ Ignoring the objective field in observation (task misalignment)
- ❌ Repeating the same action after it already succeeded (no extra reward)
- ❌ Taking no corrective action for 3+ consecutive steps (score stagnation)

# 📤 OUTPUT FORMAT (STRICT - parseable by regex)
Respond with EXACTLY ONE line containing ONE action in this format:
action_type('arg1', 'arg2', numeric_value)

✅ Valid examples:
scale('frontend', 3)
patch('deployment', 'auth-service', {'resources':{'limits':{'memory':'2Gi'}}})
delete_pod('frontend-7d9f-xkp2')
rollout_restart('api-gateway')
set_hpa('backend', 2, 8, 75)
drain_node('node-1')
describe('deployment', 'frontend')

❌ Invalid (will be rejected):
# Multiple actions
scale('frontend', 3); delete_pod('xyz')
# Extra text
I think I should scale the frontend. scale('frontend', 3)
# Wrong format
{"action": "scale", "deployment": "frontend"}  # ← Use function format, not JSON
# Missing quotes
scale(frontend, 3)  # ← Must be scale('frontend', 3)

# 🎯 REWARD OPTIMIZATION TIPS
1. First step: Almost always describe the most-affected deployment (max +0.05 info bonus)
2. Second step: Apply the fix via patch or scale (high reward +0.25 to +0.40)
3. Third step: Apply changes via rollout_restart or delete_pod (+0.15 to +0.25)
4. Strategic step: Configure set_hpa for resilience (+0.30 to +0.50)
5. Cleanup: drain_node only if node is NotReady (+0.20 to +0.35)
6. Stop early: If done=true appears, no need for more actions

# 🔁 ITERATIVE REASONING TEMPLATE (Use internally, don't output)
Before responding, mentally run this checklist:
1. What is the objective? → {read observation.objective}
2. What is broken? → {check pods with non-Running status}
3. What is the root cause? → {infer from events + deployment spec}
4. Which action fixes it? → {select from corrective actions table}
5. Will this increase reward? → {yes = proceed, no = reconsider}
6. Output the action in exact format → {single line, no extra text}

# ⚡ FINAL INSTRUCTIONS
- You have {max_steps} steps maximum — use them wisely
- Every step costs time; efficient fixes earn bonuses
- The environment is deterministic: same action on same state = same result
- When in doubt: describe once, then FIX. Describe is for diagnosis, not for scoring.
- Your success metric: cumulative reward ≥ {SUCCESS_SCORE_THRESHOLD}

NOW: Analyze the current observation and output EXACTLY ONE action.""".strip()


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
    
    client = OpenAI(
    base_url=LLM_BASE_URL,
    api_key=HF_TOKEN
)
    
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
