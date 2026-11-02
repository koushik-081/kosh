import json
import os
from collections.abc import Iterator

import httpx

API_URL = os.getenv("KOSH_API_URL", "http://localhost:8010")


def collections() -> list[dict]:
    return httpx.get(f"{API_URL}/collections", timeout=10).json()

def chats() -> list[dict]:
    return httpx.get(f"{API_URL}/chats", timeout=10).json()


def chat_messages(chat_id: int) -> list[dict]:
    return httpx.get(f"{API_URL}/chats/{chat_id}", timeout=10).json()


def new_chat(title: str) -> int:
    return httpx.post(f"{API_URL}/chats", json={"title": title}, timeout=10).json()["id"]


def save_message(chat_id: int, role: str, content: str, details: dict | None = None) -> None:
    payload = {"role": role, "content": content, "details": details or {}}
    httpx.post(f"{API_URL}/chats/{chat_id}/messages", json=payload, timeout=10).raise_for_status()


def delete_chat(chat_id: int) -> None:
    httpx.delete(f"{API_URL}/chats/{chat_id}", timeout=10).raise_for_status()


def stream_query(question: str, collection: str | None, k: int = 4) -> Iterator[tuple[str, object]]:
    """Yield (event, data) pairs from the /query Server-Sent Events stream."""
    payload = {"question": question, "collection": collection, "k": k, "stream": True}
    with httpx.stream("POST", f"{API_URL}/query", json=payload, timeout=300) as resp:
        resp.raise_for_status()
        event = None
        for line in resp.iter_lines():
            if line.startswith("event: "):
                event = line.removeprefix("event: ")
            elif line.startswith("data: "):
                yield event, json.loads(line.removeprefix("data: "))


def to_url(link: str) -> str:
    """Web links work as they are; PDF links point at data/, which the API serves at /files."""
    if link.startswith(("http://", "https://")):
        return link
    return f"{API_URL}/files/{link.removeprefix('data/')}"
