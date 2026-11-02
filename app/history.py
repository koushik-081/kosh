"""Saved chats, so the dashboard can reopen old conversations after a refresh or restart."""
from psycopg.types.json import Jsonb

from app.store import connect


def new_chat(title: str) -> int:
    with connect() as conn:
        return conn.execute("INSERT INTO chats (title) VALUES (%s) RETURNING id", (title[:80],)).fetchone()[0]


def add_message(chat_id: int, role: str, content: str, details: dict | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO messages (chat_id, role, content, details) VALUES (%s, %s, %s, %s)",
            (chat_id, role, content, Jsonb(details or {})),
        )


def list_chats(limit: int = 30) -> list[dict]:
    """Newest first."""
    with connect() as conn:
        rows = conn.execute("SELECT id, title FROM chats ORDER BY id DESC LIMIT %s", (limit,)).fetchall()
    return [{"id": chat_id, "title": title} for chat_id, title in rows]


def get_messages(chat_id: int) -> list[dict]:
    """In order, each as {"role", "content", plus the saved details}: the shape the dashboard keeps."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT role, content, details FROM messages WHERE chat_id = %s ORDER BY id", (chat_id,)
        ).fetchall()
    return [{"role": role, "content": content, **details} for role, content, details in rows]


def delete_chat(chat_id: int) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM chats WHERE id = %s", (chat_id,))  # its messages go too (ON DELETE CASCADE)