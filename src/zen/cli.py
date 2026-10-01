"""Command-line entry point for zen."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from .config import (
    add_music_root,
    get_config_path,
    load_config,
    remove_music_root,
    save_config,
    set_default_download_directory,
)
from .library.scanner import scan_roots
from .storage.database import LibraryDatabase
from .tui.app import ZenApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zen")
    commands = parser.add_subparsers(dest="command")

    config_parser = commands.add_parser("config", help="Manage zen configuration")
    config_commands = config_parser.add_subparsers(dest="config_command")

    config_commands.add_parser("list", help="List configured music roots")

    add_parser = config_commands.add_parser("add-root", help="Add a music folder")
    add_parser.add_argument("path", type=Path)

    remove_parser = config_commands.add_parser("remove-root", help="Remove a music folder")
    remove_parser.add_argument("path", type=Path)

    download_parser = config_commands.add_parser(
        "set-download-dir",
        help="Set the default download folder",
    )
    download_parser.add_argument("path", type=Path)

    scan_parser = commands.add_parser("scan", help="Scan configured music folders")
    scan_parser.add_argument(
        "--details",
        action="store_true",
        help="Print every discovered audio file",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        ZenApp().run()
        return

    if args.command == "config":
        _handle_config(args, parser)
        return

    if args.command == "scan":
        _handle_scan(args)
        return


def _handle_config(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.config_command is None:
        parser.parse_args(["config", "--help"])
        return

    config_path = get_config_path()
    config = load_config(config_path)

    if args.config_command == "list":
        print(f"Config: {config_path}")
        if not config.music_roots:
            print("No music roots configured.")
            return
        for root in config.music_roots:
            print(root)
        print(
            "Default download directory: "
            f"{config.default_download_directory or 'first music root'}"
        )
        return

    try:
        if args.config_command == "add-root":
            config = add_music_root(config, args.path)
        elif args.config_command == "remove-root":
            config = remove_music_root(config, args.path)
        elif args.config_command == "set-download-dir":
            config = set_default_download_directory(config, args.path)
        else:
            parser.error(f"Unknown config command: {args.config_command}")
            return
        save_config(config, config_path)
    except ValueError as exc:
        parser.error(str(exc))


def _handle_scan(args: argparse.Namespace) -> None:
    config = load_config()
    if not config.music_roots:
        raise SystemExit("zen: no music roots configured; use 'zen config add-root PATH'")

    tracks = list(scan_roots(config.music_roots))
    summary = LibraryDatabase().sync_tracks(config.music_roots, tracks)
    print(
        f"Scanned {summary.scanned} audio file(s): "
        f"{summary.added} added, {summary.updated} updated, {summary.removed} removed."
    )
    if args.details:
        for track in tracks:
            duration = f" ({track.duration:.0f}s)" if track.duration is not None else ""
            print(f"{track.path}{duration}")
