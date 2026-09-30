# Development Guide

## Project

`zen` is a local, keyboard-driven music player for Bash and PowerShell. Audio playback is provided by the external `mpv` executable and will be isolated behind `MpvBackend`.

## Conventions

- Keep application code under `src/zen/`.
- Keep tests under `tests/`.
- Use `pathlib` for filesystem paths.
- Keep Textual UI code separate from storage, library scanning, and playback.
- Do not add AI features to the player unless explicitly requested.
- Do not store music files in the repository.

## Checks

```bash
uv run pytest
uv run ruff check .
uv run pyright
```
