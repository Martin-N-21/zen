from pathlib import Path

import pytest

from zen.config import (
    ZenConfig,
    add_music_root,
    get_config_path,
    get_default_download_directory,
    load_config,
    remove_music_root,
    save_config,
    set_default_download_directory,
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


def test_default_download_directory_round_trip(tmp_path: Path) -> None:
    music_root = tmp_path / "music"
    downloads = music_root / "downloads"
    downloads.mkdir(parents=True)
    config = set_default_download_directory(ZenConfig((music_root,)), downloads)

    assert get_default_download_directory(config) == downloads
    assert load_config(save_config(config, tmp_path / "config.json")).default_download_directory == downloads


def test_default_config_path_uses_one_app_directory() -> None:
    config_path = get_config_path()

    assert config_path.name == "config.json"
    assert config_path.parent.name == "zen"
