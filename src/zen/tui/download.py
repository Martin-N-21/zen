"""Download modal and destination picker."""

from __future__ import annotations

from pathlib import Path

from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, DirectoryTree, Input, Label, Select, Static

from ..config import ZenConfig, get_default_download_directory
from ..download import (
    DownloadError,
    DownloadProgress,
    FormatOption,
    SearchResult,
    YtDlpProvider,
)


class DestinationPicker(ModalScreen[Path | None]):
    """Choose a directory using Textual's lazy directory tree."""

    CSS = """
    DestinationPicker {
        align: center middle;
    }

    #destination-dialog {
        width: 80%;
        height: 80%;
        border: round $accent;
        padding: 1 2;
    }

    #destination-tree {
        height: 1fr;
        border: round $secondary;
    }

    #destination-actions {
        height: 3;
        align: right middle;
    }
    """

    def __init__(self, start_path: Path) -> None:
        super().__init__()
        self.start_path = start_path
        self.selected_path = start_path

    def compose(self) -> ComposeResult:
        with Vertical(id="destination-dialog"):
            yield Label("Choose download folder")
            yield DirectoryTree(self.start_path, id="destination-tree")
            yield Label(str(self.selected_path), id="destination-selected")
            with Horizontal(id="destination-actions"):
                yield Button("Select", variant="primary", id="select-destination")
                yield Button("Cancel", id="cancel-destination")

    def on_directory_tree_directory_selected(
        self,
        event: DirectoryTree.DirectorySelected,
    ) -> None:
        self.selected_path = event.path
        self.query_one("#destination-selected", Label).update(str(event.path))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "select-destination":
            self.dismiss(self.selected_path)
        elif event.button.id == "cancel-destination":
            self.dismiss(None)


