from pathlib import Path

import pytest

from zen.config import (
    ZenConfig,
    add_music_root,
    get_config_path,
    load_config,
    remove_music_root,
    save_config,
)


def test_config_round_trip(tmp_path: Path) -> None:
    music_root = tmp_path / "music"
    music_root.mkdir()
    config_path = tmp_path / "config.json"
    config = ZenConfig((music_root,))

    save_config(config, config_path)

    assert load_config(config_path) == config


def test_add_music_root_rejects_non_directory(tmp_path: Path) -> None:
    config = ZenConfig()

    with pytest.raises(ValueError, match="not a directory"):
        add_music_root(config, tmp_path / "missing")


def test_remove_music_root_requires_configured_root(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="not configured"):
        remove_music_root(ZenConfig(), tmp_path)


def test_default_config_path_uses_one_app_directory() -> None:
    config_path = get_config_path()

    assert config_path.name == "config.json"
    assert config_path.parent.name == "zen"
