from pathlib import Path
import re, yaml
from dataclasses import dataclass
from typing import List, Dict, Iterable, Tuple

@dataclass
class Rule:
    id: str
    label: str
    severity: str
    pattern: re.Pattern

def load_rules(yaml_path: Path) -> List[Rule]:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    out: List[Rule] = []
    for r in data.get("rules", []):
        if r.get("type","regex") != "regex":
            continue
        pat = re.compile(r["value"])
        out.append(Rule(id=r["id"], label=r["label"], severity=r.get("severity","info"), pattern=pat))
    return out

def scan_chunks(text: str, rules: List[Rule]) -> Iterable[Dict]:
    for r in rules:
        for m in r.pattern.finditer(text):
            start, end = m.span()
            snippet = text[max(0,start-80):min(len(text), end+80)]
            yield {
                "rule_id": r.id,
                "label": r.label,
                "severity": r.severity,
                "start": start,
                "end": end,
                "snippet": snippet.replace("\n"," ")
            }
