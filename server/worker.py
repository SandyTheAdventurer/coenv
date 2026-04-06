from dataclasses import dataclass, field
from typing import List, Callable, Any, Optional, Dict


@dataclass
class StepRecord:
    step: int
    action_applied: str
    reward: float
    done: bool
    error: Optional[str] = None


@dataclass
class EpisodeResult:
    task_id: str
    steps_taken: int
    rewards: List[float]
    success: bool
    history: List[StepRecord] = field(default_factory=list)

    @property
    def total_reward(self) -> float:
        return sum(self.rewards)


class Worker:
    def run_episode(
        self,
        task_id: str,
        world: Any,
        get_action: Callable[[Any], Any],
        max_steps: int,
        grader: Any
    ) -> EpisodeResult:
        obs = world.reset(task=task_id)
        history: List[StepRecord] = []
        rewards: List[float] = []
        done = False
        
        for step in range(1, max_steps + 1):
            action = get_action(obs)
            
            error = None
            from server.validator import validate
            validation_error = validate(action, world.get_raw_state())
            
            if validation_error:
                history.append(StepRecord(
                    step=step,
                    action_applied="invalid_action",
                    reward=0.0,
                    done=False,
                    error=validation_error
                ))
                rewards.append(0.0)
                continue
            
            from server.executor import execute
            result = execute(action, world)
            
            reward = grader.grade(world.get_raw_state(), step, max_steps)
            done = grader.is_done(world.get_raw_state())
            
            history.append(StepRecord(
                step=step,
                action_applied=result.action_applied,
                reward=reward,
                done=done,
                error=None
            ))
            rewards.append(reward)
            obs = result.observation
            
            if done:
                break
        
        return EpisodeResult(
            task_id=task_id,
            steps_taken=len(history),
            rewards=rewards,
            success=done,
            history=history
        )
