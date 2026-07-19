from app.database.repositories.supabase_repository import _format_supabase_error
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
