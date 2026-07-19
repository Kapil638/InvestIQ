"""Google Drive API client for report PDF uploads (OAuth user delegation or service account)."""

from __future__ import annotations

import asyncio
import io
import json
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.services.google_drive_token_store import GoogleDriveTokenStore, get_google_drive_token_store
from app.utils.exceptions import GoogleDriveNotConnectedError, GoogleDriveServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)

DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive.file",)
DRIVE_VIEW_URL = "https://drive.google.com/file/d/{file_id}/view"


@dataclass(frozen=True)
class DriveUploadResult:
    file_id: str
    url: str


class GoogleDriveApiClient:
    """Upload PDFs to Google Drive.

    Prefers OAuth user delegation (required for personal Gmail accounts, since
    bare service accounts have no storage quota of their own) and falls back to
    a service account if one is configured (Workspace / Shared Drive setups).
    """

    def __init__(
        self,
        settings: Settings,
        token_store: GoogleDriveTokenStore | None = None,
    ) -> None:
        self._settings = settings
        self._token_store = token_store or get_google_drive_token_store()
        self._service: Any | None = None
        self._folder_cache: dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return self._settings.google_drive_enabled and self._has_credentials()

    def assert_enabled(self) -> None:
        if not self._settings.google_drive_enabled:
            raise GoogleDriveNotConnectedError("Google Drive is not connected.")
        if not self._has_credentials():
            raise GoogleDriveNotConnectedError("Google Drive is not connected.")

    def _has_credentials(self) -> bool:
        return bool(
            self._token_store.is_authenticated()
            or self._settings.google_drive_service_account_file
            or self._settings.google_drive_service_account_json
        )

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service

        try:
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GoogleDriveServiceError(
                "Google Drive API libraries are not installed. "
                "Install with: pip install google-api-python-client google-auth"
            ) from exc

        credentials = self._oauth_credentials() or self._service_account_credentials()

        if credentials is None:
            raise GoogleDriveNotConnectedError("Google Drive is not connected.")

        self._service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return self._service

    def _oauth_credentials(self) -> Any | None:
        session = self._token_store.get_session()
        if session is None:
            return None

        from google.oauth2.credentials import Credentials

        credentials = Credentials(
            token=session.access_token,
            refresh_token=session.refresh_token,
            token_uri=session.token_uri,
            client_id=session.client_id,
            client_secret=session.client_secret,
            scopes=session.scopes,
        )

        # google-auth refreshes automatically on expiry via googleapiclient, but
        # that refresh only lives on this in-memory Credentials object — persist
        # the new access token back to the store so it survives past this request.
        original_refresh = credentials.refresh

        def _refresh_and_persist(request: Any) -> None:
            original_refresh(request)
            self._token_store.update_access_token(credentials.token, credentials.expiry)

        credentials.refresh = _refresh_and_persist  # type: ignore[method-assign]
        return credentials

    def _service_account_credentials(self) -> Any | None:
        if not (
            self._settings.google_drive_service_account_file
            or self._settings.google_drive_service_account_json
        ):
            return None

        from google.oauth2 import service_account

        if self._settings.google_drive_service_account_json:
            info = json.loads(self._settings.google_drive_service_account_json)
            return service_account.Credentials.from_service_account_info(info, scopes=DRIVE_SCOPES)
        return service_account.Credentials.from_service_account_file(
            self._settings.google_drive_service_account_file,
            scopes=DRIVE_SCOPES,
        )

    async def upload_pdf(
        self, *, folder_path: str, filename: str, pdf_bytes: bytes
    ) -> DriveUploadResult:
        self.assert_enabled()
        return await asyncio.to_thread(
            self._upload_pdf_sync,
            folder_path,
            filename,
            pdf_bytes,
        )

    def _upload_pdf_sync(
        self, folder_path: str, filename: str, pdf_bytes: bytes
    ) -> DriveUploadResult:
        try:
            from googleapiclient.http import MediaIoBaseUpload
        except ImportError as exc:
            raise GoogleDriveServiceError(
                "Google Drive API libraries are not installed."
            ) from exc

        service = self._get_service()
        parent_id = self._ensure_folder_path(service, folder_path)

        media = MediaIoBaseUpload(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            resumable=False,
        )
        metadata = {"name": filename, "parents": [parent_id]}
        created = (
            service.files()
            .create(body=metadata, media_body=media, fields="id,webViewLink")
            .execute()
        )
        file_id = created.get("id")
        if not file_id:
            raise GoogleDriveServiceError("Google Drive upload did not return a file id")

        url = created.get("webViewLink") or DRIVE_VIEW_URL.format(file_id=file_id)
        logger.info("Uploaded %s to Google Drive folder %s", filename, folder_path)
        return DriveUploadResult(file_id=str(file_id), url=str(url))

    def _ensure_folder_path(self, service: Any, folder_path: str) -> str:
        parts = [part.strip() for part in folder_path.split("/") if part.strip()]
        parent_id = self._settings.google_drive_root_folder_id or "root"

        for part in parts:
            cache_key = f"{parent_id}/{part}"
            if cache_key in self._folder_cache:
                parent_id = self._folder_cache[cache_key]
                continue

            existing = self._find_child_folder(service, parent_id, part)
            folder_id = existing or self._create_folder(service, parent_id, part)
            self._folder_cache[cache_key] = folder_id
            parent_id = folder_id

        return parent_id

    @staticmethod
    def _find_child_folder(service: Any, parent_id: str, name: str) -> str | None:
        escaped = name.replace("'", "\\'")
        query = (
            f"mimeType='application/vnd.google-apps.folder' "
            f"and name='{escaped}' and '{parent_id}' in parents and trashed=false"
        )
        response = (
            service.files()
            .list(q=query, spaces="drive", fields="files(id)", pageSize=1)
            .execute()
        )
        files = response.get("files") or []
        if not files:
            return None
        return str(files[0]["id"])

    @staticmethod
    def _create_folder(service: Any, parent_id: str, name: str) -> str:
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        created = service.files().create(body=metadata, fields="id").execute()
        folder_id = created.get("id")
        if not folder_id:
            raise GoogleDriveServiceError(f"Failed to create Google Drive folder: {name}")
        return str(folder_id)
