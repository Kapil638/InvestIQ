"""Parse structured JSON + narrative blocks from CrewAI agent output."""

from __future__ import annotations

import json
import re

from app.schemas.agent_outputs import AnalysisOutput, AnalysisScores, RiskOutput, RiskScores
from app.utils.logging import get_logger

logger = get_logger(__name__)

_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_INLINE_JSON = re.compile(r"\{[^{}]*\"(?:growth|overall_risk|overall)\"[^{}]*\}", re.DOTALL)


def parse_analysis_output(raw: str) -> AnalysisOutput:
    scores_data = _extract_json(raw)
    narrative = _extract_narrative(raw, scores_data)

    if scores_data:
        scores = AnalysisScores.model_validate(_normalize_analysis_keys(scores_data))
        scores_estimated = False
    else:
        logger.warning(
            "Analysis JSON parse failed for raw output, using keyword-fallback scores"
        )
        scores = _fallback_analysis_scores(narrative)
        scores_estimated = True

    return AnalysisOutput(narrative=narrative, scores=scores, scores_estimated=scores_estimated)


def parse_risk_output(raw: str) -> RiskOutput:
    scores_data = _extract_json(raw)
    narrative = _extract_narrative(raw, scores_data)

    if scores_data:
        normalized = _normalize_risk_keys(scores_data)
        scores = RiskScores.model_validate(normalized)
        risks = normalized.get("risks") or _extract_risk_bullets(narrative)
        if isinstance(risks, str):
            risks = [risks]
        scores_estimated = False
    else:
        logger.warning(
            "Risk JSON parse failed for raw output, using keyword-fallback scores"
        )
        scores = _fallback_risk_scores(narrative)
        risks = _extract_risk_bullets(narrative)
        scores_estimated = True

    return RiskOutput(
        narrative=narrative,
        scores=scores,
        risks=[str(r) for r in risks[:8]],
        scores_estimated=scores_estimated,
    )


def _extract_json(raw: str) -> dict | None:
    match = _JSON_BLOCK.search(raw)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    match = _INLINE_JSON.search(raw)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    start = raw.find("{")
    end = raw.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def _extract_narrative(raw: str, scores_data: dict | None) -> str:
    text = _JSON_BLOCK.sub("", raw).strip()
    if scores_data:
        text = text.replace(json.dumps(scores_data), "").strip()
    return text or raw[:4000]


def _normalize_analysis_keys(data: dict) -> dict:
    return {
        "growth": _clamp(data.get("growth", data.get("growth_score", 55))),
        "profitability": _clamp(data.get("profitability", data.get("profitability_score", 55))),
        "valuation": _clamp(data.get("valuation", data.get("valuation_score", 55))),
        "financial_health": _clamp(
            data.get("financial_health", data.get("financial_health_score", 55))
        ),
        "management": _clamp(data.get("management", data.get("management_score", 55))),
        "sector_strength": _clamp(
            data.get("sector_strength", data.get("sector", data.get("sector_score", 55)))
        ),
        "macro": _clamp(data.get("macro", data.get("macro_score", 55))),
        "overall": _clamp(data.get("overall", data.get("overall_score", 55))),
    }


def _normalize_risk_keys(data: dict) -> dict:
    return {
        "overall_risk": _clamp(data.get("overall_risk", data.get("overall", 50))),
        "financial": _clamp(data.get("financial", data.get("financial_risk", 50))),
        "governance": _clamp(data.get("governance", data.get("governance_risk", 30))),
        "macro": _clamp(data.get("macro", data.get("macro_risk", 35))),
        "business": _clamp(data.get("business", data.get("business_risk", 40))),
        "valuation": _clamp(data.get("valuation", data.get("valuation_risk", 45))),
        "regulatory": _clamp(data.get("regulatory", data.get("regulatory_risk", 25))),
        "risks": data.get("risks") or data.get("key_risks"),
    }


def _extract_risk_bullets(text: str) -> list[str]:
    section = re.search(
        r"(?:key risks?|risk factors?)\s*[:\-]?\s*(.+?)(?:\n\s*\n|\Z)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    body = section.group(1) if section else text
    items = re.findall(r"[-*•]\s*(.+)", body)
    return [i.strip() for i in items if len(i.strip()) > 3][:8]


def _fallback_analysis_scores(narrative: str) -> AnalysisScores:
    base = 55
    lower = narrative.lower()
    if any(w in lower for w in ("strong growth", "robust", "outperform")):
        base += 10
    if any(w in lower for w in ("weak", "decline", "pressure", "concern")):
        base -= 10
    return AnalysisScores(
        growth=base,
        profitability=base,
        valuation=base,
        financial_health=base,
        management=base,
        sector_strength=base,
        macro=base,
        overall=base,
    )


def _fallback_risk_scores(narrative: str) -> RiskScores:
    bullets = _extract_risk_bullets(narrative)
    overall = min(90, 35 + len(bullets) * 8)
    return RiskScores(
        overall_risk=overall,
        financial=overall,
        governance=30,
        macro=35,
        business=40,
        valuation=45,
        regulatory=25,
    )


def _clamp(value: object, default: int = 50) -> int:
    try:
        num = int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(0, min(100, num))
