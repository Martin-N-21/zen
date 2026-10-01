"""Playback abstractions used by the terminal interface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class PlaybackState:
    """Snapshot of the current playback state."""

    path: Path | None = None
    duration: float | None = None
    position: float = 0.0
    paused: bool = True
    volume: float = 100.0
    eof: bool = False
    error: str | None = None

    @property
    def playing(self) -> bool:
        return self.path is not None and not self.paused and not self.eof


class PlaybackError(RuntimeError):
    """Raised when the playback backend cannot complete an operation."""


class PlaybackBackend(Protocol):
    """Interface implemented by audio playback engines."""

    def load(self, path: Path) -> None:
        """Load a local audio file."""
        ...

    def play(self) -> None:
        """Start or resume playback."""
        ...

    def pause(self) -> None:
        """Pause playback."""
        ...

    def stop(self) -> None:
        """Stop playback and return to idle state."""
        ...

    def toggle_pause(self) -> None:
        """Toggle between playing and paused states."""
        ...

    def seek(self, seconds: float) -> None:
        """Move relative to the current position."""
        ...

    def set_volume(self, volume: float) -> None:
        """Set volume from 0 to 100."""
        ...

    def poll(self) -> PlaybackState:
        """Return the latest state from the backend."""
        ...

    def close(self) -> None:
        """Release backend resources."""
        ...
