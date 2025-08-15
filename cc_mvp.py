from pathlib import Path
import re, glob
import pdfplumber
from docx import Document as DocxDocument

MAX_CHUNK = 1200
CHUNK_OVERLAP = 150

def normalize_text(t: str) -> str:
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"-\n", "", t)    # join hyphen linebreaks
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()

def read_pdf(path: Path) -> str:
    parts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)

def read_docx(path: Path) -> str:
    doc = DocxDocument(str(path))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

def read_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def chunk_text(text: str):
    i, n = 0, len(text)
    while i < n:
        end = min(n, i + MAX_CHUNK)
        yield (i, end, text[i:end])
        if end == n: break
        i = end - CHUNK_OVERLAP

def main():
    docs = sorted(glob.glob("data/docs/*"))
    if not docs:
        print("Put a few files in data/docs/ (PDF, DOCX, or TXT).")
        return
    for p in docs:
        path = Path(p)
        if path.suffix.lower()==".pdf":
            raw = read_pdf(path)
        elif path.suffix.lower()==".docx":
            raw = read_docx(path)
        else:
            raw = read_txt(path)
        text = normalize_text(raw)
        chunks = list(chunk_text(text))
        print(f"{path.name}: {len(text):,} chars, {len(chunks)} chunks")

if __name__ == "__main__":
    main()
