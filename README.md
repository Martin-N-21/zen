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
- Search and download audio through supported `yt-dlp` platforms.
- Work from both Linux/WSL and Windows terminals.

AI features are intentionally out of scope for the music player. A separate AI project may be built later using the library data.

## Requirements

- `uv`.
- `mpv` available on `PATH`.
- `yt-dlp` available on `PATH` for downloads.
- `ffmpeg` available on `PATH` for audio conversion.

`uv` will install and use the Python version declared in `.python-version`.

On Debian or WSL, install the system prerequisites with:

```bash
sudo apt update
sudo apt install -y curl mpv ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
```

Install `yt-dlp` separately if downloads are enabled:

```bash
uv tool install --force yt-dlp
source "$HOME/.local/bin/env"
yt-dlp --version
```

Use a current `yt-dlp` release. Distribution packages can be outdated and may fail against recent platform changes.

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

## Configure music folders

The configuration is stored in the platform-specific user configuration directory. Add one or more local music folders with:

```bash
uv run zen config add-root "/mnt/c/Users/YourUser/Music"
uv run zen config list
```

On PowerShell, use a Windows path:

```powershell
uv run zen config add-root "C:\Users\YourUser\Music"
```

Set the default download folder with:

```bash
uv run zen config set-download-dir "/mnt/c/Users/YourUser/Music"
```

## Run

```bash
uv run zen
```

The current version can persist music folders and scan supported audio files into SQLite. It includes a lazy-loaded library tree, an `MpvBackend` for local playback, and the first download screen backed by `yt-dlp`.

To scan configured folders:

```bash
uv run zen scan --details
```

The SQLite database is stored in the platform-specific user data directory as `zen/library.db`.

## Keyboard Controls

- `Enter`: expand a folder or play a file.
- `←` / `→`: collapse or expand the selected folder.
- `Space`: play or pause.
- `h` / `l`: seek backward or forward five seconds.
- `-` / `=`: decrease or increase volume.
- `s`: stop playback.
- `d`: open the download screen.
- `q`: quit.

## Checks

```bash
uv run pytest
uv run ruff check .
uv run pyright
```

## License

The license will be selected before the first public release.
