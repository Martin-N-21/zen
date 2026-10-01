"""Widgets used by the playback panel."""

from __future__ import annotations

import math

from textual.widgets import Static

from ..playback.base import PlaybackState


class PlayerPanel(Static):
    """Display the current track and live playback information."""

    def update_state(self, state: PlaybackState) -> None:
        if state.path is None:
            self.update("No track selected\n\nSelect an audio file from the library.")
            return

        status = "Finished" if state.eof else "Paused" if state.paused else "Playing"
        duration = _format_time(state.duration)
        position = _format_time(state.position)
        progress = _progress_bar(state.position, state.duration)

        self.update(
            "\n".join(
                (
                    f"Status: {status}",
                    f"File: {state.path.name}",
                    f"Time: {position} / {duration}",
                    progress,
                    f"Volume: {state.volume:.0f}%",
                    "",
                    f"Location: {state.path.as_posix()}",
                )
            )
        )


def _format_time(value: float | None) -> str:
    if value is None or not math.isfinite(value) or value < 0:
        return "--:--"

    total_seconds = int(value)
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _progress_bar(position: float, duration: float | None, width: int = 30) -> str:
    if duration is None or duration <= 0:
        return "[" + "-" * width + "]"

    ratio = max(0.0, min(1.0, position / duration))
    filled = int(ratio * width)
    return "[" + "=" * filled + "-" * (width - filled) + "]"
