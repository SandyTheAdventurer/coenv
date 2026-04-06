# COEnv — Project Documentation
### Meta × Hugging Face OpenEnv RL Hackathon

---

## Table of Contents

1. [What Is This Project?](#1-what-is-this-project)
2. [Why Kubernetes?](#2-why-kubernetes)
3. [How It Works — The Big Picture](#3-how-it-works--the-big-picture)
4. [The Three Layers Explained](#4-the-three-layers-explained)
5. [Team Ownership](#5-team-ownership)
6. [Full Project Directory Structure](#6-full-project-directory-structure)
7. [The Three Tasks (Easy → Medium → Hard)](#7-the-three-tasks-easy--medium--hard)
8. [Reward & Grading Design](#8-reward--grading-design)
9. [The Complete Episode Flow](#9-the-complete-episode-flow)
10. [OpenEnv Spec Compliance Checklist](#10-openenv-spec-compliance-checklist)
11. [Submission Checklist](#11-submission-checklist)
12. [Key Technical Decisions](#12-key-technical-decisions)

---

## 1. What Is This Project?

**COEnv** is a Reinforcement Learning environment that simulates real-world Kubernetes cluster operations. An AI agent (LLM) is placed inside a broken or degraded Kubernetes cluster and must figure out the right sequence of operations to fix it — just like a real Site Reliability Engineer (SRE) would.

This is built for the **Meta × Hugging Face OpenEnv RL Hackathon**, which requires:
- A real-world task simulation (not games or toys)
- Full OpenEnv interface implementation (`step()`, `reset()`, `state()`)
- At least 3 tasks with programmatic graders (easy → medium → hard)
- A meaningful reward function that gives partial credit throughout the episode
- A working `inference.py` that runs an LLM agent and logs structured output
- Deployment on Hugging Face Spaces with a working Dockerfile

**In simple terms:** We fake a Kubernetes cluster in Python memory, break it in specific ways, and then let an LLM try to fix it step by step — scoring it on how well it does.

---

## 2. Why Kubernetes?

Kubernetes (k8s) is the industry-standard container orchestration system used by virtually every tech company running production software. Managing it is genuinely difficult and is a daily job for SREs and DevOps engineers worldwide.

**Why it's a perfect RL environment:**

| RL Concept | Kubernetes Equivalent |
|---|---|
| State | Cluster state (pod statuses, node health, resource usage) |
| Action | kubectl commands (scale, patch, delete, restart) |
| Reward | How close the cluster is to a healthy target state |
| Episode | One incident recovery scenario |
| Done | All SLOs restored / all pods healthy |

**Why it's novel for OpenEnv:** None of Meta's reference environments (calendar, REPL, browser, CARLA, reasoning gym) touch infrastructure operations. This fills a real gap.

**Why it's practical:** Companies would immediately use an environment like this to train or evaluate agents that assist SREs — the real-world utility score (30% of judging) is very high.

---

## 3. How It Works — The Big Picture

Think of the project as three concentric layers:

```
┌─────────────────────────────────────────────────────────┐
│                   LAYER 1 — RL ENVIRONMENT               │
│  inference.py  ←→  main.py (FastAPI)  ←→  tasks/graders │
│                      (Sandeep)                           │
├─────────────────────────────────────────────────────────┤
│                LAYER 2 — SIMULATION ENGINE               │
│       world.py  ←→  models.py  ←→  conditions/          │
│                        (You)                             │
├─────────────────────────────────────────────────────────┤
│                LAYER 3 — ACTION SPACE                    │
│    worker.py  ←→  executor.py  ←→  actions/  ←→  validator│
│                    (Third Person)                        │
└─────────────────────────────────────────────────────────┘
```

**Layer 1 (Sandeep)** is what the judges see — the API endpoints, the inference script, the task definitions, the graders, the README.

**Layer 2 (You)** is the fake Kubernetes cluster. It holds the state of the cluster, knows how pods transition between statuses, and can inject failures. Everything sits in Python dictionaries — no real Kubernetes cluster runs.

**Layer 3 (Third Person)** is the action space — the specific operations the LLM agent is allowed to perform, and the validation/execution bridge that translates those actions into state changes in the simulator.

---

## 4. The Three Layers Explained

### Layer 1 — RL Environment (Sandeep)

This layer is the **public contract** of the project. It's what OpenEnv's `validate` command checks, what the judges' scripts call, and what the LLM agent talks to.

**`main.py` — FastAPI application**

The central API server. It exposes exactly three mandatory endpoints:

- `POST /reset` — Starts a new episode. Sets up a broken cluster using one of the condition injectors. Returns the initial `ClusterObservation` (what the agent sees first).
- `POST /step` — Receives an action from the agent. Validates it, executes it on the simulated cluster, advances time by one tick, and returns the new observation + reward + done flag + info.
- `GET /state` — Returns the full current cluster state. Used for debugging and grading.

**`inference.py` — LLM agent runner**

This is the script the hackathon validators actually run. It:
1. Reads `API_BASE_URL`, `MODEL_NAME`, `HF_TOKEN` from environment variables
2. Calls `/reset` to start an episode
3. Feeds the observation to the LLM using the OpenAI client
4. Parses the LLM's response as a structured action
5. Calls `/step` with that action
6. Prints structured stdout logs after every step:
   ```
   [START] task=pod-recovery env=coenv model=Qwen3-VL-30B
   [STEP] step=1 action=delete_pod('frontend-7d9f-xkp2') reward=0.20 done=false error=null
   [STEP] step=2 action=scale('frontend',3) reward=0.60 done=false error=null
   [END] success=true steps=2 rewards=0.20,0.60
   ```
7. Repeats until `done=true` or `max_steps` is reached

**`openenv.yaml` — Spec metadata**

Required for `openenv validate` to pass. Contains:
- Environment name, version, description
- List of task IDs with difficulty labels
- References to the action schema and observation schema

**`classes/tasks/` — Task definitions**

Three Python files, each defining one task:
- What the broken state looks like (which condition to inject)
- What the agent's objective is (in plain English, passed to the LLM as a prompt)
- What counts as success
- Maximum number of steps allowed

**`classes/graders/` — Reward graders**

Three Python files, each implementing a `grade(world_state) -> float` function. Graders must be fully deterministic — same world state always returns same score. They implement partial credit: a grader doesn't just say "fixed or not fixed" but scores partial progress (e.g., 2 out of 5 pods fixed = 0.4).

**`Dockerfile`**

Single-stage Python container. Installs `requirements.txt`, copies the project, exposes port 8000, runs `uvicorn main:app`. Must build and run cleanly — this is a hard pass/fail gate.

**`README.md`**

Mandatory documentation. Must include: environment overview, motivation, action space definition, observation space definition, task descriptions with difficulty labels, setup instructions, baseline scores table.

---

### Layer 2 — Simulation Engine (You)

This is the **most important layer technically**. It's what makes the environment believable. Since we cannot run a real Kubernetes cluster inside a 2 vCPU / 8 GB HF Space container, the entire cluster is simulated as an in-memory Python object.

**`classes/world.py` — The cluster simulator**

This is the brain of the project. It maintains the complete cluster state as a Python dictionary, structured like a real Kubernetes API response:

```python
cluster_state = {
    "nodes": [
        {"name": "node-1", "status": "Ready", "cpu_capacity": 4, "mem_capacity": 8192},
        {"name": "node-2", "status": "NotReady", "cpu_capacity": 4, "mem_capacity": 8192}
    ],
    "deployments": [
        {"name": "frontend", "desired_replicas": 3, "available_replicas": 1, "image": "nginx:1.21"}
    ],
    "pods": [
        {"name": "frontend-7d9f-xkp2", "status": "CrashLoopBackOff", "node": "node-1", "restarts": 7},
        {"name": "frontend-7d9f-ab3c", "status": "Running", "node": "node-1", "restarts": 0},
        {"name": "frontend-7d9f-mn8x", "status": "Pending", "node": None, "restarts": 0}
    ],
    "services": [...],
    "configmaps": [...],
    "hpa": [...]
}
```

Key methods:
- `reset(condition)` — Wipes state, injects a failure condition, returns initial observation
- `get_pods(namespace, selector)` — Returns filtered pod list (mimics `kubectl get pods`)
- `apply_patch(resource_type, name, patch)` — Applies a patch to a resource
- `scale(deployment_name, replicas)` — Changes replica count
- `delete_pod(pod_name)` — Removes a pod (it gets recreated by the deployment controller on next tick)
- `tick()` — Advances simulated time by one step. Pods in `CrashLoopBackOff` increment their restart counter. Pending pods on ready nodes eventually transition to `Running`. Dead nodes stay dead unless drained.
- `get_observation()` — Serialises the current state into a `ClusterObservation` Pydantic model

**`classes/models.py` — Pydantic typed models**

All data structures are defined here. This is mandatory for OpenEnv spec compliance — typed models enforce the action/observation contract.

```python
class PodStatus(BaseModel):
    name: str
    status: Literal["Running", "Pending", "CrashLoopBackOff", "OOMKilled", "Terminating", "Unknown"]
    node: Optional[str]
    restarts: int
    cpu_usage: float
    mem_usage: float

class NodeStatus(BaseModel):
    name: str
    status: Literal["Ready", "NotReady", "SchedulingDisabled"]
    cpu_capacity: float
    mem_capacity: float
    cpu_usage: float
    mem_usage: float

class ClusterObservation(BaseModel):
    nodes: List[NodeStatus]
    pods: List[PodStatus]
    deployments: List[DeploymentStatus]
    services: List[ServiceStatus]
    events: List[ClusterEvent]          # recent k8s events (error messages, warnings)
    step: int
    objective: str                      # plain English description of what to fix

class RewardSignal(BaseModel):
    reward: float                       # 0.0 to 1.0 incremental reward this step
    cumulative: float                   # total reward so far
    done: bool
    info: Dict[str, Any]               # breakdown: why this reward was given
```

**`classes/conditions/` — Failure injectors**

Each condition is a Python class with a single `inject(cluster_state) -> cluster_state` method that takes a healthy cluster and returns a broken one. This is how each task starts with a specific failure scenario:

- `crash_loop.py` — Sets 3 pods to `CrashLoopBackOff` with high restart counts. Simulates a bad image tag or missing environment variable.
- `oom_kill.py` — Sets pods to `OOMKilled`. Memory limits are set too low in the deployment spec. Pods keep restarting.
- `node_failure.py` — Sets one node to `NotReady`. All pods on that node go to `Unknown`. New pods are `Pending` (no space to schedule).
- `cascade_failure.py` — Combines multiple failures: one OOMKilled service causes downstream 503s in two dependent services, creating a cascading failure across 3 deployments.

**`classes/utils.py` — Probability and simulation helpers**

Utility functions that make the simulation feel realistic:
- `sample_cpu_usage(base_load, noise_factor)` — Returns a slightly randomised CPU % (real clusters are never exactly at baseline)
- `sample_latency(healthy_latency, degradation_factor)` — Simulates p95 request latency under load
- `should_pod_recover(restarts, backoff_seconds)` — Determines if a `CrashLoopBackOff` pod would naturally recover (it usually won't — that's the point)
- `generate_cluster_events(pod_list)` — Creates realistic k8s event messages like `"Back-off restarting failed container"` or `"OOMKilled: container exceeded memory limit"`

**`config.json` — Cluster defaults**

Single source of truth for all simulation parameters:

```json
{
  "cluster": {
    "num_nodes": 3,
    "cpu_per_node": 4,
    "mem_per_node_gb": 8
  },
  "tasks": {
    "pod_recovery": { "max_steps": 15, "success_threshold": 0.9 },
    "autoscaling":  { "max_steps": 20, "success_threshold": 0.85 },
    "incident":     { "max_steps": 30, "success_threshold": 0.80 }
  },
  "simulation": {
    "tick_interval_seconds": 30,
    "crash_backoff_max_seconds": 300,
    "hpa_cooldown_seconds": 180
  }
}
```

---

### Layer 3 — Action Space & Workers (Third Person)

This layer defines what the LLM is allowed to do, makes sure it's valid, and executes it against the simulator.

**`classes/actions/` — Typed action definitions**

Each action is a Pydantic model. The LLM must output one of these (Sandeep's inference.py prompts it to respond in JSON matching one of these schemas):

```python
class ScaleAction(BaseModel):
    action_type: Literal["scale"]
    deployment: str          # e.g. "frontend"
    replicas: int            # e.g. 3

class DeletePodAction(BaseModel):
    action_type: Literal["delete_pod"]
    pod_name: str            # e.g. "frontend-7d9f-xkp2"

class PatchAction(BaseModel):
    action_type: Literal["patch"]
    resource_type: str       # "deployment" | "configmap" | "service"
    name: str
    patch: Dict[str, Any]   # the fields to update

class RolloutRestartAction(BaseModel):
    action_type: Literal["rollout_restart"]
    deployment: str

class SetHPAAction(BaseModel):
    action_type: Literal["set_hpa"]
    deployment: str
    min_replicas: int
    max_replicas: int
    cpu_target_percent: int

class DrainNodeAction(BaseModel):
    action_type: Literal["drain_node"]
    node_name: str

class DescribeAction(BaseModel):
    action_type: Literal["describe"]
    resource_type: str
    name: str               # "investigation" action — no state change, returns detail
```

**`classes/validator.py` — Action validation**

Before any action touches the world state, the validator checks it:
- Does the target resource exist? (Can't delete a pod that doesn't exist)
- Is the scale value sane? (Can't scale to 0 or to 1000 replicas)
- Is the node already drained? (Can't drain twice)
- Is the deployment name a real deployment?

If validation fails, it returns an error string. This flows directly into the `[STEP] error=` field in stdout logs. The step still counts against the agent's limit — bad actions are penalised by wasting steps.

**`classes/executor.py` — Action execution bridge**

Maps each validated action type to the correct `world.py` method call:

```python
def execute(action: KubeAction, world: World) -> ExecutionResult:
    if action.action_type == "scale":
        world.scale(action.deployment, action.replicas)
    elif action.action_type == "delete_pod":
        world.delete_pod(action.pod_name)
    elif action.action_type == "rollout_restart":
        world.rollout_restart(action.deployment)
    ...
    world.tick()   # always advance time after an action
    return ExecutionResult(observation=world.get_observation(), ...)
```

**`classes/worker.py` — Agent episode loop**

Manages the full lifecycle of a single episode. Sandeep's `inference.py` calls this:

```python
class Worker:
    def run_episode(self, task_id, world, max_steps) -> EpisodeResult:
        obs = world.reset(task=task_id)
        rewards = []
        for step in range(1, max_steps + 1):
            action = self.get_action(obs)          # calls LLM
            result = executor.execute(action, world)
            rewards.append(result.reward)
            if result.done:
                break
        return EpisodeResult(rewards=rewards, steps=step, success=result.done)
```

---

## 5. Team Ownership

| Module | Owner | Why It's Their Responsibility |
|---|---|---|
| `main.py` | Sandeep | He owns the public API contract |
| `inference.py` | Sandeep | He owns the hackathon submission script |
| `openenv.yaml` | Sandeep | He owns spec compliance |
| `Dockerfile` | Sandeep | He owns deployment |
| `README.md` | Sandeep | He owns documentation |
| `classes/tasks/` | Sandeep | He defines what success looks like |
| `classes/graders/` | Sandeep | He owns the scoring logic |
| `classes/world.py` | You | You own the cluster simulator |
| `classes/models.py` | You | You own all typed data models |
| `classes/utils.py` | You | You own simulation helpers |
| `classes/conditions/` | You | You own failure injection |
| `config.json` | You | You own all parameters |
| `classes/worker.py` | Third person | They own the episode loop |
| `classes/actions/` | Third person | They own the action space |
| `classes/executor.py` | Third person | They own action execution |
| `classes/validator.py` | Third person | They own action validation |
| `tests/` | All three | Each writes tests for their own module |

---

## 6. Full Project Directory Structure

```text
COEnv/
├── .dockerignore                  # Docker build exclusions
├── __init__.py                    # Module exports
├── README.md                      # Project documentation
├── openenv.yaml                   # OpenEnv manifest
├── pyproject.toml                 # Project metadata and dependencies
├── uv.lock                        # Locked dependencies
├── client.py                      # CoenvEnv client / inference-side runner
├── models.py                      # Shared action and observation models
├── config.json                    # Cluster defaults and simulation params
├── mkdocs.yml                     # Docs site configuration
├── tests/                         # End-to-end and unit tests
│   ├── test_environment.py        # From test_world.py
│   ├── test_conditions.py         # From test_conditions.py
│   ├── test_models.py             # From test_models.py
│   ├── test_actions.py            # From test_actions.py
│   ├── test_executor.py           # From test_executor.py
│   ├── test_graders.py            # From test_graders.py
│   ├── test_tasks.py              # From test_tasks.py
│   └── test_integration.py        # End-to-end reset→step→state flow
└── server/
    ├── __init__.py                # Server module exports
    ├── COEnv_environment.py       # Core environment logic
    ├── app.py                     # FastAPI app exposing /reset /step /state
    ├── Dockerfile                 # Container image definition
    ├── utils.py                   # Simulation helpers
    ├── validator.py               # Action validation
    ├── executor.py                # Action execution bridge
    ├── worker.py                  # Episode loop manager
    ├── tasks/
    │   ├── __init__.py
    │   ├── task_pod_recovery.py
    │   ├── task_autoscaling.py
    │   └── task_incident.py
    ├── graders/
    │   ├── __init__.py
    │   ├── grader_pod_recovery.py
    │   ├── grader_autoscaling.py
    │   └── grader_incident.py
    ├── conditions/
    │   ├── __init__.py
    │   ├── crash_loop.py
    │   ├── oom_kill.py
    │   ├── node_failure.py
    │   └── cascade_failure.py
    └── actions/
        ├── __init__.py
        ├── scale_action.py
        ├── patch_action.py
        ├── delete_pod_action.py
        ├── rollout_action.py
        ├── hpa_action.py
        ├── drain_action.py
        └── describe_action.py
```

---

## 7. The Three Tasks (Easy → Medium → Hard)

### Task 1 — Pod Recovery (Easy)

**What's broken:** A frontend deployment has 3 pods stuck in `CrashLoopBackOff`. The restart count is climbing. The root cause is a wrong environment variable in the deployment spec pointing to a database host that doesn't exist.

**What the agent must do:**
1. Observe the broken pods and read the k8s events (which mention a connection refused error)
2. Identify the bad `DB_HOST` environment variable using a `describe` or `patch` inspect action
3. Patch the deployment with the correct `DB_HOST` value
4. Optionally delete the crash-looping pods to speed up recovery (they'll get recreated with the new config)
5. Verify all 3 pods reach `Running` state

**Objective string shown to agent:** *"The frontend deployment is crash-looping. Diagnose and fix the root cause so that all pods reach Running state."*

**Max steps:** 15  
**Success threshold:** All 3 pods in `Running` state (score ≥ 0.9)

**Partial rewards:**
- +0.1 for each pod that stops crash-looping
- +0.2 for correctly patching the environment variable
- +0.3 bonus for all pods Running within 10 steps

---

### Task 2 — HPA Autoscaling Under Traffic Spike (Medium)

**What's broken:** The cluster is healthy but receiving 10× normal traffic. The deployment has no HPA configured, is running on fixed 2 replicas, and is already at 95% CPU. Request latency is climbing past the SLO threshold.

**What the agent must do:**
1. Observe high CPU usage and rising latency in the observation
2. Immediately scale up the deployment to handle current load
3. Configure a HorizontalPodAutoscaler (HPA) with appropriate min/max replicas and CPU target
4. Set correct CPU resource requests/limits on the deployment so HPA has a baseline to work with
5. Verify that latency drops back below the SLO threshold

**Objective string shown to agent:** *"Traffic has spiked 10×. The api-server deployment is overloaded. Configure autoscaling and ensure p95 latency stays below 500ms."*

**Max steps:** 20  
**Success threshold:** p95 latency < 500ms, HPA configured, replicas ≥ 4 (score ≥ 0.85)

**Partial rewards:**
- +0.15 for scaling up replicas immediately (within 3 steps)
- +0.20 for configuring HPA correctly
- +0.25 for latency dropping below 1000ms
- +0.30 for latency dropping below 500ms (SLO met)
- -0.10 penalty for scaling beyond 12 replicas unnecessarily (resource waste)

---

### Task 3 — Multi-Service Cascading Incident (Hard)

**What's broken:** The `auth-service` deployment has pods getting OOMKilled because memory limits are set 4× too low relative to actual usage. This causes the `api-gateway` to fail authentication checks and return 503s. Downstream, the `data-processor` service is also throwing errors because it depends on the gateway. Three services are degraded simultaneously.

**What the agent must do:**
1. Identify the blast radius — which services are affected and why
2. Investigate `auth-service` to find the OOMKill root cause (memory limits too low)
3. Patch `auth-service` deployment with correct memory limits
4. Rollout restart `auth-service` so new pods come up with correct limits
5. Drain the partially-failed node where most OOMKilled pods were running, to force clean rescheduling
6. Verify `api-gateway` 503 errors stop (automatically once auth recovers)
7. Verify `data-processor` error rate drops (automatically once gateway recovers)
8. Confirm all three services are fully healthy

**Objective string shown to agent:** *"A cascading incident has degraded auth-service, api-gateway, and data-processor. Identify the root cause and restore all three services to healthy state without data loss."*

**Max steps:** 30  
**Success threshold:** All 3 services healthy, error rate < 0.1% (score ≥ 0.80)

**Partial rewards:**
- +0.10 for correctly identifying `auth-service` as the root cause (within 5 steps)
- +0.15 for patching memory limits correctly
- +0.15 for auth-service pods reaching Running
- +0.20 for api-gateway 503s stopping
- +0.20 for data-processor errors resolving
- +0.10 for draining the bad node cleanly
- -0.15 penalty for deleting services or breaking healthy components

---

## 8. Reward & Grading Design

The grading philosophy follows what the PS requires: reward signal over the **full trajectory**, not just at the end.

### Reward Principles

**Partial progress is always rewarded.** If the agent fixes 1 out of 3 broken pods, it gets 1/3 of the maximum reward for that milestone — not zero.

**Speed bonus.** Fixing the issue in fewer steps earns a small bonus. This incentivises efficient reasoning.

**Waste penalty.** Unnecessary destructive actions (scaling to 0, deleting healthy pods, draining a healthy node) subtract from the reward. This teaches the agent to be surgical.

**Idempotency.** Repeating the same correct action doesn't give extra reward but doesn't penalise either (except for wasted steps).

### Grader Implementation Pattern

Each grader implements:

```python
def grade(world_state: dict, step: int, max_steps: int) -> float:
    score = 0.0

    # Milestone 1: Partial progress
    running_pods = [p for p in world_state["pods"] if p["status"] == "Running"]
    score += (len(running_pods) / total_expected_pods) * 0.5

    # Milestone 2: Full success
    if all(p["status"] == "Running" for p in world_state["pods"]):
        score += 0.4

    # Speed bonus
    efficiency = 1.0 - (step / max_steps)
    score += efficiency * 0.1

    return min(score, 1.0)  # always clamp to [0, 1]
```

---

## 9. The Complete Episode Flow

Here is the full step-by-step flow of one complete episode, from start to finish:

```
1. JUDGE / VALIDATOR runs:
   python inference.py

2. inference.py reads env vars:
   API_BASE_URL, MODEL_NAME, HF_TOKEN

3. inference.py calls:
   POST /reset  { "task": "pod_recovery" }

4. main.py receives /reset:
   → Calls task_pod_recovery.get_condition()  →  crash_loop.inject(cluster_state)
   → world.reset(broken_state)
   → Returns ClusterObservation (3 CrashLoopBackOff pods, events, objective string)

5. stdout prints:
   [START] task=pod-recovery env=coenv model=Qwen3-30B

6. inference.py builds LLM prompt:
   "You are an SRE. Current cluster state: [observation JSON].
    Objective: Fix the frontend deployment crash loop.
    Respond with a JSON action from the available action types."

7. LLM responds:
   { "action_type": "describe", "resource_type": "deployment", "name": "frontend" }

8. inference.py calls:
   POST /step  { action }

9. main.py receives /step:
   → validator.validate(action, world)  →  OK
   → executor.execute(action, world)
   → world.tick()
   → grader.grade(world.state, step=1) → reward=0.00 (just investigating)
   → Returns observation, reward=0.00, done=false, info={...}

10. stdout prints:
    [STEP] step=1 action=describe('deployment','frontend') reward=0.00 done=false error=null

11. LLM sees deployment spec, notices DB_HOST=wrong-host.internal
    LLM responds: { "action_type": "patch", "resource_type": "deployment",
                    "name": "frontend",
                    "patch": {"env": [{"name": "DB_HOST", "value": "db.prod.internal"}]} }

12. POST /step  { patch action }
    → executor patches deployment in world state
    → world.tick() — pods begin restarting with new config
    → grader → reward=0.20 (correct patch applied)

13. [STEP] step=2 action=patch('frontend',{env...}) reward=0.20 done=false error=null

14. LLM responds: { "action_type": "delete_pod", "pod_name": "frontend-7d9f-xkp2" }
    → world deletes pod, recreates with correct env, status → Running
    → grader → reward=0.40

15. Repeat for remaining 2 pods...

16. All 3 pods Running. grader → reward=1.0, done=true

17. stdout prints:
    [END] success=true steps=8 rewards=0.00,0.20,0.40,0.55,0.70,0.85,0.95,1.00
```

---

## 10. OpenEnv Spec Compliance Checklist

| Requirement | File | Status |
|---|---|---|
| Typed Observation model | `classes/models.py` → `ClusterObservation` | Required |
| Typed Action model | `classes/models.py` → `KubeAction` | Required |
| Typed Reward model | `classes/models.py` → `RewardSignal` | Required |
| `step(action) → (obs, reward, done, info)` | `main.py` → `POST /step` | Required |
| `reset() → initial_observation` | `main.py` → `POST /reset` | Required |
| `state() → current_state` | `main.py` → `GET /state` | Required |
| `openenv.yaml` with metadata | `openenv.yaml` | Required |
| `openenv validate` passes | Tested via pre-validation script | Required |
| Min 3 tasks | `classes/tasks/` — 3 files | Required |
| Easy → medium → hard difficulty | task_pod_recovery / task_autoscaling / task_incident | Required |
| Graders return 0.0–1.0 | `classes/graders/` — 3 graders | Required |
| Graders are deterministic | Pure functions, no randomness | Required |
| Partial reward signals | All 3 graders implement milestone scoring | Required |
| Penalise bad actions | validator.py + grader penalty terms | Required |
| `inference.py` in root | `inference.py` | Required |
| `[START]` log line | `inference.py` → `log_start()` | Required |
| `[STEP]` log per step | `inference.py` → `log_step()` | Required |
| `[END]` log always emitted | `inference.py` → `finally: log_end()` | Required |
| Reads `API_BASE_URL` with default | `inference.py` | Required |
| Reads `MODEL_NAME` with default | `inference.py` | Required |
| Reads `HF_TOKEN` (no default) | `inference.py` | Required |
| Uses OpenAI client | `from openai import OpenAI` | Required |
| `Dockerfile` builds cleanly | `Dockerfile` | Required |
| HF Space deploys and responds | Deployed on Hugging Face | Required |
| Inference runs in < 20 min | Max 30 steps × ~20s/step = ~10 min | Required |
| Runs in 2 vCPU / 8 GB RAM | Pure Python in-memory sim, no real k8s | Required |
| README with all required sections | `README.md` | Required |

---

## 11. Submission Checklist

Before submitting, verify all of these:

- [ ] `inference.py` is in the **root directory** (not inside `classes/`)
- [ ] `inference.py` has default values for `API_BASE_URL` and `MODEL_NAME`
- [ ] `inference.py` raises `ValueError` if `HF_TOKEN` is missing
- [ ] `[START]`, `[STEP]`, `[END]` format matches the spec **exactly** (field names, order, lowercase booleans)
- [ ] `openenv validate` passes locally
- [ ] `docker build` completes without errors
- [ ] `docker run` starts the server and responds to `GET /state`
- [ ] HF Space is in **Running** state (not Building, not Stopped)
- [ ] All 3 tasks can be reset and stepped without crashing
- [ ] All 3 graders return a float between 0.0 and 1.0
- [ ] Running `inference.py` end-to-end completes in under 20 minutes
- [ ] `README.md` includes baseline scores table
- [ ] `tests/test_integration.py` passes cleanly

---

## 12. Key Technical Decisions

### Why a simulated cluster, not a real one?

Running `kind` or `minikube` inside a Hugging Face Space container with 2 vCPU / 8 GB RAM is not feasible. The Kubernetes control plane alone (etcd + apiserver + scheduler + controller-manager) consumes ~1.5–2 GB RAM before any workloads run. An in-memory Python simulator is the only viable approach within the hardware constraints. It is also faster (no scheduling latency), fully deterministic (same input = same output), and easier to test.

### Why a constrained action space?

Free-form kubectl text strings are nearly impossible to grade deterministically. By defining ~7 typed Pydantic action models, we make the action space clear to the LLM (easier to prompt), easy to validate (Pydantic does the type checking), and easy to grade (executor calls predictable world methods). This also keeps the action space small enough that the LLM can reason about it effectively without getting lost in kubectl's hundreds of sub-commands.

### Why FastAPI?

OpenEnv environments are expected to be HTTP servers. FastAPI gives automatic OpenAPI documentation (at `/docs`), Pydantic integration for request/response validation, async support for when we need it, and a clean decorator syntax that makes `main.py` easy to read. It is also trivial to run with `uvicorn` inside a Docker container.

### Why partial rewards matter for the hackathon

The PS explicitly states: *"The reward function must provide feedback throughout the task trajectory, not just at completion."* Binary rewards (0 until success, then 1) are explicitly penalised in the environment design score. Our graders implement milestone-based partial rewards, which also makes the environment more useful for actual RL training — sparse rewards make training slow and unstable.

---

*COEnv — Meta × Hugging Face OpenEnv RL Hackathon*  
*Team: Sandeep (RL environment) · You (Simulation) · Third Person (Actions & Workers)*
