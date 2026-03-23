"""Glob pattern matching tool."""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class GlobInput(BaseModel):
    """Input schema for the glob tool."""

    pattern: str = Field(description="Glob pattern (e.g., '*.py', '**/*.ts')")
    base_dir: str = Field(default=".", description="Base directory to search from")


@tool(args_schema=GlobInput)
async def glob_files(pattern: str, base_dir: str = ".") -> str:
    """Find files matching a glob pattern.

    Supports standard glob patterns:
    - *.py - matches all .py files in current directory
    - **/*.js - matches all .js files recursively
    - src/* - matches all files in src directory
    - **/test_*.py - matches test files recursively

    Args:
        pattern: Glob pattern to match
        base_dir: Base directory to search from (default: current directory)

    Returns:
        List of matching file paths, one per line, or message if no matches
    """
    try:
        base = Path(base_dir).resolve()
        if not base.exists():
            return f"Error: Base directory not found: {base_dir}"

        matches = sorted([str(p.relative_to(base)) for p in base.rglob(pattern)])

        if not matches:
            return f"No files found matching pattern: {pattern}"

        return "\n".join(matches)

    except Exception as e:
        return f"Error searching for pattern: {str(e)}"


__all__ = ["glob_files"]
