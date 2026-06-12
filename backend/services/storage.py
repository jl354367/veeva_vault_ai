"""
Storage abstraction for custom training sessions.

Current backend : LOCAL       (files + JSON in backend/data/custom_training/)
Future  backend : SHAREPOINT  (Microsoft Graph API)

To migrate to SharePoint later:
  1. Set STORAGE_BACKEND=sharepoint in your environment / .env file.
  2. Provide these env vars:
       SHAREPOINT_SITE_URL      https://yourorg.sharepoint.com/sites/VaultBot
       SHAREPOINT_FOLDER        /CustomTraining
       SHAREPOINT_CLIENT_ID     Azure App Registration client ID
       SHAREPOINT_CLIENT_SECRET Azure App Registration client secret
       SHAREPOINT_TENANT_ID     Azure tenant ID
  3. Auth flow:
       POST https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token
       body: grant_type=client_credentials, scope=https://graph.microsoft.com/.default
       → returns access_token (Bearer)
  4. Upload file:
       PUT https://graph.microsoft.com/v1.0/sites/{site_id}/drives/{drive_id}/
           items/root:/{SHAREPOINT_FOLDER}/{session_id}_{file_name}:/content
  5. Store metadata in a SharePoint List named "VaultBotSessions" via Graph API.
     The list columns mirror the dict keys in save_session().
"""

import json
import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

# ── Config ─────────────────────────────────────────────────────────────────────

STORAGE_BACKEND  = os.getenv("STORAGE_BACKEND", "local")   # "local" | "sharepoint"

_LOCAL_DATA_DIR  = Path(__file__).parent.parent / "data" / "custom_training"
_LOCAL_META_FILE = _LOCAL_DATA_DIR / "sessions.json"


# ── Abstract interface ─────────────────────────────────────────────────────────

class StorageProvider(ABC):

    @abstractmethod
    def save_session(
        self,
        meta: dict,
        file_bytes: bytes | None,
        file_name: str | None,
    ) -> dict:
        """Persist a new training session. Returns saved session dict (with id, created_at)."""

    @abstractmethod
    def list_sessions(self) -> list[dict]:
        """Return all custom training sessions, newest first."""

    @abstractmethod
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and its attached file. Returns True if found and deleted."""

    @abstractmethod
    def get_file_bytes(self, session_id: str) -> tuple[bytes, str] | None:
        """Return (file_bytes, file_name) or None if no file is attached."""


# ── Local storage implementation ───────────────────────────────────────────────

class LocalStorage(StorageProvider):
    """
    Stores session metadata as a JSON file and file attachments on disk.
    Location: backend/data/custom_training/
    """

    def __init__(self):
        _LOCAL_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # -- Public interface -------------------------------------------------------

    def save_session(
        self,
        meta: dict,
        file_bytes: bytes | None,
        file_name: str | None,
    ) -> dict:
        session_id = str(uuid.uuid4())[:8]
        session = {**meta}
        session["id"]         = session_id
        session["created_at"] = datetime.now().isoformat()
        session["storage"]    = "local"
        session["file_name"]  = file_name
        session["file_path"]  = None

        if file_bytes and file_name:
            dest = _LOCAL_DATA_DIR / f"{session_id}_{file_name}"
            dest.write_bytes(file_bytes)
            session["file_path"] = str(dest)

        sessions = self._load()
        sessions.insert(0, session)
        _LOCAL_META_FILE.write_text(
            json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return session

    def list_sessions(self) -> list[dict]:
        return self._load()

    def delete_session(self, session_id: str) -> bool:
        sessions  = self._load()
        remaining = []
        deleted   = False
        for s in sessions:
            if s.get("id") == session_id:
                deleted = True
                if s.get("file_path"):
                    try:
                        Path(s["file_path"]).unlink(missing_ok=True)
                    except Exception:
                        pass
            else:
                remaining.append(s)
        if deleted:
            _LOCAL_META_FILE.write_text(
                json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return deleted

    def get_file_bytes(self, session_id: str) -> tuple[bytes, str] | None:
        for s in self._load():
            if s.get("id") == session_id and s.get("file_path"):
                p = Path(s["file_path"])
                if p.exists():
                    return p.read_bytes(), s.get("file_name", "file")
        return None

    # -- Private ---------------------------------------------------------------

    def _load(self) -> list[dict]:
        if not _LOCAL_META_FILE.exists():
            return []
        try:
            return json.loads(_LOCAL_META_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []


# ── SharePoint storage (future) ────────────────────────────────────────────────

class SharePointStorage(StorageProvider):
    """
    Placeholder for the future Microsoft SharePoint / Graph API backend.
    Raises NotImplementedError until SHAREPOINT_* env vars are configured
    and this class is implemented.
    """

    _NOT_READY = (
        "SharePoint storage is not yet configured. "
        "Set STORAGE_BACKEND=local until SharePoint credentials are available."
    )

    def save_session(self, meta, file_bytes, file_name):
        raise NotImplementedError(self._NOT_READY)

    def list_sessions(self):
        raise NotImplementedError(self._NOT_READY)

    def delete_session(self, session_id):
        raise NotImplementedError(self._NOT_READY)

    def get_file_bytes(self, session_id):
        raise NotImplementedError(self._NOT_READY)


# ── Factory ────────────────────────────────────────────────────────────────────

def get_storage() -> StorageProvider:
    """Return the configured storage provider (default: local)."""
    if STORAGE_BACKEND == "sharepoint":
        return SharePointStorage()
    return LocalStorage()
