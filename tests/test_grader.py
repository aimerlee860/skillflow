"""Tests for grader modules."""

import pytest
import json
from pathlib import Path
from skillgrade.graders import DeterministicGrader
from skillgrade.types import GraderConfig, GraderType


@pytest.mark.asyncio
async def test_deterministic_grader_success(tmp_path):
    """Test deterministic grader with passing script."""
    grader = DeterministicGrader()

    script = 'import json; print(json.dumps({"score": 1.0, "details": "All passed"}))'

    config = GraderConfig(type=GraderType.DETERMINISTIC, run=script, weight=1.0)
    result = await grader.grade(tmp_path, config, [])

    assert result.score == 1.0
    assert result.grader_type == "deterministic"


@pytest.mark.asyncio
async def test_deterministic_grader_failure(tmp_path):
    """Test deterministic grader with failing script."""
    grader = DeterministicGrader()

    script = 'import json; print(json.dumps({"score": 0.0, "details": "Failed"}))'

    config = GraderConfig(type=GraderType.DETERMINISTIC, run=script, weight=1.0)
    result = await grader.grade(tmp_path, config, [])

    assert result.score == 0.0


@pytest.mark.asyncio
async def test_deterministic_grader_with_checks(tmp_path):
    """Test deterministic grader with checks."""
    grader = DeterministicGrader()

    script = """
import json
print(json.dumps({
    "score": 0.5,
    "details": "1/2 checks passed",
    "checks": [
        {"name": "check1", "passed": True, "message": "OK"},
        {"name": "check2", "passed": False, "message": "Failed"}
    ]
}))
"""

    config = GraderConfig(type=GraderType.DETERMINISTIC, run=script, weight=1.0)
    result = await grader.grade(tmp_path, config, [])

    assert result.score == 0.5
    assert result.checks is not None
    assert len(result.checks) == 2
