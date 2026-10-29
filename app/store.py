from collections.abc import Callable

import psycopg
from pgvector import Vector
from pgvector.psycopg import register_vector

from app.config import get_settings
from app.llm import embed
from app.models import Chunk


def connect() -> psycopg.Connection:
    conn = psycopg.connect(get_settings().database_url)
    register_vector(conn)
    return conn


def save_chunks(
    chunks: list[Chunk], batch_size: int = 32, on_progress: Callable[[int, int], None] | None = None
) -> int:
    """Embed and store chunks, skipping ones already in the collection. Returns how many were added.

    on_progress(done, total) is called before each batch, so callers can show progress.
    """
    added = 0
    with connect() as conn:
        for i in range(0, len(chunks), batch_size):
            if on_progress:
                on_progress(i, len(chunks))
            batch = chunks[i : i + batch_size]
            new = _skip_existing(conn, batch)
            if not new:
                continue
            vectors = embed([c.text for c in new])
            for chunk, vector in zip(new, vectors):
                cur = conn.execute(
                    """
                    INSERT INTO chunks
                        (collection, document_id, chunk_index, text, locator,
                         metadata, version, content_hash, embedding)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (collection, content_hash) DO NOTHING
                    """,
                    (
                        chunk.collection,
                        chunk.document_id,
                        chunk.chunk_index,
                        chunk.text,
                        chunk.locator.model_dump_json(exclude_none=True),
                        psycopg.types.json.Jsonb(chunk.metadata),
                        chunk.version,
                        chunk.content_hash,
                        Vector(vector),
                    ),
                )
                added += cur.rowcount
    return added


def _skip_existing(conn: psycopg.Connection, batch: list[Chunk]) -> list[Chunk]:
    """Drop chunks whose text is already stored, so we don't spend time embedding them again."""
    rows = conn.execute(
        "SELECT content_hash FROM chunks WHERE collection = %s AND content_hash = ANY(%s)",
        (batch[0].collection, [c.content_hash for c in batch]),
    ).fetchall()
    seen = {r[0] for r in rows}
    return [c for c in batch if c.content_hash not in seen]
