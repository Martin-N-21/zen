import asyncio
from pathlib import Path

from textual.widgets import Tree

from zen.config import ZenConfig
from zen.playback.base import PlaybackState
from zen.storage.database import LibraryDatabase
from zen.tui.app import ZenApp
from zen.tui.download import DownloadScreen


def test_app_title() -> None:
    assert ZenApp.TITLE == "zen"


def test_download_screen_opens_from_keyboard(tmp_path: Path) -> None:
    music_root = tmp_path / "music"
    music_root.mkdir()
    app = ZenApp(
        backend=FakeBackend(),
        config=ZenConfig((music_root,)),
        database=LibraryDatabase(tmp_path / "library.db"),
    )

    async def check_app() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()
            assert isinstance(app.screen, DownloadScreen)

    asyncio.run(check_app())


def test_app_mounts_configured_music_root(tmp_path: Path) -> None:
    music_root = tmp_path / "music"
    music_root.mkdir()
    song = music_root / "song.mp3"
    song.touch()
    backend = FakeBackend()
    app = ZenApp(
        backend=backend,
        config=ZenConfig((music_root,)),
        database=LibraryDatabase(tmp_path / "library.db"),
    )

    async def check_app() -> None:
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one("#library-tree", Tree)
            assert len(tree.root.children) == 1
            tree.focus()
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            root_node = tree.root.children[0]
            assert len(root_node.children) == 1
            await pilot.press("left")
            await pilot.pause()
            assert not root_node.is_expanded
            await pilot.press("right")
            await pilot.pause()
            assert root_node.is_expanded
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.pause()
            assert backend.state.path == song
            await pilot.press("space")
            await pilot.pause()
            assert backend.state.paused
            await pilot.press("space")
            await pilot.pause()
            assert not backend.state.paused
            await pilot.press("-")
            assert backend.state.volume == 95.0

    asyncio.run(check_app())


class FakeBackend:
    def __init__(self) -> None:
        self.state = PlaybackState()

    def load(self, path: Path) -> None:
        self.state = PlaybackState(path=path, paused=False)

    def play(self) -> None:
        self.state = PlaybackState(path=self.state.path, paused=False)

    def pause(self) -> None:
        self.state = PlaybackState(path=self.state.path, paused=True)

    def stop(self) -> None:
        self.state = PlaybackState()

    def toggle_pause(self) -> None:
        self.state = PlaybackState(path=self.state.path, paused=not self.state.paused)

    def seek(self, seconds: float) -> None:
        del seconds

    def set_volume(self, volume: float) -> None:
        self.state = PlaybackState(path=self.state.path, volume=volume)

    def poll(self) -> PlaybackState:
        return self.state

    def close(self) -> None:
        pass
