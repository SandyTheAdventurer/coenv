from ..client import CoEnv
from ..models import CoenvAction
import pytest

@pytest.mark.asyncio
async def test_client_step_and_state():
    async with CoEnv(base_url="https://nightreigners-coenv.hf.space/") as client:
        # Test reset and initial state
        reset_result = await client.reset()
        assert hasattr(reset_result.observation, "step")
        assert hasattr(reset_result.observation, "done")
        assert reset_result.observation.step == 0
        assert reset_result.done is False

        # Test step with a sample action
        action = CoenvAction(action_type="describe", resource_type="pod", name="test-pod")
        step_result = await client.step(action)
        assert hasattr(step_result.observation, "step")
        assert step_result.observation.step == 1

        # Test state retrieval
        
        step_result = await client.step(action)

        state_attr = getattr(client, "state")
        state = await state_attr() if callable(state_attr) else state_attr
        if isinstance(state, dict):
            step_count = state.get("step_count", state.get("step", -1))
        else:
            step_count = getattr(state, "step_count", getattr(state, "step", -1))
        assert step_count == 2