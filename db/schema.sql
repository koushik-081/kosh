CREATE TABLE IF NOT EXISTS chunks (
    id           BIGSERIAL PRIMARY KEY,
    collection   TEXT        NOT NULL,
    document_id  TEXT        NOT NULL,
    chunk_index  INT         NOT NULL,
    text         TEXT        NOT NULL,
    locator      JSONB       NOT NULL,
    metadata     JSONB       NOT NULL DEFAULT '{}',
    version      INT         NOT NULL DEFAULT 1,
    content_hash TEXT        NOT NULL,
    embedding    vector(1024),
    tsv          tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (collection, content_hash)
);
CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX IF NOT EXISTS chunks_doc_idx ON chunks (collection, document_id);

-- Saved chats for the dashboard (Day 8a)
CREATE TABLE IF NOT EXISTS chats (
    id         BIGSERIAL PRIMARY KEY,
    title      TEXT        NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS messages (
    id         BIGSERIAL PRIMARY KEY,
    chat_id    BIGINT      NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role       TEXT        NOT NULL,              -- 'user' or 'assistant'
    content    TEXT        NOT NULL,
    details    JSONB       NOT NULL DEFAULT '{}', -- steps, sources, citations, unsupported
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_chat_idx ON messages (chat_id, id);