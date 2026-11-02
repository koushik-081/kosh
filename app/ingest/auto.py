from app.ingest.github import load_github
from app.ingest.pdf import load_pdf
from app.ingest.web import load_web
from app.ingest.youtube import load_youtube
from app.models import Chunk


def load_any(source: str, collection: str, subpath: str = "") -> list[Chunk]:
    """Pick the right connector from what the source looks like (used by the CLI and the API)."""
    if "youtube.com/" in source or "youtu.be/" in source:
        return load_youtube(source, collection)
    if source.startswith("https://github.com/"):
        return load_github(source, collection, subpath)
    if source.startswith(("http://", "https://")):
        return load_web(source, collection)
    return load_pdf(source, collection)