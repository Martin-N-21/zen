from pathlib import Path

import pytest

from zen.playback import MpvBackend, PlaybackError, PlaybackState


def test_mpv_backend_reports_missing_executable(tmp_path: Path) -> None:
    audio_file = tmp_path / "track.mp3"
    audio_file.touch()
    backend = MpvBackend(executable="zen-mpv-that-does-not-exist")

    with pytest.raises(PlaybackError, match="mpv was not found"):
        backend.load(audio_file)


def test_mpv_backend_preserves_audio_output_errors_until_next_load() -> None:
    backend = MpvBackend()
    backend._state = PlaybackState(path=Path("track.mp3"), paused=False)

    backend._handle_message(
        {
            "event": "end-file",
            "reason": "error",
            "file_error": "audio output initialization failed",
        }
    )
    backend._handle_message(
        {"event": "property-change", "name": "idle-active", "data": True}
    )

    assert backend._state.path is None
    assert backend._state.error == "mpv playback error: audio output initialization failed"
