"""I/O utilities with formatting and progress indicators."""

from __future__ import annotations

import sys
from typing import Generator


class Spinner:
    """Simple terminal spinner for progress indication.

    Usage:
        with Spinner("Loading"):
            # do work
    """

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, label: str = "", total: int = 100):
        """Initialize spinner.

        Args:
            label: Label to display
            total: Total steps for progress
        """
        self.label = label
        self.total = total
        self.current = 0
        self._enabled = sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False

    def update(self, n: int = 1) -> None:
        """Update spinner progress.

        Args:
            n: New progress value
        """
        self.current = min(n, self.total)
        if not self._enabled:
            return

        percent = self.current / self.total * 100
        frame = self.FRAMES[self.current % len(self.FRAMES)]
        sys.stdout.write(f"\r{frame} {self.label}: {self.current}/{self.total} ({percent:.0f}%)   ")
        sys.stdout.flush()

    def __enter__(self) -> "Spinner":
        """Enter context manager."""
        if self._enabled:
            sys.stdout.write(f"\r  {self.label}: 0/{self.total} (0%)")
            sys.stdout.flush()
        return self

    def __exit__(self, *args: object) -> None:
        """Exit context manager."""
        if self._enabled:
            sys.stdout.write(f"\r✓ {self.label}: Done ({self.total}/{self.total})   \n")
            sys.stdout.flush()


def fmt_score(score: float) -> str:
    """Format a score for terminal display with color.

    Args:
        score: Score between 0 and 1

    Returns:
        Formatted string with ANSI color codes
    """
    if score >= 0.8:
        return f"\033[92m{score:.2f}\033[0m"
    elif score >= 0.5:
        return f"\033[93m{score:.2f}\033[0m"
    else:
        return f"\033[91m{score:.2f}\033[0m"


def fmt_percent(value: float) -> str:
    """Format a value as a percentage.

    Args:
        value: Value between 0 and 1

    Returns:
        Formatted percentage string
    """
    return f"{value * 100:.1f}%"


def print_header(title: str, width: int = 60) -> None:
    """Print a section header.

    Args:
        title: Header title
        width: Line width
    """
    print()
    print("=" * width)
    print(title)
    print("=" * width)


def print_key_value(key: str, value: str, indent: int = 0) -> None:
    """Print a key-value pair.

    Args:
        key: Key name
        value: Value
        indent: Indentation spaces
    """
    prefix = " " * indent
    print(f"{prefix}{key}: {value}")


def print_success(message: str) -> None:
    """Print a success message.

    Args:
        message: Message to print
    """
    print(f"\033[92m✓ {message}\033[0m")


def print_error(message: str) -> None:
    """Print an error message.

    Args:
        message: Message to print
    """
    print(f"\033[91m✗ {message}\033[0m")


def print_warning(message: str) -> None:
    """Print a warning message.

    Args:
        message: Message to print
    """
    print(f"\033[93m⚠ {message}\033[0m")


def print_info(message: str) -> None:
    """Print an info message.

    Args:
        message: Message to print
    """
    print(f"\033[94mℹ {message}\033[0m")
