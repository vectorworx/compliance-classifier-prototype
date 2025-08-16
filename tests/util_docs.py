# Tags: #cctests #ccfixtures
from pathlib import Path
from contextlib import contextmanager
import shutil

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "data" / "docs"


@contextmanager
def temp_docs(files: dict[str, str]):
    """
    Temporarily write a set of {filename: content} into data/docs,
    yield the list of written Paths, then clean them up.
    """
    DOCS.mkdir(parents=True, exist_ok=True)
    written = []
    try:
        for name, content in files.items():
            p = DOCS / name
            p.write_text(content, encoding="utf-8")
            written.append(p)
        yield written
    finally:
        for p in written:
            try:
                p.unlink()
            except Exception:
                pass
        # keep docs dir for other tests; don't remove the folder
