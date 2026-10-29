import re

import httpx
from youtube_transcript_api import YouTubeTranscriptApi

from app.models import Chunk, Locator

VIDEO_ID = re.compile(r"(?:v=|youtu\.be/|shorts/|embed/)([A-Za-z0-9_-]{11})")
MAX_CHARS = 1200
OVERLAP_SNIPPETS = 2  # repeat the last few caption lines at the start of the next chunk


def load_youtube(url: str, collection: str) -> list[Chunk]:
    """Fetch a video's transcript and chunk it; every chunk remembers the second it starts at."""
    match = VIDEO_ID.search(url)
    if not match:
        raise ValueError(f"Not a YouTube video URL: {url}")
    video_id = match.group(1)
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    title = _title(video_url)
    snippets = [
        (s.start, " ".join(s.text.split()))  # collapse newlines and non-breaking spaces
        for s in YouTubeTranscriptApi().fetch(video_id, languages=["en"])
    ]

    chunks: list[Chunk] = []
    for start, text in _group(snippets):
        chunks.append(
            Chunk(
                collection=collection,
                document_id=f"youtube:{video_id}",
                chunk_index=len(chunks),
                text=text,
                locator=Locator(
                    source_type="youtube", uri=video_url, start_sec=start,
                    section=f"{title} @ {_mmss(start)}",
                ),
                metadata={"title": title, "video_id": video_id},
            )
        )
    return chunks


def _group(snippets: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """Join caption lines into ~MAX_CHARS chunks; returns (start second, text) pairs."""
    groups: list[tuple[float, str]] = []
    current: list[tuple[float, str]] = []
    for snippet in snippets:
        if current and sum(len(t) + 1 for _, t in current) + len(snippet[1]) > MAX_CHARS:
            groups.append((current[0][0], " ".join(t for _, t in current)))
            current = current[-OVERLAP_SNIPPETS:]
        current.append(snippet)
    if current:
        groups.append((current[0][0], " ".join(t for _, t in current)))
    return groups


def _title(video_url: str) -> str:
    """Video title from YouTube's public oEmbed endpoint (no API key needed)."""
    try:
        resp = httpx.get("https://www.youtube.com/oembed", params={"url": video_url, "format": "json"}, timeout=10)
        return resp.json()["title"]
    except (httpx.HTTPError, KeyError, ValueError):
        return video_url


def _mmss(seconds: float) -> str:
    minutes, secs = divmod(int(seconds), 60)
    return f"{minutes}:{secs:02d}"