"""Data models for the local music library."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Track:
    """A local audio file and the metadata available for it."""

    path: Path
    root: Path
    title: str
    artist: str | None = None
    album: str | None = None
    genre: str | None = None
    duration: float | None = None

    @property
    def relative_path(self) -> Path:
        return self.path.relative_to(self.root)
