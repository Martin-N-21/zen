"""Persistent user configuration for zen."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from platformdirs import user_config_dir


@dataclass(frozen=True, slots=True)
class ZenConfig:
    """Configuration values that are independent from the project directory."""

    music_roots: tuple[Path, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"version": 1, "music_roots": [str(root) for root in self.music_roots]}


def get_config_path(path: Path | None = None) -> Path:
    """Return the configured path or the platform-specific default path."""

    if path is not None:
        return path.expanduser()
    return Path(user_config_dir("zen", appauthor=False)) / "config.json"


def load_config(path: Path | None = None) -> ZenConfig:
    """Load configuration from disk, returning empty defaults when it is absent."""

    config_path = get_config_path(path)
    if not config_path.exists():
        return ZenConfig()

    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid configuration file: {config_path}") from exc

    if not isinstance(raw, dict):
        raise ValueError("Configuration must contain a JSON object")

    raw_roots = raw.get("music_roots", [])
    if not isinstance(raw_roots, list) or not all(isinstance(root, str) for root in raw_roots):
        raise ValueError("Configuration field 'music_roots' must be a list of paths")

    roots = tuple(_normalize_path(Path(root)) for root in raw_roots)
    return ZenConfig(music_roots=roots)


def save_config(config: ZenConfig, path: Path | None = None) -> Path:
    """Save configuration and return the path that was written."""

    config_path = get_config_path(path)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    return config_path


def add_music_root(config: ZenConfig, root: Path) -> ZenConfig:
    """Return a config with an existing directory added once."""

    normalized_root = _normalize_path(root)
    if not normalized_root.is_dir():
        raise ValueError(f"Music root is not a directory: {normalized_root}")
    if normalized_root in config.music_roots:
        return config
    return ZenConfig(config.music_roots + (normalized_root,))


def remove_music_root(config: ZenConfig, root: Path) -> ZenConfig:
    """Return a config with a configured directory removed."""

    normalized_root = _normalize_path(root)
    if normalized_root not in config.music_roots:
        raise ValueError(f"Music root is not configured: {normalized_root}")
    return ZenConfig(tuple(item for item in config.music_roots if item != normalized_root))


def _normalize_path(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)
