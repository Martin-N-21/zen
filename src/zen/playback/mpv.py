"""mpv JSON IPC playback backend."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from dataclasses import replace
from itertools import count
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Any, BinaryIO, cast

from .base import PlaybackError, PlaybackState


class MpvBackend:
    """Control a headless mpv process through one persistent JSON IPC connection."""

    _OBSERVED_PROPERTIES = {
        1: "path",
        2: "duration",
        3: "time-pos",
        4: "pause",
        5: "volume",
        6: "eof-reached",
        7: "idle-active",
    }

    def __init__(
        self,
        executable: str = "mpv",
        request_timeout: float = 0.75,
        startup_timeout: float = 3.0,
    ) -> None:
        self.executable = executable
        self.request_timeout = request_timeout
        self.startup_timeout = startup_timeout
        self._process: subprocess.Popen[bytes] | None = None
        self._endpoint: str | None = None
        self._connection: _IpcConnection | None = None
        self._request_ids = count(1)
        self._state = PlaybackState()

    def load(self, path: Path) -> None:
        path = path.expanduser().resolve(strict=False)
        if not path.is_file():
            raise PlaybackError(f"Audio file does not exist: {path}")

        self._request(["loadfile", str(path), "replace"])
        self._state = PlaybackState(path=path, volume=self._state.volume)
        self.play()

    def play(self) -> None:
        self._request(["set_property", "pause", False])
        self._state = replace(self._state, paused=False, eof=False, error=None)

    def pause(self) -> None:
        self._request(["set_property", "pause", True])
        self._state = replace(self._state, paused=True, error=None)

    def stop(self) -> None:
        if self._process is None:
            self._state = PlaybackState(volume=self._state.volume)
            return

        self._request(["stop"])
        self._state = PlaybackState(volume=self._state.volume)

    def toggle_pause(self) -> None:
        self.poll()
        if self._state.path is None:
            return
        next_pause = not self._state.paused
        self._request(["set_property", "pause", next_pause])
        self._state = replace(self._state, paused=next_pause, error=None)

    def seek(self, seconds: float) -> None:
        if self._state.path is None:
            return
        self._request(["seek", seconds, "relative"])

    def set_volume(self, volume: float) -> None:
        normalized_volume = max(0.0, min(100.0, volume))
        self._request(["set_property", "volume", normalized_volume])
        self._state = replace(self._state, volume=normalized_volume, error=None)

    def poll(self) -> PlaybackState:
        """Drain cached IPC events without blocking the UI thread."""

        process = self._process
        connection = self._connection
        if process is None:
            return self._state

        if process.poll() is not None:
            self._disconnect()
            self._state = replace(self._state, error="mpv exited unexpectedly")
            return self._state

        if connection is None or not connection.is_alive:
            self._state = replace(self._state, error="mpv IPC connection closed")
            return self._state

        for message in connection.drain():
            self._handle_message(message)
        return self._state

    def close(self) -> None:
        process = self._process
        endpoint = self._endpoint

        if process is None:
            self._disconnect()
            _cleanup_endpoint(endpoint)
            return

        try:
            if self._connection is not None:
                try:
                    self._request(["quit"])
                except PlaybackError:
                    pass
        finally:
            self._disconnect()

        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=1.0)
        finally:
            self._process = None
            self._endpoint = None
            _cleanup_endpoint(endpoint)

    def _request(self, command: list[Any]) -> Any:
        self._ensure_started()
        connection = self._connection
        if connection is None:
            raise PlaybackError("mpv IPC connection is not available")

        request_id = next(self._request_ids)
        payload = {"command": command, "request_id": request_id}
        try:
            return connection.request(payload, request_id, self.request_timeout)
        except PlaybackError as exc:
            self._disconnect()
            raise PlaybackError(f"mpv IPC request failed: {exc}") from exc

    def _ensure_started(self) -> None:
        if self._process is not None:
            if self._process.poll() is not None:
                _cleanup_endpoint(self._endpoint)
                self._process = None
                self._endpoint = None
                self._disconnect()
                raise PlaybackError("mpv exited unexpectedly")
            if self._connection is None:
                self._connect_to_endpoint(time.monotonic() + self.startup_timeout)
            return

        executable = shutil.which(self.executable)
        if executable is None:
            raise PlaybackError("mpv was not found on PATH. Install mpv and try again.")

        endpoint = _make_endpoint()
        command = [
            executable,
            "--idle=yes",
            "--no-video",
            "--force-window=no",
            "--terminal=no",
            "--audio-stream-silence=yes",
            "--pulse-allow-suspended=yes",
            f"--input-ipc-server={endpoint}",
        ]
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._process = process
        self._endpoint = endpoint

        try:
            self._connect_to_endpoint(time.monotonic() + self.startup_timeout)
        except PlaybackError:
            self.close()
            raise

    def _connect_to_endpoint(self, deadline: float) -> None:
        endpoint = self._endpoint
        if endpoint is None:
            raise PlaybackError("mpv IPC endpoint is not available")

        last_error: OSError | PlaybackError | None = None
        while time.monotonic() < deadline:
            process = self._process
            if process is not None and process.poll() is not None:
                raise PlaybackError("mpv exited before opening its IPC endpoint")

            if not _endpoint_is_ready(endpoint):
                time.sleep(0.05)
                continue

            try:
                self._connection = _IpcConnection.connect(endpoint)
                self._register_observers()
                return
            except (OSError, PlaybackError) as exc:
                last_error = exc
                self._disconnect()
                time.sleep(0.05)

        detail = f": {last_error}" if last_error else ""
        raise PlaybackError(f"Timed out connecting to mpv IPC{detail}")

    def _register_observers(self) -> None:
        for property_id, name in self._OBSERVED_PROPERTIES.items():
            self._request(["observe_property", property_id, name])

    def _disconnect(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is not None:
            connection.close()

    def _handle_message(self, message: dict[str, Any]) -> None:
        event = message.get("event")
        if event == "end-file":
            if message.get("reason") == "error":
                file_error = message.get("file_error") or "unknown playback error"
                self._state = replace(
                    self._state,
                    paused=True,
                    error=f"mpv playback error: {file_error}",
                )
            return

        if event != "property-change":
            return

        name = message.get("name")
        value = message.get("data")
        if name == "idle-active" and bool(value):
            self._state = PlaybackState(volume=self._state.volume, error=self._state.error)
        elif name == "path":
            if isinstance(value, str) and value:
                self._state = replace(self._state, path=Path(value), eof=False, error=None)
            else:
                self._state = PlaybackState(volume=self._state.volume, error=self._state.error)
        elif name == "duration":
            self._state = replace(self._state, duration=_number_or_none(value))
        elif name == "time-pos":
            self._state = replace(self._state, position=_number_or_zero(value))
        elif name == "pause":
            self._state = replace(self._state, paused=bool(value))
        elif name == "volume":
            self._state = replace(self._state, volume=_number_or_default(value, self._state.volume))
        elif name == "eof-reached":
            reached_eof = bool(value)
            self._state = replace(self._state, eof=reached_eof, paused=reached_eof)


class _IpcConnection:
    """Persistent line-oriented IPC connection with a background reader."""

    def __init__(self, stream: BinaryIO, socket_connection: socket.socket | None) -> None:
        self._stream = stream
        self._socket = socket_connection
        self._messages: Queue[dict[str, Any]] = Queue()
        self._write_lock = Lock()
        self._closed = Event()
        self._reader = Thread(target=self._read_loop, daemon=True)
        self._reader.start()

    @classmethod
    def connect(cls, endpoint: str) -> _IpcConnection:
        if os.name == "nt":
            return cls(open(endpoint, "r+b", buffering=0), None)

        unix_family = getattr(socket, "AF_UNIX", None)
        if unix_family is None:
            raise OSError("Unix IPC sockets are not available on this platform")
        connection = socket.socket(unix_family, socket.SOCK_STREAM)
        connection.connect(endpoint)
        stream = cast(BinaryIO, connection.makefile("rwb", buffering=0))
        return cls(stream, connection)

    @property
    def is_alive(self) -> bool:
        return self._reader.is_alive() and not self._closed.is_set()

    def request(self, payload: dict[str, Any], request_id: int, timeout: float) -> Any:
        deferred: list[dict[str, Any]] = []
        with self._write_lock:
            try:
                self._stream.write(_json_line(payload))
                self._stream.flush()
            except (OSError, ValueError) as exc:
                raise PlaybackError(str(exc)) from exc

            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                remaining = deadline - time.monotonic()
                try:
                    message = self._messages.get(timeout=max(remaining, 0.01))
                except Empty as exc:
                    self._restore_messages(deferred)
                    raise PlaybackError("timed out") from exc

                if message.get("request_id") != request_id:
                    deferred.append(message)
                    continue

                self._restore_messages(deferred)
                error = message.get("error", "success")
                if error != "success":
                    raise PlaybackError(f"mpv rejected command: {error}")
                return message.get("data")

        raise PlaybackError("timed out")

    def drain(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        while True:
            try:
                messages.append(self._messages.get_nowait())
            except Empty:
                return messages

    def close(self) -> None:
        self._closed.set()
        try:
            self._stream.close()
        except (OSError, ValueError):
            pass
        if self._socket is not None:
            try:
                self._socket.close()
            except OSError:
                pass
        self._reader.join(timeout=0.5)

    def _read_loop(self) -> None:
        while not self._closed.is_set():
            try:
                line = self._stream.readline()
            except (OSError, ValueError):
                return
            if not line:
                return
            try:
                message = json.loads(line.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(message, dict):
                self._messages.put(message)

    def _restore_messages(self, messages: list[dict[str, Any]]) -> None:
        for message in messages:
            self._messages.put(message)


def _make_endpoint() -> str:
    if os.name == "nt":
        return rf"\\.\pipe\zen-mpv-{os.getpid()}-{next(_ENDPOINT_IDS)}"
    return str(
        Path(tempfile.gettempdir())
        / f"zen-mpv-{os.getpid()}-{next(_ENDPOINT_IDS)}.sock"
    )


def _endpoint_is_ready(endpoint: str) -> bool:
    if os.name == "nt":
        try:
            with open(endpoint, "r+b", buffering=0):
                return True
        except OSError:
            return False
    return Path(endpoint).exists()


def _cleanup_endpoint(endpoint: str | None) -> None:
    if endpoint and os.name != "nt":
        Path(endpoint).unlink(missing_ok=True)


def _json_line(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")


def _number_or_none(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _number_or_zero(value: Any) -> float:
    number = _number_or_none(value)
    return number if number is not None else 0.0


def _number_or_default(value: Any, default: float) -> float:
    number = _number_or_none(value)
    return number if number is not None else default


_ENDPOINT_IDS = count(1)
