import ast
import subprocess
from pathlib import Path

from app.models import Chunk, Locator

REPOS_DIR = Path(__file__).resolve().parents[2] / "data" / "repos"
CODE_EXTENSIONS = {".py", ".md", ".js", ".ts", ".go", ".java", ".rs", ".toml", ".yaml", ".yml"}
MAX_FILE_BYTES = 200_000  # skip huge generated files
WINDOW = 60  # lines per chunk for non-Python files and very long functions
OVERLAP = 10


def load_github(repo_url: str, collection: str, subpath: str = "") -> list[Chunk]:
    """Clone a GitHub repo and chunk its code; Python is split into whole functions and classes."""
    repo_url = repo_url.rstrip("/").removesuffix(".git")
    repo_dir = _clone(repo_url)
    chunks: list[Chunk] = []
    for file in sorted((repo_dir / subpath).rglob("*")):
        if not _wanted(file):
            continue
        rel_path = file.relative_to(repo_dir).as_posix()
        lines = file.read_text(errors="ignore").splitlines()
        pieces = _python_pieces(file, lines) if file.suffix == ".py" else _windows(lines, 1, len(lines))
        for name, start, end in pieces:
            body = "\n".join(lines[start - 1 : end])
            if not body.strip():
                continue
            label = f"{rel_path} > {name}" if name else rel_path
            chunks.append(
                Chunk(
                    collection=collection,
                    document_id=f"code:{repo_url}/{rel_path}",
                    chunk_index=len(chunks),
                    text=f"# {label} (lines {start}-{end})\n{body}",
                    locator=Locator(
                        source_type="code", uri=repo_url, path=rel_path,
                        line_start=start, line_end=end, section=label,
                    ),
                    metadata={"repo": repo_url, "language": file.suffix.lstrip(".")},
                )
            )
    return chunks


def _clone(repo_url: str) -> Path:
    """Shallow-clone into data/repos/<owner>__<name>, or pull if it is already there."""
    owner, name = repo_url.split("/")[-2:]
    target = REPOS_DIR / f"{owner}__{name}"
    if target.exists():
        subprocess.run(["git", "-C", str(target), "pull", "--quiet"], check=True)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--depth", "1", "--quiet", repo_url, str(target)], check=True)
    return target


def _wanted(file: Path) -> bool:
    return (
        file.is_file()
        and file.suffix in CODE_EXTENSIONS
        and ".git" not in file.parts
        and file.stat().st_size <= MAX_FILE_BYTES
    )


def _python_pieces(file: Path, lines: list[str]) -> list[tuple[str, int, int]]:
    """(name, first line, last line) for each top-level function/class; big classes split per method."""
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return _windows(lines, 1, len(lines))
    pieces: list[tuple[str, int, int]] = []
    covered: set[int] = set()
    for node in tree.body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = node.decorator_list[0].lineno if node.decorator_list else node.lineno
        end = node.end_lineno
        covered.update(range(start, end + 1))
        if isinstance(node, ast.ClassDef) and end - start > WINDOW:
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    s = item.decorator_list[0].lineno if item.decorator_list else item.lineno
                    pieces += _windows(lines, s, item.end_lineno, f"{node.name}.{item.name}")
        else:
            pieces += _windows(lines, start, end, node.name)
    # module-level code (imports, constants, scripts) that is not inside any function or class
    rest = [n for n in range(1, len(lines) + 1) if n not in covered and lines[n - 1].strip()]
    if len(rest) >= 5:
        pieces += _windows(lines, rest[0], rest[-1], "module")
    return pieces


def _windows(lines: list[str], start: int, end: int, name: str = "") -> list[tuple[str, int, int]]:
    """Split lines start..end into overlapping windows of WINDOW lines."""
    out = []
    pos = start
    while pos <= end:
        stop = min(pos + WINDOW - 1, end)
        out.append((name, pos, stop))
        if stop == end:
            break
        pos = stop - OVERLAP + 1
    return out
