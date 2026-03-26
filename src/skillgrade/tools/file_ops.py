"""File operations tools."""

from __future__ import annotations

from pathlib import Path

from langchain_core.tools import tool
from pydantic import BaseModel, Field


class ReadFileInput(BaseModel):
    """Input schema for reading a file."""

    file_path: str = Field(description="Path to the file to read")


class WriteFileInput(BaseModel):
    """Input schema for writing a file."""

    file_path: str = Field(description="Path to the file to write")
    content: str = Field(description="Content to write to the file")


@tool(args_schema=ReadFileInput)
async def read_file(file_path: str) -> str:
    """Read the contents of a file.

    Use this to view existing files, check configurations, or read inputs.

    Args:
        file_path: Path to the file to read

    Returns:
        File contents as string, or error message if file not found
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return f"Error: File not found: {file_path}"

        return path.read_text()
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except Exception as e:
        return f"Error reading file: {str(e)}"


@tool(args_schema=WriteFileInput)
async def write_file(file_path: str, content: str) -> str:
    """Write content to a file.

    Use this to create or update files with new content.

    Args:
        file_path: Path to the file to write
        content: Content to write

    Returns:
        Success message or error
    """
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"Successfully wrote to {file_path}"
    except PermissionError:
        return f"Error: Permission denied: {file_path}"
    except Exception as e:
        return f"Error writing file: {str(e)}"


__all__ = ["read_file", "write_file"]
