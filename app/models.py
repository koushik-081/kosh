import hashlib
from typing import Literal

from pydantic import BaseModel, Field

SourceType = Literal["pdf", "docx", "pptx", "web", "code", "youtube", "table"]


class Locator(BaseModel):
    """Where a chunk came from, precise enough to build a deep link."""

    source_type: SourceType
    uri: str  # file path, page URL, repo URL or video URL
    page: int | None = None  # PDF / DOCX / PPTX / table
    section: str | None = None  # heading path, e.g. "Tutorial > Dependencies"
    anchor: str | None = None  # web: #fragment of the heading
    path: str | None = None  # code: file path inside the repo
    line_start: int | None = None
    line_end: int | None = None
    start_sec: float | None = None  # YouTube / audio
    table_id: str | None = None

    def deep_link(self) -> str:
        match self.source_type:
            case "code":
                lines = f"#L{self.line_start}-L{self.line_end}" if self.line_start else ""
                return f"{self.uri}/blob/HEAD/{self.path}{lines}"
            case "youtube":
                return f"{self.uri}&t={int(self.start_sec or 0)}s"
            case "web":
                return f"{self.uri}#{self.anchor}" if self.anchor else self.uri
            case _:
                return f"{self.uri}#page={self.page}" if self.page else self.uri


class Chunk(BaseModel):
    collection: str  # e.g. "fastapi-demo"; one collection = one knowledge base
    document_id: str  # stable id of the source document
    chunk_index: int  # position of this chunk inside its document
    text: str
    locator: Locator
    metadata: dict = Field(default_factory=dict)
    version: int = 1

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()
