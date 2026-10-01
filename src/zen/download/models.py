"""Models shared by download providers and the download UI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable


class DownloadError(RuntimeError):
    """Raised when a provider cannot search, inspect, or download media."""


@dataclass(frozen=True, slots=True)
class SearchResult:
    """A media item returned by a platform search."""

    item_id: str
    title: str
    url: str
    platform: str
    uploader: str | None = None
    duration: float | None = None

    @property
    def label(self) -> str:
        duration = _format_duration(self.duration)
        uploader = f" - {self.uploader}" if self.uploader else ""
        return f"{self.title}{uploader} [{duration}]"


@dataclass(frozen=True, slots=True)
class FormatOption:
    """An audio source format reported by a provider."""

    format_id: str
    extension: str
    codec: str | None
    bitrate: float | None
    label: str


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    """Progress update emitted while downloading a media item."""

    percent: float | None
    message: str


ProgressCallback = Callable[[DownloadProgress], None]


def _format_duration(value: float | None) -> str:
    if value is None or value < 0:
        return "unknown duration"
    total_seconds = int(value)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_download_path(path: Path) -> str:
    """Return a normalized path for user-facing messages."""

    return path.as_posix()
