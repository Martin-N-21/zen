import json
from subprocess import CompletedProcess
from unittest.mock import patch

from zen.download.models import SearchResult
from zen.download.ytdlp import YtDlpProvider


def test_search_parses_flat_results() -> None:
    payload = {
        "entries": [
            {
                "id": "abc123",
                "title": "Example track",
                "webpage_url": "https://www.youtube.com/watch?v=abc123",
                "uploader": "Example artist",
                "duration": 125,
            }
        ]
    }
    provider = YtDlpProvider()
    completed = CompletedProcess([], 0, json.dumps(payload), "")

    with patch("zen.download.ytdlp.shutil.which", return_value="yt-dlp"):
        with patch("zen.download.ytdlp.subprocess.run", return_value=completed):
            results = provider.search("youtube", "example")

    assert len(results) == 1
    assert results[0].title == "Example track"
    assert results[0].url.endswith("abc123")


def test_formats_keep_audio_only_options() -> None:
    payload = {
        "formats": [
            {"format_id": "251", "ext": "webm", "acodec": "opus", "vcodec": "none", "abr": 160},
            {"format_id": "137", "ext": "mp4", "acodec": "none", "vcodec": "avc1", "tbr": 1000},
        ]
    }
    provider = YtDlpProvider()
    completed = CompletedProcess([], 0, json.dumps(payload), "")
    result = SearchResult(
        item_id="abc123",
        title="Example track",
        url="https://www.youtube.com/watch?v=abc123",
        platform="youtube",
    )

    with patch("zen.download.ytdlp.shutil.which", return_value="yt-dlp"):
        with patch("zen.download.ytdlp.subprocess.run", return_value=completed):
            options = provider.formats(result)

    assert [option.format_id for option in options] == ["251"]
