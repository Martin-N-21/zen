from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.events import Key
from textual.widgets import Footer, Header, Tree
from textual.widgets.tree import TreeNode

from ..config import ZenConfig, load_config
from ..library.scanner import SUPPORTED_EXTENSIONS
from ..playback import MpvBackend, PlaybackBackend, PlaybackError
from ..storage.database import LibraryDatabase
from .player import PlayerPanel


class LibraryTree(Tree):
    """Tree with predictable keyboard behavior for directories."""

    def on_key(self, event: Key) -> None:
        node = self.cursor_node
        path = node.data if node is not None else None

        app_actions = {
            "space": "action_toggle_pause",
            "s": "action_stop",
            "h": "action_seek_back",
            "l": "action_seek_forward",
            "-": "action_volume_down",
            "=": "action_volume_up",
        }
        action_name = app_actions.get(event.key)
        if action_name is not None:
            getattr(self.app, action_name)()
            event.stop()
            return

        if event.key == "q":
            self.app.exit()
            event.stop()
            return

        if event.key == "enter" and node is not None and isinstance(path, Path):
            if path.is_dir():
                if node.is_expanded:
                    node.collapse()
                else:
                    node.expand()
                event.stop()
                return

        if event.key == "left" and node is not None and node.is_expanded:
            node.collapse()
            event.stop()
            return

        if event.key == "right" and node is not None and isinstance(path, Path):
            if not node.is_expanded:
                node.expand()
            event.stop()
            return



class ZenApp(App[None]):
    """Keyboard-driven terminal interface for the zen music player."""

    TITLE = "zen"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("space", "toggle_pause", "Play/Pause"),
        ("s", "stop", "Stop"),
        ("h", "seek_back", "Back 5s"),
        ("l", "seek_forward", "Forward 5s"),
        ("-", "volume_down", "Volume -"),
        ("=", "volume_up", "Volume +"),
    ]

    CSS = """
    #main {
        height: 1fr;
    }

    #library-tree {
        width: 55%;
        border: round $accent;
    }

    #player-panel {
        width: 45%;
        padding: 1 2;
        border: round $secondary;
    }
    """

    def __init__(
        self,
        *,
        backend: PlaybackBackend | None = None,
        config: ZenConfig | None = None,
        database: LibraryDatabase | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.config = config or load_config()
        self.database = database or LibraryDatabase()
        self.backend = backend or MpvBackend()
        self._loaded_directories: set[Path] = set()
        self._last_error: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main"):
            yield LibraryTree("Music Library", id="library-tree")
            yield PlayerPanel(id="player-panel")
        yield Footer()

    def on_mount(self) -> None:
        tree = self.query_one("#library-tree", Tree)
        tree.root.expand()
        for root in self.config.music_roots:
            if root.is_dir():
                tree.root.add(str(root), data=root, allow_expand=True)
        if not self.config.music_roots:
            self.notify("No music roots configured. Use 'zen config add-root PATH'.")
        self._refresh_player()
        self.set_interval(0.25, self._refresh_player)

    def on_unmount(self) -> None:
        self.backend.close()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded) -> None:
        path = event.node.data
        if isinstance(path, Path):
            self._load_directory(event.node, path)

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        path = event.node.data
        if not isinstance(path, Path):
            return
        if path.is_dir():
            if event.node.is_expanded:
                event.node.collapse()
            else:
                event.node.expand()
        elif path.is_file():
            self._play(path)

    def action_toggle_pause(self) -> None:
        try:
            self.backend.toggle_pause()
        except PlaybackError as exc:
            self._show_error(exc)

    def action_stop(self) -> None:
        try:
            self.backend.stop()
        except PlaybackError as exc:
            self._show_error(exc)

    def action_seek_back(self) -> None:
        self._seek(-5.0)

    def action_seek_forward(self) -> None:
        self._seek(5.0)

    def action_volume_down(self) -> None:
        self._change_volume(-5.0)

    def action_volume_up(self) -> None:
        self._change_volume(5.0)

    def _load_directory(self, node: TreeNode, path: Path) -> None:
        if path in self._loaded_directories:
            return
        self._loaded_directories.add(path)

        try:
            entries = sorted(path.iterdir(), key=lambda entry: entry.name.casefold())
        except OSError as exc:
            self._show_error(exc)
            return

        directories = [
            entry for entry in entries if entry.is_dir() and not entry.is_symlink()
        ]
        files = [
            entry
            for entry in entries
            if entry.is_file() and entry.suffix.casefold() in SUPPORTED_EXTENSIONS
        ]

        for directory in directories:
            node.add(directory.name, data=directory, allow_expand=True)
        for file_path in files:
            node.add(file_path.name, data=file_path, allow_expand=False)

    def _play(self, path: Path) -> None:
        try:
            self.backend.load(path)
        except PlaybackError as exc:
            self._show_error(exc)

    def _seek(self, seconds: float) -> None:
        try:
            self.backend.seek(seconds)
        except PlaybackError as exc:
            self._show_error(exc)

    def _change_volume(self, delta: float) -> None:
        state = self.backend.poll()
        try:
            self.backend.set_volume(state.volume + delta)
        except PlaybackError as exc:
            self._show_error(exc)

    def _refresh_player(self) -> None:
        state = self.backend.poll()
        panel = self.query_one("#player-panel", PlayerPanel)
        panel.update_state(state)
        if state.error and state.error != self._last_error:
            self._show_error(state.error)
        self._last_error = state.error

    def _show_error(self, error: Exception | str) -> None:
        self.notify(str(error), severity="error")
