from pathlib import Path
import re, glob
import pdfplumber
from docx import Document as DocxDocument
from pathlib import Path
import csv
from src.engine import load_rules, scan_chunks


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

def load_ruleset(regime: str) -> list[Path]:
    base = Path("rules")
    if regime.upper() == "GDPR":
        return [base / "gdpr_critical.yml"]
    if regime.upper() == "SOC2":
        return [base / "soc2_critical.yml"]
    return []


def main():
    import argparse, glob
    parser = argparse.ArgumentParser()
    parser.add_argument("--regime", choices=["GDPR","SOC2"], required=True)
    parser.add_argument("--out", default="data/outputs/findings.csv")
    args = parser.parse_args()

    rule_files = load_ruleset(args.regime)
    if not rule_files:
        print("No rules found. Add files in rules/ .")
        return

    # load & merge rules
    rules = []
    for f in rule_files:
        rules.extend(load_rules(f))
    print(f"Loaded {len(rules)} rules for {args.regime}")

    docs = sorted(glob.glob("data/docs/*"))
    if not docs:
        print("Put a few files in data/docs/ (PDF, DOCX, or TXT).")
        return

    rows = []
    for p in docs:
        path = Path(p)
        # ingest
        if path.suffix.lower()==".pdf":
            raw = read_pdf(path)
        elif path.suffix.lower()==".docx":
            raw = read_docx(path)
        else:
            raw = read_txt(path)
        text = normalize_text(raw)

        # scan
        for finding in scan_chunks(text, rules):
            finding["doc"] = path.name
            rows.append(finding)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["doc","rule_id","label","severity","start","end","snippet"])
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {len(rows)} findings → {args.out}")
