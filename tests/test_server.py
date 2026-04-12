from ..client import CoEnv
from ..models import CoenvAction
import pytest


@pytest.mark.asyncio
async def test_client_step_and_state():
    async with CoEnv(base_url="https://nightreigners-coenv.hf.space") as client:
        async def _get_step_count() -> int:
            state_attr = getattr(client, "state")
            state = await state_attr() if callable(state_attr) else state_attr
            if isinstance(state, dict):
                return state.get("step_count", state.get("step", -1))
            return getattr(state, "step_count", getattr(state, "step", -1))

        # Test reset and initial state
        reset_result = await client.reset()
        assert hasattr(reset_result.observation, "step")
        assert hasattr(reset_result.observation, "done")
        assert reset_result.observation.step == 0
        assert reset_result.done is False

        deployment_name = (
            reset_result.observation.deployments[0].name
            if reset_result.observation.deployments
            else "frontend"
        )

        # Test step with a sample action
        action = CoenvAction(
            action_type="describe", resource_type="deployment", name=deployment_name
        )
        step_result = await client.step(action)
        assert hasattr(step_result.observation, "step")
        assert isinstance(step_result.observation.step, int)
        assert step_result.observation.step >= 0
        assert await _get_step_count() == 1

        # Test state retrieval
        await client.step(action)
        assert await _get_step_count() == 2
