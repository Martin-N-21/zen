from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Static


class ZenApp(App[None]):
    """Initial terminal shell for the zen music player."""

    TITLE = "zen"
    BINDINGS = [("q", "quit", "Quit")]

    CSS = """
    Screen {
        align: center middle;
    }

    #welcome {
        width: 60;
        height: 7;
        border: round $accent;
        content-align: center middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(
            "zen\n\nMusic library and playback are coming next.",
            id="welcome",
        )
        yield Footer()
