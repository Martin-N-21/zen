from pathlib import Path

import pytest

from zen.library.scanner import scan_root


def test_scan_root_finds_supported_files_in_sorted_nested_order(tmp_path: Path) -> None:
    root = tmp_path / "music"
    (root / "b-folder").mkdir(parents=True)
    (root / "a-folder").mkdir()
    (root / "b-folder" / "second.FLAC").touch()
    (root / "a-folder" / "first.mp3").touch()
    (root / "ignored.txt").touch()

    tracks = list(scan_root(root))

    assert [track.relative_path.as_posix() for track in tracks] == [
        "a-folder/first.mp3",
        "b-folder/second.FLAC",
    ]
    assert tracks[0].title == "first"


def test_scan_root_requires_a_directory(tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        list(scan_root(tmp_path / "missing"))
