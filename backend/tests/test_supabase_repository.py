from datetime import UTC, datetime

from app.database.repositories.supabase_repository import _format_supabase_error, _to_summary
from app.utils.exceptions import ExternalServiceError


class FakeApiError(Exception):
    def __init__(self, message: dict[str, str]) -> None:
        super().__init__(str(message))
        self.message = message


def test_format_supabase_error_extracts_policy_message() -> None:
    try:
        raise FakeApiError(
            {
                "message": (
                    'new row violates row-level security policy for table "research_reports"'
                ),
                "code": "42501",
            }
        )
    except FakeApiError as exc:
        wrapped = ExternalServiceError("wrapper")
        wrapped.__cause__ = exc
        detail = _format_supabase_error(wrapped)

    assert "row-level security policy" in detail


def _base_row(**overrides: object) -> dict:
    row = {
        "id": "abc-123",
        "ticker": "INFY",
        "company_name": "Infosys Limited",
        "guardrails_passed": True,
        "generated_at": datetime.now(UTC).isoformat(),
        "pdf_generated_at": None,
        "google_drive_file_id": None,
        "google_drive_url": None,
        "google_drive_saved_at": None,
        "confidence_score": None,
        "recommendation": None,
        "investment_committee": None,
    }
    row.update(overrides)
    return row


def test_to_summary_uses_lean_projection_with_recommendation() -> None:
    """_to_summary must work from list_reports()'s lean select() projection —
    it no longer receives a full report_json blob, only a handful of
    top-level columns plus specific report_json->* sub-fields."""
    row = _base_row(
        confidence_score=67,
        recommendation={
            "rating": "Hold",
            "confidence_score": 67.0,
            "reasoning": "test",
            "risks": [],
        },
    )

    summary = _to_summary(row)

    assert summary.id == "abc-123"
    assert summary.ticker == "INFY"
    assert summary.rating == "HOLD"
    assert summary.confidence_score == 67.0
    assert summary.guardrails_passed is True


def test_to_summary_falls_back_to_bare_confidence_score() -> None:
    """When there's no recommendation/investment_committee (e.g. an older
    report), resolve_report_summary falls back to the deterministic
    confidence-band mapping — this must still work from the lean row shape."""
    row = _base_row(confidence_score=42)

    summary = _to_summary(row)

    assert summary.confidence_score == 42.0
    assert summary.rating is not None


def test_to_summary_handles_all_optional_fields_missing() -> None:
    """No recommendation, no investment_committee, no confidence_score at all —
    must not raise, just return no rating/confidence."""
    row = _base_row()

    summary = _to_summary(row)

    assert summary.rating is None
    assert summary.confidence_score is None
