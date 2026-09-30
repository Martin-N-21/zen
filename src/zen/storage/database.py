"""SQLite persistence for the local music library."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from platformdirs import user_data_dir
from sqlalchemy import URL, Float, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from ..library.models import Track


class Base(DeclarativeBase):
    """Base class for zen's SQLite tables."""


class MusicRootRow(Base):
    __tablename__ = "music_roots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(4096), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class TrackRow(Base):
    __tablename__ = "tracks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    path: Mapped[str] = mapped_column(String(4096), unique=True, index=True)
    root_path: Mapped[str] = mapped_column(String(4096), index=True)
    relative_path: Mapped[str] = mapped_column(String(4096))
    title: Mapped[str] = mapped_column(String(1024))
    artist: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    album: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    genre: Mapped[str | None] = mapped_column(String(512), nullable=True)
    duration: Mapped[float | None] = mapped_column(Float, nullable=True)
    modified_ns: Mapped[int] = mapped_column(Integer)
    indexed_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))

    @classmethod
    def from_track(cls, track: Track, modified_ns: int) -> TrackRow:
        return cls(
            path=str(track.path),
            root_path=str(track.root),
            relative_path=track.relative_path.as_posix(),
            title=track.title,
            artist=track.artist,
            album=track.album,
            genre=track.genre,
            duration=track.duration,
            modified_ns=modified_ns,
        )

    def update_from_track(self, track: Track, modified_ns: int) -> None:
        self.root_path = str(track.root)
        self.relative_path = track.relative_path.as_posix()
        self.title = track.title
        self.artist = track.artist
        self.album = track.album
        self.genre = track.genre
        self.duration = track.duration
        self.modified_ns = modified_ns
        self.indexed_at = datetime.now(timezone.utc)

    def to_track(self) -> Track:
        return Track(
            path=Path(self.path),
            root=Path(self.root_path),
            title=self.title,
            artist=self.artist,
            album=self.album,
            genre=self.genre,
            duration=self.duration,
        )


@dataclass(frozen=True, slots=True)
class SyncSummary:
    """Changes made by one complete library synchronization."""

    scanned: int
    added: int
    updated: int
    removed: int


class LibraryDatabase:
    """Small synchronous repository around the local SQLite database."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = get_database_path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        database_url = URL.create("sqlite", database=str(self.path))
        self.engine = create_engine(database_url)
        Base.metadata.create_all(self.engine)

    def sync_tracks(self, roots: Iterable[Path], tracks: Iterable[Track]) -> SyncSummary:
        """Synchronize the database with a complete scan result."""

        configured_roots = tuple(_normalize_path(root) for root in roots)
        scanned_tracks = tuple(tracks)
        current_paths: set[str] = set()
        added = 0
        updated = 0
        removed = 0
        configured_root_strings = {str(root) for root in configured_roots}

        with Session(self.engine) as session, session.begin():
            existing_roots = session.scalars(select(MusicRootRow)).all()
            for root_row in existing_roots:
                if root_row.path not in configured_root_strings:
                    session.delete(root_row)

            existing_root_paths = {root.path for root in existing_roots}
            for root in configured_roots:
                if str(root) not in existing_root_paths:
                    session.add(MusicRootRow(path=str(root)))

            existing_tracks = session.scalars(select(TrackRow)).all()
            tracks_by_path = {track.path: track for track in existing_tracks}

            for track in scanned_tracks:
                try:
                    modified_ns = track.path.stat().st_mtime_ns
                except OSError:
                    continue

                path = str(track.path)
                current_paths.add(path)
                existing = tracks_by_path.get(path)
                if existing is None:
                    session.add(TrackRow.from_track(track, modified_ns))
                    added += 1
                    continue

                if _needs_update(existing, track, modified_ns):
                    existing.update_from_track(track, modified_ns)
                    updated += 1

            for track_row in existing_tracks:
                is_stale = track_row.root_path not in configured_root_strings
                is_missing = track_row.path not in current_paths
                if is_stale or is_missing:
                    session.delete(track_row)
                    removed += 1

        return SyncSummary(
            scanned=len(scanned_tracks),
            added=added,
            updated=updated,
            removed=removed,
        )

    def list_tracks(self) -> list[Track]:
        """Return indexed tracks sorted by their absolute path."""

        with Session(self.engine) as session:
            rows = session.scalars(select(TrackRow).order_by(TrackRow.path)).all()
            return [row.to_track() for row in rows]


def get_database_path(path: Path | None = None) -> Path:
    """Return the explicit or platform-specific database path."""

    if path is not None:
        return path.expanduser()
    return Path(user_data_dir("zen", appauthor=False)) / "library.db"


def _normalize_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _needs_update(row: TrackRow, track: Track, modified_ns: int) -> bool:
    return any(
        (
            row.modified_ns != modified_ns,
            row.root_path != str(track.root),
            row.relative_path != track.relative_path.as_posix(),
            row.title != track.title,
            row.artist != track.artist,
            row.album != track.album,
            row.genre != track.genre,
            row.duration != track.duration,
        )
    )
