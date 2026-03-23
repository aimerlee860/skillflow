"""Tests for workspace module."""

import pytest
from pathlib import Path
from skillgrade.core.workspace import (
    create_temp_workspace,
    cleanup_workspace,
    read_env_file,
)
from skillgrade.types import WorkspaceFile


@pytest.mark.asyncio
async def test_create_temp_workspace(tmp_path):
    """Test workspace creation."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("hello")

    workspace = create_temp_workspace([WorkspaceFile(src=str(test_file), dest="output.txt")])

    assert workspace.exists()
    assert (workspace / "output.txt").read_text() == "hello"

    cleanup_workspace(workspace)


@pytest.mark.asyncio
async def test_read_env_file(tmp_path):
    """Test reading .env file."""
    env_file = tmp_path / ".env"
    env_file.write_text("KEY1=value1\nKEY2=value2\n# comment\n\nKEY3=value3")

    env_vars = read_env_file(env_file)
    assert env_vars["KEY1"] == "value1"
    assert env_vars["KEY2"] == "value2"
    assert env_vars["KEY3"] == "value3"
