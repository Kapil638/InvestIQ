from app.api.error_mapping import map_exception_to_response


class FakeClientError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"{status_code} UNAUTHENTICATED. {{'error': {{'message': '{message}'}}}}")
        self.status_code = status_code
        self.response_json = {"error": {"code": status_code, "message": message}}


def test_maps_google_auth_error_to_401(monkeypatch) -> None:
    monkeypatch.setitem(
        __import__("sys").modules,
        "google.genai.errors",
        type("m", (), {"ClientError": FakeClientError})(),
    )
    exc = FakeClientError(401, "Request had invalid authentication credentials.")

    mapped = map_exception_to_response(exc)

    assert mapped.status_code == 401
    assert "invalid authentication credentials" in mapped.detail
    assert "OPENROUTER_API_KEY" in mapped.detail
    assert mapped.error_type == "FakeClientError"


def test_maps_quota_error_to_429() -> None:
    exc = Exception("429 RESOURCE_EXHAUSTED. quota exceeded for gemini-2.0-flash")

    mapped = map_exception_to_response(exc)

    assert mapped.status_code == 429
    assert "quota" in mapped.detail.lower()


def test_maps_google_genai_import_error_to_503() -> None:
    exc = ImportError(
        'Google Gen AI native provider not available, to install: uv add "crewai[google-genai]"'
    )

    mapped = map_exception_to_response(exc)

    assert mapped.status_code == 503
    assert "crewai[google-genai]" in mapped.detail


def test_maps_unknown_error_with_exact_message() -> None:
    exc = RuntimeError("Crew kickoff failed: agent timeout")

    mapped = map_exception_to_response(exc)

    assert mapped.status_code == 500
    assert mapped.detail == "Crew kickoff failed: agent timeout"
    assert mapped.error_type == "RuntimeError"
