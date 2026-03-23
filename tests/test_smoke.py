"""Tests for smoke evaluation."""

import pytest
from skillgrade.graph import run_quick_eval


@pytest.mark.asyncio
@pytest.mark.skip(reason="Requires LLM API")
async def test_run_quick_eval():
    """Test quick evaluation without full smoke."""
    graders = [
        {
            "type": "deterministic",
            "run": 'import json; print(json.dumps({"score": 1.0, "details": "OK"}))',
            "weight": 1.0,
        }
    ]

    result = await run_quick_eval(
        instruction="Create a file called hello.txt with 'world'",
        graders=graders,
    )

    assert "output" in result
    assert "reward" in result