class DownloadScreen(ModalScreen[None]):
    """Search and download audio without blocking the player UI."""

    CSS = """
    DownloadScreen {
        align: center middle;
    }

    #download-dialog {
        width: 92%;
        height: 92%;
        border: round $accent;
        padding: 1 2;
    }

    #query-row, #destination-row, #download-actions {
        height: 3;
        align: left middle;
    }

    #query, #destination {
        width: 1fr;
    }

    #results, #formats {
        height: 8;
        margin: 1 0;
    }

    #download-status {
        height: 4;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        config: ZenConfig,
        provider: YtDlpProvider | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.provider = provider or YtDlpProvider()
        self._results: list[SearchResult] = []
        self._formats: list[FormatOption] = []
        self._selected_result: SearchResult | None = None
        self._query = ""
        self._platform = "youtube"
        self._seen_ids: set[str] = set()
        self._quality_confirmation_required = False

    def compose(self) -> ComposeResult:
        default_directory = get_default_download_directory(self.config)
        with Vertical(id="download-dialog"):
            yield Label("Download audio")
            yield Select(
                [("YouTube", "youtube"), ("SoundCloud", "soundcloud")],
                value="youtube",
                id="platform",
            )
            yield Select(
                [("Search by name", "search"), ("Download from URL", "url")],
                value="search",
                id="source-mode",
            )
            with Horizontal(id="query-row"):
                yield Input(placeholder="Search or paste a URL", id="query")
                yield Button("Search", variant="primary", id="submit-query")
            yield Select([], prompt="Search results", id="results")
            yield Select([], prompt="Audio quality", id="formats")
            with Horizontal(id="destination-row"):
                yield Input(
                    value=str(default_directory) if default_directory else "",
                    placeholder="Download folder",
                    id="destination",
                )
                yield Button("Browse", id="browse-destination")
                yield Button("Default", id="default-destination")
            yield Static("", id="download-status")
            with Horizontal(id="download-actions"):
                yield Button("More results", id="more-results", disabled=True)
                yield Button("Download", variant="success", id="download")
                yield Button("Close", id="close")

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id == "platform":
            self._platform = str(event.value)
            self._clear_results()
        elif event.select.id == "source-mode":
            mode = str(event.value)
            button = self.query_one("#submit-query", Button)
            button.label = "Inspect URL" if mode == "url" else "Search"
            self._clear_results()
        elif event.select.id == "results" and isinstance(event.value, str):
            try:
                self._selected_result = self._results[int(event.value)]
            except (IndexError, ValueError):
                self._selected_result = None
            if self._selected_result is not None:
                self._load_formats(self._selected_result)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "submit-query":
            self._submit_query()
        elif button_id == "more-results":
            self._search_more()
        elif button_id == "browse-destination":
            self._browse_destination()
        elif button_id == "default-destination":
            self._use_default_destination()
        elif button_id == "download":
            self._start_download()
        elif button_id == "close":
            self.dismiss(None)

    def _submit_query(self) -> None:
        query = self.query_one("#query", Input).value.strip()
        if not query:
            self._set_status("Enter a search query or URL first.")
            return
        self._query = query
        mode = str(self.query_one("#source-mode", Select).value)
        if mode == "url":
            self._inspect_url(query)
        else:
            self._seen_ids.clear()
            self._search(query, ())

    def _search_more(self) -> None:
        if self._query:
            self._search(self._query, tuple(self._seen_ids))

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _search(self, query: str, exclude_ids: tuple[str, ...]) -> None:
        try:
            results = self.provider.search(
                self._platform,
                query,
                limit=10,
                exclude_ids=exclude_ids,
            )
        except DownloadError as exc:
            self.app.call_from_thread(self._show_error, str(exc))
            return
        self.app.call_from_thread(self._append_results, results)

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _inspect_url(self, url: str) -> None:
        try:
            result = self.provider.inspect_url(self._platform, url)
        except DownloadError as exc:
            self.app.call_from_thread(self._show_error, str(exc))
            return
        self.app.call_from_thread(self._append_results, [result])

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _load_formats(self, result: SearchResult) -> None:
        try:
            formats = self.provider.formats(result)
        except DownloadError as exc:
            self.app.call_from_thread(self._show_error, str(exc))
            return
        self.app.call_from_thread(self._set_formats, formats)

    @work(thread=True, exclusive=True, exit_on_error=False)
    def _download_worker(
        self,
        result: SearchResult,
        destination: Path,
        format_id: str,
    ) -> None:
        try:
            path = self.provider.download(
                result,
                destination,
                format_id=format_id,
                progress_callback=lambda progress: self.app.call_from_thread(
                    self._update_progress,
                    progress,
                ),
            )
        except DownloadError as exc:
            self.app.call_from_thread(self._show_error, str(exc))
            return
        self.app.call_from_thread(self._download_finished, path)

    def _append_results(self, results: list[SearchResult]) -> None:
        if not results:
            self._set_status("No new results were found.")
            return
        self._results.extend(results)
        self._seen_ids.update(result.item_id for result in results)
        select = self.query_one("#results", Select)
        select.set_options(
            [(f"{index + 1}. {result.label}", str(index)) for index, result in enumerate(self._results)]
        )
        self.query_one("#more-results", Button).disabled = True
        self.query_one("#more-results", Button).disabled = len(results) < 10
        self._set_status(f"Found {len(results)} new result(s). Select one to inspect quality.")

    def _set_formats(self, formats: list[FormatOption]) -> None:
        self._formats = formats
        self._quality_confirmation_required = len(formats) == 1
        select = self.query_one("#formats", Select)
        select.set_options(
            [(format_option.label, format_option.format_id) for format_option in formats]
        )
        if self._quality_confirmation_required:
            self._set_status("Only one quality is available. Download to continue anyway.")
        else:
            self._set_status("Choose an audio quality and download folder.")

    def _start_download(self) -> None:
        if self._selected_result is None:
            self._set_status("Select a search result first.")
            return
        destination_text = self.query_one("#destination", Input).value.strip()
        if not destination_text:
            self._set_status("Choose a download folder first.")
            return
        format_value = self.query_one("#formats", Select).value
        format_id = str(format_value) if isinstance(format_value, str) else "bestaudio/best"
        destination = Path(destination_text).expanduser()
        if self._quality_confirmation_required:
            self._quality_confirmation_required = False
            self.query_one("#download", Button).label = "Confirm download"
            self._set_status("Press Confirm download to use the only available quality.")
            return
        self.query_one("#download", Button).disabled = True
        self._set_status("Starting download...")
        self._download_worker(self._selected_result, destination, format_id)

    def _browse_destination(self) -> None:
        current = Path(self.query_one("#destination", Input).value or ".").expanduser()
        if not current.is_dir():
            current = current.parent
        self.app.push_screen(DestinationPicker(current), self._destination_selected)

    def _destination_selected(self, path: Path | None) -> None:
        if path is not None:
            self.query_one("#destination", Input).value = str(path)

    def _use_default_destination(self) -> None:
        default_directory = get_default_download_directory(self.config)
        if default_directory is None:
            self._set_status("No default folder is configured.")
            return
        self.query_one("#destination", Input).value = str(default_directory)

    def _clear_results(self) -> None:
        self._results.clear()
        self._formats.clear()
        self._selected_result = None
        self.query_one("#results", Select).set_options([])
        self.query_one("#formats", Select).set_options([])
        self.query_one("#more-results", Button).disabled = True

    def _update_progress(self, progress: DownloadProgress) -> None:
        if progress.percent is None:
            self._set_status(progress.message)
        else:
            self._set_status(f"Downloading: {progress.percent:.1f}%")

    def _download_finished(self, path: Path) -> None:
        self.query_one("#download", Button).disabled = False
        self._set_status(f"Downloaded: {path.as_posix()}")
        getattr(self.app, "handle_download_complete")(path)
        self.app.notify("Download completed.")

    def _set_status(self, message: str) -> None:
        self.query_one("#download-status", Static).update(message)

    def _show_error(self, message: str) -> None:
        self.query_one("#download", Button).disabled = False
        self._set_status(f"Error: {message}")
        self.app.notify(message, severity="error")
