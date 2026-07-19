"""Upload report PDFs to Google Drive via the Drive API."""

from __future__ import annotations

from app.core.config import Settings
from app.providers.google_drive_api_client import DriveUploadResult, GoogleDriveApiClient
from app.services.report_pdf_service import build_drive_folder_path


class GoogleDriveService:
    def __init__(self, settings: Settings, client: GoogleDriveApiClient | None = None) -> None:
        self._settings = settings
        self._client = client or GoogleDriveApiClient(settings)

    @property
    def connected(self) -> bool:
        return self._client.enabled

    async def upload_report_pdf(
        self, *, ticker: str, filename: str, pdf_bytes: bytes
    ) -> DriveUploadResult:
        folder_path = build_drive_folder_path(ticker)
        return await self._client.upload_pdf(
            folder_path=folder_path,
            filename=filename,
            pdf_bytes=pdf_bytes,
        )
