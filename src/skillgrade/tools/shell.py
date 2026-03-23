"""Shell execution tool."""

from __future__ import annotations

import asyncio
from typing import Annotated

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ShellInput(BaseModel):
    """Input schema for the shell tool."""

    command: str = Field(description="The bash command to execute")


@tool(args_schema=ShellInput)
async def shell(command: str) -> str:
    """Execute a bash command and return the output.

    This tool allows running shell commands in the current workspace.
    Use it to install packages, run scripts, check files, etc.

    Args:
        command: The bash command to execute

    Returns:
        Formatted output including stdout, stderr, and exit code
    """
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        result_parts = []
        if stdout:
            result_parts.append(f"stdout: {stdout.decode()}")
        if stderr:
            result_parts.append(f"stderr: {stderr.decode()}")
        result_parts.append(f"exit_code: {proc.returncode}")

        return "\n".join(result_parts)

    except asyncio.TimeoutError:
        return "Error: Command timed out"
    except Exception as e:
        return f"Error executing command: {str(e)}"


__all__ = ["shell"]
