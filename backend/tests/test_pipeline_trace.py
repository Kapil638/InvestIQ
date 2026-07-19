"""Pipeline trace and risk extraction tests."""

from app.services.pipeline_tracer import PipelineTracer
from app.services.risk_extraction_service import extract_structured_risks


def test_pipeline_tracer_records_stages() -> None:
    tracer = PipelineTracer()
    tracer.start("financial")
    tracer.complete("financial")
    tracer.start("risk")
    tracer.complete("risk")
    trace = tracer.to_list()
    stages = [entry.stage for entry in trace]
    assert "financial" in stages
    assert "risk" in stages
    assert all(entry.duration_ms is not None for entry in trace if entry.status == "completed")


def test_risk_extraction_from_analysis() -> None:
    analysis = (
        "Infosys shows improving momentum.\n\n"
        "Key Risks:\n"
        "- Wage inflation\n"
        "- FX volatility\n"
    )
    result = extract_structured_risks(analysis)
    assert result.risk_count >= 2
    assert any("Wage" in risk for risk in result.risks)
