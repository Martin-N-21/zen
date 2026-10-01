"""yt-dlp provider used by the download screen."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from .models import (
    DownloadError,
    DownloadProgress,
    FormatOption,
    ProgressCallback,
    SearchResult,
)

PLATFORMS = {
    "youtube": "ytsearch",
    "soundcloud": "scsearch",
}

_PERCENT_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")


class YtDlpProvider:
    """Run yt-dlp without invoking a shell."""

    def __init__(self, executable: str = "yt-dlp", metadata_timeout: float = 60.0) -> None:
        self.executable = executable
        self.metadata_timeout = metadata_timeout

    def search(
        self,
        platform: str,
        query: str,
        limit: int = 10,
        exclude_ids: Iterable[str] = (),
    ) -> list[SearchResult]:
        prefix = PLATFORMS.get(platform)
        if prefix is None:
            raise DownloadError(f"Search is not supported for platform: {platform}")
        if not query.strip():
            raise DownloadError("Search query cannot be empty")

        excluded = set(exclude_ids)
        requested = max(limit + len(excluded), limit)
        data = self._metadata(
            [
                "--flat-playlist",
                f"{prefix}{requested}:{query}",
            ]
        )
        results: list[SearchResult] = []
        for entry in data.get("entries", []):
            result = self._result_from_entry(entry, platform)
            if result is None or result.item_id in excluded:
                continue
            results.append(result)
            if len(results) == limit:
                break
        return results

    def inspect_url(self, platform: str, url: str) -> SearchResult:
        if not url.strip():
            raise DownloadError("URL cannot be empty")
        data = self._metadata(["--no-playlist", url])
        result = self._result_from_entry(data, platform)
        if result is None:
            raise DownloadError("yt-dlp did not return a downloadable media item")
        return result

    def formats(self, result: SearchResult) -> list[FormatOption]:
        data = self._metadata(["--no-playlist", result.url])
        options: list[FormatOption] = []
        seen_ids: set[str] = set()
        for raw_format in data.get("formats", []):
            if not isinstance(raw_format, dict):
                continue
            if raw_format.get("vcodec") not in (None, "none"):
                continue
            if raw_format.get("acodec") in (None, "none"):
                continue
            format_id = str(raw_format.get("format_id", ""))
            if not format_id or format_id in seen_ids:
                continue
            seen_ids.add(format_id)
            extension = str(raw_format.get("ext") or "unknown")
            codec = _optional_string(raw_format.get("acodec"))
            bitrate = _number(raw_format.get("abr")) or _number(raw_format.get("tbr"))
            bitrate_label = f"{bitrate:.0f} kbps" if bitrate is not None else "unknown bitrate"
            codec_label = f" {codec}" if codec else ""
            options.append(
                FormatOption(
                    format_id=format_id,
                    extension=extension,
                    codec=codec,
                    bitrate=bitrate,
                    label=f"{format_id}: {extension}{codec_label}, {bitrate_label}",
                )
            )

        options.sort(key=lambda option: option.bitrate or 0, reverse=True)
        return options or [
            FormatOption(
                format_id="bestaudio/best",
                extension="best available",
                codec=None,
                bitrate=None,
                label="Best available quality",
            )
        ]

    def download(
        self,
        result: SearchResult,
        destination: Path,
        format_id: str = "bestaudio/best",
        audio_quality: str = "0",
        progress_callback: ProgressCallback | None = None,
    ) -> Path:
        executable = self._find_executable()
        destination = destination.expanduser().resolve(strict=False)
        destination.mkdir(parents=True, exist_ok=True)
        command = [
            executable,
            "--no-warnings",
            "--newline",
            "--no-playlist",
            "--format",
            format_id,
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--audio-quality",
            audio_quality,
            "--paths",
            str(destination),
            "--output",
            "%(title)s.%(ext)s",
            "--print",
            "after_move:filepath",
            result.url,
        ]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        printed_path: Path | None = None
        output_lines: list[str] = []
        if process.stdout is not None:
            for line in process.stdout:
                clean_line = line.strip()
                output_lines.append(clean_line)
                if progress_callback is not None:
                    progress_callback(
                        DownloadProgress(_parse_percent(clean_line), clean_line)
                    )
                candidate = Path(clean_line)
                if not candidate.is_absolute():
                    candidate = destination / candidate
                if candidate.is_file():
                    printed_path = candidate

        return_code = process.wait()
        if return_code != 0:
            details = next(
                (line for line in reversed(output_lines) if line.startswith("ERROR:")),
                "yt-dlp failed to download the item",
            )
            raise DownloadError(details)
        if printed_path is None:
            raise DownloadError("yt-dlp finished without returning the downloaded file")
        return printed_path

    def _metadata(self, arguments: list[str]) -> dict[str, Any]:
        executable = self._find_executable()
        command = [
            executable,
            "--no-warnings",
            "--dump-single-json",
            "--skip-download",
            *arguments,
        ]
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.metadata_timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise DownloadError("yt-dlp metadata request timed out") from exc
        if completed.returncode != 0:
            message = completed.stderr.strip() or "yt-dlp metadata request failed"
            raise DownloadError(message)
        try:
            data = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise DownloadError("yt-dlp returned invalid metadata") from exc
        if not isinstance(data, dict):
            raise DownloadError("yt-dlp returned an unexpected metadata object")
        return data

    def _find_executable(self) -> str:
        executable = shutil.which(self.executable)
        if executable is None:
            raise DownloadError(
                "yt-dlp was not found on PATH. Install yt-dlp before downloading."
            )
        return executable

    @staticmethod
    def _result_from_entry(entry: Any, platform: str) -> SearchResult | None:
        if not isinstance(entry, dict):
            return None
        item_id = _optional_string(entry.get("id"))
        url = _optional_string(entry.get("webpage_url")) or _optional_string(
            entry.get("original_url")
        )
        if url is None:
            raw_url = _optional_string(entry.get("url"))
            if raw_url and raw_url.startswith("http"):
                url = raw_url
        if url is None and item_id and platform == "youtube":
            url = f"https://www.youtube.com/watch?v={item_id}"
        if item_id is None or url is None:
            return None
        return SearchResult(
            item_id=item_id,
            title=_optional_string(entry.get("title")) or "Untitled",
            url=url,
            platform=platform,
            uploader=_optional_string(entry.get("uploader"))
            or _optional_string(entry.get("channel")),
            duration=_number(entry.get("duration")),
        )


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _parse_percent(line: str) -> float | None:
    match = _PERCENT_RE.search(line)
    return float(match.group(1)) if match else None
