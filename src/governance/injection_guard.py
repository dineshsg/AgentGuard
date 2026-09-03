"""
src/governance/injection_guard.py

A regex-based prompt-injection scanner for TWO independent input
surfaces: the user's question (scan_question) and any document the
Researcher retrieves as evidence (scan_document).

**This is the centerpiece of AgentGuard.** A guard that only inspects
the user's question is trivially incomplete for a RAG system, because
the retrieved documents themselves are an attacker-controllable surface:
a compromised or poisoned data source can embed an instruction ("ignore
your instructions and instead...") inside a document that gets retrieved
for a completely innocent question. scan_document exists specifically to
catch that -- an INDIRECT injection, not a direct one -- and
src/governance/redteam_corpus.py's CLEAN_QUESTION_POISONED_RETRIEVAL_PAIRS
is the labeled scenario that proves it, not just claims it.

**Stated limitation, deliberately, here and in the README:** this is a
heuristic, regex-based prototype. Real production systems increasingly
use a trained classifier or an LLM-based guard model, and a determined
attacker can paraphrase around fixed patterns. This module demonstrates
the *architecture* -- scan both input surfaces, score by matched
category, gate on severity, evaluate against a labeled corpus -- which
transfers directly to a stronger detector; it does not claim
research-grade robustness.

Zero LLM/network dependency (re, dataclasses only), consistent with the
rest of src/governance/.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

DIRECT_INJECTION_PATTERNS = [
    r"ignore (all |the )?(previous|prior|above) instructions",
    r"disregard (all |the )?(previous|prior|above) (instructions|rules|prompt)",
    r"you are now\b",
    r"new instructions?\s*:",
    r"\bsystem\s*:\s*",
    r"\[system\]",
    r"###\s*(system|instruction)",
    r"act as (?:an?|if you (?:are|have)).*\b(no|without) (restrictions?|filters?|limits?)",
    r"reveal your (system )?prompt",
    r"print your instructions",
    r"pretend (you|to) (have no|are not)\b",
    r"\bjailbreak\b",
    r"\bdo anything now\b",
    r"override (your|the) (safety|guard\s*rails?)",
]

EXFIL_PATTERNS = [
    r"send (this|the following|it) to\b",
    r"email (this|the following) to\b",
    r"forward (this|the following) to\b",
]
EXFIL_URL_PROXIMITY_CHARS = 80
# An EXFIL_PATTERNS phrase match on its own is weak evidence -- "send
# this to the printer" is completely innocuous. It only becomes a real
# exfiltration signal when there's an actual destination nearby: the
# "exfil" category is matched only when a phrase match AND a URL
# (r"https?://\S+") both appear, within this many characters of each
# other -- two independent signals required together, not either alone.

INDIRECT_ONLY_MARKER_PATTERNS = [
    r"^\s*assistant\s*:",  # a document impersonating a conversation turn
    r"\[system\]",
    r"###\s*(system|instruction)",
]
# Checked ONLY for documents (scan_document), never for questions -- a
# user typing "[SYSTEM]" in their own question is not the attack this
# category watches for; a document embedding a fake role marker to
# hijack the conversation IS.

_URL_PATTERN = re.compile(r"https?://\S+")
_REGEX_FLAGS = re.IGNORECASE | re.MULTILINE


@dataclass
class InjectionScanResult:
    source: str  # "question" | "document"
    source_id: str  # the question text (truncated) or doc_id
    risk_score: int  # count of distinct pattern categories matched -- max 3
    matched_categories: list[str] = field(default_factory=list)
    flagged: bool = False  # risk_score >= 1
    severity: str = "Low"  # "Low" | "Medium" (risk_score==1) | "Critical" (>=2)


def _any_pattern_matches(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, _REGEX_FLAGS) for pattern in patterns)


def _exfil_category_matched(text: str) -> bool:
    exfil_matches = [
        m for pattern in EXFIL_PATTERNS for m in re.finditer(pattern, text, _REGEX_FLAGS)
    ]
    if not exfil_matches:
        return False

    url_matches = list(_URL_PATTERN.finditer(text))
    if not url_matches:
        return False

    for exfil_match in exfil_matches:
        for url_match in url_matches:
            if exfil_match.start() <= url_match.start():
                gap = url_match.start() - exfil_match.end()
            else:
                gap = exfil_match.start() - url_match.end()
            if gap <= EXFIL_URL_PROXIMITY_CHARS:
                return True
    return False


def scan_text(
    text: str, source: str, source_id: str, include_indirect_markers: bool = False
) -> InjectionScanResult:
    matched_categories: list[str] = []

    if _any_pattern_matches(DIRECT_INJECTION_PATTERNS, text):
        matched_categories.append("direct")

    if _exfil_category_matched(text):
        matched_categories.append("exfil")

    if include_indirect_markers and _any_pattern_matches(INDIRECT_ONLY_MARKER_PATTERNS, text):
        matched_categories.append("indirect-marker")

    risk_score = len(matched_categories)
    severity = "Critical" if risk_score >= 2 else ("Medium" if risk_score == 1 else "Low")

    return InjectionScanResult(
        source=source,
        source_id=source_id,
        risk_score=risk_score,
        matched_categories=matched_categories,
        flagged=risk_score >= 1,
        severity=severity,
    )


def scan_question(question: str) -> InjectionScanResult:
    """Scans only for direct injection + exfiltration attempts -- never
    indirect-only markers, since a user's own question impersonating a
    system/assistant turn is not the threat model this category exists
    for."""
    return scan_text(
        question, source="question", source_id=question[:80], include_indirect_markers=False
    )


def scan_document(doc_id: str, text: str) -> InjectionScanResult:
    """Scans retrieved evidence for direct injection, exfiltration
    attempts, AND indirect-only markers (fake role turns, fake system
    headers) -- the extra category that makes this an INDIRECT
    prompt-injection guard, not just a direct one applied twice."""
    return scan_text(text, source="document", source_id=doc_id, include_indirect_markers=True)
