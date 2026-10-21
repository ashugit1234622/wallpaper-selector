"""Base autostart adapter interface."""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class BaseAutostartAdapter(ABC):
    """Abstract interface for managing per-user desktop login startup entries."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if login autostart is currently registered."""
        pass

    @abstractmethod
    def enable(self, command: str) -> bool:
        """Register the command to launch on user desktop login."""
        pass

    @abstractmethod
    def disable(self) -> bool:
        """Remove the login startup entry."""
        pass

    @abstractmethod
    def get_registered_command(self) -> Optional[str]:
        """Return the currently registered startup command, if any."""
        pass
