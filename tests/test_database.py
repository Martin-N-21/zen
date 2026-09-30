from pathlib import Path

from zen.library.scanner import scan_root
from zen.storage.database import LibraryDatabase


def test_sync_is_idempotent_and_removes_missing_tracks(tmp_path: Path) -> None:
    root = tmp_path / "music"
    root.mkdir()
    first = root / "first.mp3"
    second = root / "second.flac"
    first.touch()
    second.touch()
    database = LibraryDatabase(tmp_path / "library.db")

    tracks = list(scan_root(root))
    first_sync = database.sync_tracks((root,), tracks)
    second_sync = database.sync_tracks((root,), list(scan_root(root)))

    second.unlink()
    removal_sync = database.sync_tracks((root,), list(scan_root(root)))

    assert first_sync.scanned == 2
    assert first_sync.added == 2
    assert first_sync.updated == 0
    assert first_sync.removed == 0
    assert second_sync.added == 0
    assert second_sync.updated == 0
    assert second_sync.removed == 0
    assert removal_sync.removed == 1
    assert [track.path for track in database.list_tracks()] == [first]
