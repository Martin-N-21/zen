"""Recursive audio-file scanning and metadata extraction."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from os import walk
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen import MutagenError

from .models import Track

SUPPORTED_EXTENSIONS = frozenset({".flac", ".mp3", ".ogg", ".wav"})


def scan_root(root: Path) -> Iterator[Track]:
    """Yield supported audio files below one directory in deterministic order."""

    normalized_root = root.expanduser().resolve(strict=False)
    if not normalized_root.is_dir():
        raise NotADirectoryError(normalized_root)

    for directory, directories, filenames in walk(
        normalized_root,
        topdown=True,
        followlinks=False,
    ):
        directories.sort(key=str.casefold)
        for filename in sorted(filenames, key=str.casefold):
            path = Path(directory) / filename
            if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
                continue
            yield _track_from_file(path, normalized_root)


def scan_roots(roots: tuple[Path, ...]) -> Iterator[Track]:
    """Yield tracks from each configured root in configuration order."""

    for root in roots:
        yield from scan_root(root)


def _track_from_file(path: Path, root: Path) -> Track:
    title, artist, album, genre, duration = _read_metadata(path)
    return Track(
        path=path,
        root=root,
        title=title or path.stem,
        artist=artist,
        album=album,
        genre=genre,
        duration=duration,
    )


def _read_metadata(
    path: Path,
) -> tuple[str | None, str | None, str | None, str | None, float | None]:
    try:
        audio = MutagenFile(path, easy=True)
    except (MutagenError, OSError, ValueError):
        return None, None, None, None, None

    if audio is None:
        return None, None, None, None, None

    tags = audio.tags
    duration = getattr(audio.info, "length", None)
    if not isinstance(duration, (int, float)) or duration < 0:
        duration = None

    return (
        _tag_text(tags, "title"),
        _tag_text(tags, "artist"),
        _tag_text(tags, "album"),
        _tag_text(tags, "genre"),
        float(duration) if duration is not None else None,
    )


def _tag_text(tags: Mapping[str, Any] | None, key: str) -> str | None:
    if not tags:
        return None
    return _first_text(tags.get(key))


def _first_text(value: Any) -> str | None:
    if isinstance(value, (list, tuple)):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None
