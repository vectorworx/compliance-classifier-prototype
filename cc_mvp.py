# cc_mvp.py — Compliance Classifier MVP with visible output + file writes
# Tags: #ccengine #ccrules #ccproof

from pathlib import Path
import re, glob, csv, json, argparse, datetime
from collections import Counter
from src.llm_layer import analyze_text
from src.audit import write_events, new_run_id

APP_VERSION = "0.1.0"

# Optional deps you already installed:
# pdfplumber, python-docx, PyYAML, pandas (pandas not required here)

# ---------- Ingestion ----------
import pdfplumber
from docx import Document as DocxDocument
import yaml

MAX_CHUNK = 1200
CHUNK_OVERLAP = 150


def normalize_text(t: str) -> str:
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"-\n", "", t)  # join hyphen linebreaks
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
        if end == n:
            break
        i = end - CHUNK_OVERLAP


# ---------- Rules ----------
def load_rules_file(yaml_path: Path):
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    rules = []
    for r in data.get("rules", []):
        if r.get("type", "regex") != "regex":
            continue
        pat = re.compile(r["value"])
        rules.append(
            {
                "id": r["id"],
                "label": r["label"],
                "severity": r.get("severity", "info"),
                "pattern": pat,
            }
        )
    return rules


def load_ruleset(regime: str):
    base = Path("rules")
    if regime.upper() == "GDPR":
        files = [base / "gdpr_critical.yml"]
    elif regime.upper() == "SOC2":
        files = [base / "soc2_critical.yml"]
    else:
        files = []
    rules = []
    for f in files:
        if not f.exists():
            raise FileNotFoundError(f"Missing rules file: {f}")
        rules.extend(load_rules_file(f))
    return rules


def scan_text(text: str, rules):
    for r in rules:
        for m in r["pattern"].finditer(text):
            start, end = m.span()
            snippet = text[max(0, start - 80) : min(len(text), end + 80)].replace("\n", " ")
            yield {
                "rule_id": r["id"],
                "label": r["label"],
                "severity": r["severity"],
                "start": start,
                "end": end,
                "snippet": snippet,
            }


# ---------- Orchestration ----------
def process_docs(regime: str):
    docs = sorted(glob.glob("data/docs/*"))
    if not docs:
        print("⚠ No input docs found. Add files under data/docs/ (PDF/DOCX/TXT).")
        return [], []

    rules = load_ruleset(regime)
    if not rules:
        print(f"⚠ No rules loaded for {regime}. Check rules/ folder.")
        return [], []

    all_rows = []
    doc_list = []
    for p in docs:
        path = Path(p)
        # ingest
        if path.suffix.lower() == ".pdf":
            raw = read_pdf(path)
        elif path.suffix.lower() == ".docx":
            raw = read_docx(path)
        else:
            raw = read_txt(path)
        text = normalize_text(raw)

        # (simple chunking here for realism; we scan full text)
        _ = list(chunk_text(text))  # placeholder for future chunk-level LLM

        # rules scan
        hits = list(scan_text(text, rules))

        # ✅ Targeted LLM: ONLY if there were no rule hits (avoid duplicates)
        if not hits:
            llm_hits = analyze_text(regime, text)
            for h in llm_hits:
                h["doc"] = path.name
            hits.extend(llm_hits)

        # finalize doc hits
        for h in hits:
            h["doc"] = path.name

        all_rows.extend(hits)
        doc_list.append(path.name)

    return all_rows, doc_list


def write_outputs(rows, regime: str):
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = Path("data/outputs")
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"findings_{regime.lower()}_{ts}.csv"
    json_path = out_dir / f"findings_{regime.lower()}_{ts}.json"

    # CSV
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["doc", "rule_id", "label", "severity", "start", "end", "snippet"]
        )
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "doc": r["doc"],
                    "rule_id": r["rule_id"],
                    "label": r["label"],
                    "severity": r["severity"],
                    "start": r["start"],
                    "end": r["end"],
                    "snippet": r["snippet"],
                }
            )

    # JSON
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    return csv_path, json_path


def print_summary(rows, regime: str, processed_docs):
    total = len(rows)
    by_rule = Counter(r["rule_id"] for r in rows)
    by_doc = Counter(r["doc"] for r in rows)
    llm_count = sum(1 for r in rows if r.get("source") == "llm")

    print("\n============================")
    print(f" Compliance Results — {regime}")
    print("============================")
    print(f"Processed docs: {len(processed_docs)} -> {processed_docs}")
    print(f"Total findings: {total}  (AI adds: {llm_count})")
    if total:
        print("\nTop rules:")
        for rid, cnt in by_rule.most_common():
            lbl = next((r["label"] for r in rows if r["rule_id"] == rid), rid)
            print(f"  - {rid} ({lbl}): {cnt}")
        print("\nPreview (first 3 findings):")
        for r in rows[:3]:
            s = r["snippet"]
            src = r.get("source", "rules")
            extra = f" [{src}, conf={r.get('confidence')}]" if src == "llm" else ""
            print(f"  • [{r['doc']}] {r['rule_id']}{extra}: {s[:140]}{'…' if len(s) > 140 else ''}")
    else:
        print("No matches found.")


def ascii_safe(s: str) -> str:
    # minimal mapping for Windows cp1252 / legacy consoles
    return (
        s.replace("→", "->")
        .replace("📄", "[doc]")
        .replace("🔎", "[find]")
        .replace("🔥", "[crit]")
        .replace("⬆", "[hi]")
        .replace("🏷️", "[rule]")
        .replace("⬇", "[out]")
        .replace("🧾", "[run]")
    )


def main():
    parser = argparse.ArgumentParser(description="Compliance Classifier MVP")
    parser.add_argument("--regime", choices=["GDPR", "SOC2"], required=True)
    args = parser.parse_args()

    rows, processed_docs = process_docs(args.regime)
    print_summary(rows, args.regime, processed_docs)

    # ✅ Persist to SQLite audit log (fixed indentation)
    run_id = new_run_id()
    if rows:
        count, db_path = write_events(rows, args.regime, APP_VERSION, run_id)
        print(f"\nAudit log: wrote {count} events to {db_path} (run_id={run_id})")

    # write outputs
    if rows:
        csv_path, json_path = write_outputs(rows, args.regime)
        print("\nOutputs written:")
        print(f"  CSV : {csv_path}")
        print(f"  JSON: {json_path}")
    else:
        print("\nNo outputs written (no findings).")


if __name__ == "__main__":
    main()
