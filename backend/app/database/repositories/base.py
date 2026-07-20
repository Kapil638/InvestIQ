"""Report and owner-user repository interfaces."""

from typing import Protocol

from app.models.owner_user import OwnerUser, WebAuthnCredential
from app.models.research_report import StoredResearchReport
from app.schemas.research import ResearchReportResponse
from app.schemas.storage import ReportSummary


class ReportRepository(Protocol):
    async def save(self, report: ResearchReportResponse) -> StoredResearchReport: ...

    async def get_by_id(self, report_id: str) -> StoredResearchReport | None: ...

    async def list_reports(
        self,
        *,
        ticker: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ReportSummary], int]: ...

    async def delete(self, report_id: str) -> bool: ...


class UserRepository(Protocol):
    """Owner-user + WebAuthn credential storage for the single-owner auth gate.

    `list_credentials(owner_id=None)` returning ALL credentials when no owner_id
    is given is deliberate: the pre-login WebAuthn authenticate-options endpoint
    needs to list allowed credential IDs without knowing who's asking, since
    there's exactly one owner in this scope. A multi-user system would need to
    scope this by email/handle instead.
    """

    async def get_or_create_owner(
        self,
        *,
        google_sub: str,
        email: str,
        display_name: str | None,
        picture_url: str | None,
    ) -> OwnerUser: ...

    async def get_owner_by_id(self, owner_id: str) -> OwnerUser | None: ...

    async def touch_last_login(self, owner_id: str) -> None: ...

    async def add_credential(
        self,
        *,
        owner_id: str,
        credential_id: str,
        public_key: str,
        sign_count: int,
        transports: list[str],
        device_label: str | None,
    ) -> WebAuthnCredential: ...

    async def get_credential(self, credential_id: str) -> WebAuthnCredential | None: ...

    async def list_credentials(self, owner_id: str | None = None) -> list[WebAuthnCredential]: ...

    async def update_sign_count(self, credential_id: str, sign_count: int) -> None: ...
