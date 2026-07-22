"""Guardrail check – unsupported numeric claims (hallucination detection)."""

import re

from app.guardrails.evidence import EvidenceCorpus
from app.schemas.research import GuardrailIssue

# Matches $1.5B, $200, 45%, 1,000,000, 3.5 million, etc.
MONEY_PATTERN = re.compile(
    r"\$?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(billion|million|bn|mm|b|m)?",
    re.IGNORECASE,
)
PERCENT_PATTERN = re.compile(r"(\d{1,3}(?:\.\d+)?)\s*%")
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")


def check_hallucinations(analysis: str, corpus: EvidenceCorpus) -> list[GuardrailIssue]:
    issues: list[GuardrailIssue] = []
    unsupported: list[str] = []

    for match in MONEY_PATTERN.finditer(analysis):
        raw = match.group(0).strip()
        if YEAR_PATTERN.match(raw.lstrip("$").strip()):
            continue
        value = _parse_money(match.group(1), match.group(2))
        if value is None or value < 1_000:
            continue
        if not _number_supported(value, corpus.numbers):
            unsupported.append(raw)

    for match in PERCENT_PATTERN.finditer(analysis):
        raw = match.group(0)
        value = float(match.group(1))
        if not _percent_supported(value, corpus.numbers):
            unsupported.append(raw)

    if unsupported:
        unique = list(dict.fromkeys(unsupported))[:5]
        issues.append(
            GuardrailIssue(
                code="unsupported_numeric_claims",
                message=(
                    "Analysis contains numeric claims not found in source data: "
                    + ", ".join(unique)
                ),
                severity="error",
            )
        )

    if corpus.company_name and corpus.company_name.lower() not in analysis.lower():
        if corpus.ticker not in analysis.upper():
            issues.append(
                GuardrailIssue(
                    code="company_name_mismatch",
                    message=(
                        f"Analysis does not reference {corpus.company_name} or {corpus.ticker}"
                    ),
                    severity="warning",
                )
            )

    return issues


def _parse_money(number_str: str, suffix: str | None) -> float | None:
    try:
        base = float(number_str.replace(",", ""))
    except ValueError:
        return None
    if not suffix:
        return base
    suffix = suffix.lower()
    if suffix in {"billion", "bn", "b"}:
        return base * 1_000_000_000
    if suffix in {"million", "mm", "m"}:
        return base * 1_000_000
    return base


def _number_supported(value: float, corpus_numbers: set[float]) -> bool:
    if not corpus_numbers:
        return True
    for known in corpus_numbers:
        if known == 0:
            continue
        # MONEY_PATTERN never captures a leading minus sign, so a claim like
        # "277.94 million" parses to +277,940,000 even when citing a real
        # figure that is negative (e.g. negative operating cash flow) -
        # compare magnitudes, not signed values.
        magnitude = abs(known)
        ratio = value / magnitude
        if 0.85 <= ratio <= 1.15:
            return True
        if value > 1_000_000 and 0.5 <= ratio <= 2.0:
            return True
    return False


def _percent_supported(value: float, corpus_numbers: set[float]) -> bool:
    if not corpus_numbers:
        return True
    decimal = value / 100
    candidates = {value, decimal, round(decimal, 4)}
    for known in corpus_numbers:
        for candidate in candidates:
            if abs(known - candidate) <= max(0.5, abs(candidate) * 0.15):
                return True
    return value in {0.0, 100.0}
