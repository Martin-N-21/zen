# zen

`zen` is a local music player for the terminal, designed for keyboard-only use in Bash and PowerShell.

The project is being developed as both a personal tool and a junior software-engineering portfolio project.

## Planned Features

- Browse music folders and subfolders with a lazy-loaded tree.
- Play local audio files through `mpv`.
- Show the current file, full path, total duration, live position, and progress.
- Store the local library and playback history in SQLite.
- Search the library quickly.
- Support MP3, FLAC, OGG, and WAV files.
- Work from both Linux/WSL and Windows terminals.

AI features are intentionally out of scope for the music player. A separate AI project may be built later using the library data.

## Requirements

- `uv`.
- `mpv` available on `PATH`.

`uv` will install and use the Python version declared in `.python-version`.

On Debian or WSL, install the system prerequisites with:

```bash
sudo apt update
sudo apt install -y curl mpv
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

When running the application directly from Windows, install the Windows build of `mpv` and make sure its executable is available on `PATH`.

Install `uv` from the official instructions for Windows and then run from PowerShell:

```powershell
Set-Location "C:\Users\User\Desktop\zen"
uv sync
uv run zen
```

## Setup

From WSL:

```bash
cd /mnt/c/Users/User/Desktop/zen
uv sync
```

## Run

```bash
uv run zen
```

The current version only contains the initial Textual shell. Library scanning, SQLite persistence, and `MpvBackend` will be implemented in later steps.

## Checks

```bash
uv run pytest
uv run ruff check .
uv run pyright
```

## License

The license will be selected before the first public release.
