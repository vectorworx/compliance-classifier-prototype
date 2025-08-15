# src/llm_layer.py
# Tags: #ccai #ccengine #ccproof
from dataclasses import dataclass
from typing import List, Dict, Optional
import os, re


@dataclass
class LLMFinding:
    rule_id: str
    label: str
    severity: str
    confidence: float
    rationale: str


def _heuristic_classify_gdpr(text: str) -> list[LLMFinding]:
    """Cheap, deterministic fallback for GDPR hints when no LLM key is present."""
    t = text.lower()
    hints_time = any(
        p in t for p in ["72 hours", "seventy-two hours", "three days", "undue delay", "promptly"]
    )
    hints_notify = any(p in t for p in ["notify", "notification", "inform", "report"])
    hints_regulator = any(p in t for p in ["supervisory authority", "regulator", "controller"])
    if hints_notify and hints_regulator and (hints_time or "promptly" in t):
        conf = 0.65 if "promptly" in t and "72" not in t else 0.85
        return [
            LLMFinding(
                rule_id="GDPR-BREACH-72H-IMPLICIT",
                label="Breach Notification (timing implied)",
                severity="medium",
                confidence=conf,
                rationale=(
                    "Detected notification to regulator with implied/approximate timing "
                    "(e.g., 'promptly'); recommend human review."
                ),
            )
        ]
    return []


def _heuristic_classify_soc2(text: str) -> list[LLMFinding]:
    """Cheap fallback for SOC 2 hints (access control/encryption)."""
    t = text.lower()
    mfa = "mfa" in t or "multi-factor" in t or "multifactor" in t
    enc = "encryption" in t or "tls" in t or "at rest" in t or "in transit" in t
    finds: list[LLMFinding] = []
    if mfa:
        finds.append(
            LLMFinding(
                rule_id="SOC2-ACCESS-CONTROL-IMPLICIT",
                label="Access Controls (policy signal)",
                severity="low",
                confidence=0.6,
                rationale="Mentions MFA/multi-factor; treat as supporting evidence, not a pass/fail.",
            )
        )
    if enc:
        finds.append(
            LLMFinding(
                rule_id="SOC2-ENCRYPTION-IMPLICIT",
                label="Encryption (policy signal)",
                severity="low",
                confidence=0.6,
                rationale="Mentions encryption/TLS; treat as supporting evidence, not a pass/fail.",
            )
        )
    return finds


def _maybe_openai_client():
    """Return a callable that takes prompt -> (label, confidence, rationale) if OPENAI_API_KEY is set, else None."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI  # openai>=1.0

        client = OpenAI(api_key=api_key)

        def _call(prompt: str) -> dict:
            # Small, inexpensive model—adjust if desired
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a compliance assistant. Answer in strict JSON.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
            )
            content = resp.choices[0].message.content
            import json

            return json.loads(content)

        return _call
    except Exception:
        return None


def analyze_text(regime: str, text: str) -> list[dict]:
    """
    Returns a list of dicts shaped like rule findings:
    {rule_id, label, severity, start, end, snippet, confidence, source, rationale}
    """
    llm = _maybe_openai_client()

    # If no LLM configured, use heuristics
    if not llm:
        if regime.upper() == "GDPR":
            findings = _heuristic_classify_gdpr(text)
        elif regime.upper() == "SOC2":
            findings = _heuristic_classify_soc2(text)
        else:
            findings = []
    else:
        # Minimal prompt—kept tight for cost/reliability.
        if regime.upper() == "GDPR":
            prompt = (
                "Task: Determine if text implies GDPR breach-notification timing.\n"
                "Return JSON with: label, rule_id, severity (low|medium|high), confidence (0-1), rationale.\n"
                "Criteria: mentions notifying regulator/authority/controller AND mentions timing (72 hours, three days, or implied terms like 'promptly'/'undue delay').\n"
                f"Text:\n{text[:4000]}"
            )
        elif regime.upper() == "SOC2":
            prompt = (
                "Task: Identify SOC 2-relevant policy signals for access controls or encryption.\n"
                "Return JSON array (0-2 items), fields: label, rule_id, severity, confidence (0-1), rationale.\n"
                f"Text:\n{text[:4000]}"
            )
        else:
            return []

        try:
            result = llm(prompt)
            if isinstance(result, dict):
                result = [result]
            findings = []
            for item in result or []:
                findings.append(
                    LLMFinding(
                        rule_id=item.get("rule_id", "AI-GENERIC"),
                        label=item.get("label", "AI Finding"),
                        severity=item.get("severity", "low"),
                        confidence=float(item.get("confidence", 0.5)),
                        rationale=item.get("rationale", ""),
                    )
                )
        except Exception:
            # fall back to heuristics on any API failure
            if regime.upper() == "GDPR":
                findings = _heuristic_classify_gdpr(text)
            elif regime.upper() == "SOC2":
                findings = _heuristic_classify_soc2(text)
            else:
                findings = []

    out: list[dict] = []
    for f in findings:
        out.append(
            {
                "rule_id": f.rule_id,
                "label": f.label,
                "severity": f.severity,
                "start": None,
                "end": None,
                "snippet": text[:200].replace("\n", " "),
                "confidence": round(f.confidence, 2),
                "source": "llm",
                "rationale": f.rationale,
            }
        )
    return out
