"""Tests for structured agent output parsing."""

from app.guardrails.structured_output_parser import parse_analysis_output, parse_risk_output
from tests.pipeline_mocks import ANALYSIS_CREW_OUTPUT, RISK_CREW_OUTPUT


def test_parse_analysis_output_marks_parsed_scores() -> None:
    output = parse_analysis_output(ANALYSIS_CREW_OUTPUT)
    assert output.scores_estimated is False


def test_parse_analysis_output_marks_estimated_scores_on_fallback() -> None:
    output = parse_analysis_output("Strong growth outlook without JSON block.")
    assert output.scores_estimated is True


def test_parse_risk_output_marks_parsed_scores() -> None:
    output = parse_risk_output(RISK_CREW_OUTPUT)
    assert output.scores_estimated is False


def test_parse_risk_output_marks_estimated_scores_on_fallback() -> None:
    output = parse_risk_output("Key Risks:\n- Regulatory pressure")
    assert output.scores_estimated is True
