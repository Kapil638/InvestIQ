"""Structured risk extraction from analysis text – deterministic, no LLM."""

from __future__ import annotations

import re

from app.schemas.research import StructuredRiskAssessment

_RISK_HEADERS = re.compile(
    r"(?:^|\n)\s*(?:#{1,3}\s*)?(?:key\s+)?risks?(?:\s+and\s+concerns)?\s*[:\-]?\s*\n",
    re.IGNORECASE,
)
_BULLET = re.compile(r"^\s*[-*•]\s+(.+)$", re.MULTILINE)
_NUMBERED = re.compile(r"^\s*\d+[\.)]\s+(.+)$", re.MULTILINE)
_BEARISH = re.compile(
    r"\b(risk|downside|concern|debt|volatile|slowdown|pressure|headwind|uncertainty)\b",
    re.IGNORECASE,
)


def extract_structured_risks(analysis: str | None) -> StructuredRiskAssessment:
    if not analysis or not analysis.strip():
        return StructuredRiskAssessment(risks=[], source="analysis", risk_count=0)

    risks: list[str] = []
    header_match = _RISK_HEADERS.search(analysis)
    if header_match:
        section = analysis[header_match.end() :]
        next_section = re.search(r"\n\s*[A-Z][a-z]+(?:\s+[A-z]+){0,3}\s*[:\-]\s*\n", section)
        if next_section:
            section = section[: next_section.start()]
        risks.extend(_extract_bullets(section))

    if len(risks) < 2:
        for line in analysis.split("\n"):
            cleaned = line.strip()
            if len(cleaned) < 20:
                continue
            if _BEARISH.search(cleaned) and cleaned not in risks:
                risks.append(re.sub(r"^[-*•]\s*", "", cleaned))

    deduped: list[str] = []
    seen: set[str] = set()
    for risk in risks:
        key = risk.lower()[:80]
        if key not in seen:
            seen.add(key)
            deduped.append(risk[:300])

    return StructuredRiskAssessment(
        risks=deduped[:8],
        source="analysis",
        risk_count=len(deduped),
    )


def _extract_bullets(section: str) -> list[str]:
    items: list[str] = []
    for pattern in (_BULLET, _NUMBERED):
        for match in pattern.finditer(section):
            text = match.group(1).strip()
            if len(text) > 12:
                items.append(text)
    return items
