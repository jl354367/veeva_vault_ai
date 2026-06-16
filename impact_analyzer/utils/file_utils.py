"""
File handling utilities — saving uploads, cleaning up temp files.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".xls"}


def validate_upload(filename: str, content_length: int) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    if content_length > settings.max_upload_bytes:
        raise ValueError(
            f"File exceeds maximum size of {settings.max_upload_mb} MB."
        )


def save_upload(session_id: str, label: str, filename: str, content: bytes) -> str:
    """
    Persist uploaded file bytes to local storage.
    Returns the absolute path to the saved file.
    """
    session_dir = settings.storage_path / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(filename).suffix.lower()
    dest = session_dir / f"{label}{ext}"
    dest.write_bytes(content)
    logger.info("Saved upload '%s' → %s (%d bytes)", label, dest, len(content))
    return str(dest)


def delete_session_files(session_id: str) -> None:
    """Remove all temp files for a session."""
    session_dir = settings.storage_path / session_id
    if session_dir.exists():
        for f in session_dir.iterdir():
            f.unlink(missing_ok=True)
        session_dir.rmdir()
        logger.info("Cleaned up session files for %s", session_id)
