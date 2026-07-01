"""
File handling utilities.

Three small jobs:
  1. Check that an uploaded file is a supported type and not too big.
  2. Save the uploaded bytes under storage/<session_id>/<label>.<ext>.
  3. Delete the session's files when the user hits Reset.
"""

from __future__ import annotations

import logging
from pathlib import Path

from config import settings

logger = logging.getLogger(__name__)

# File extensions the tool knows how to accept. Anything else is rejected upfront.
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md", ".xlsx", ".xls"}


def validate_upload(filename: str, content_length: int) -> None:
    """
    Reject bad uploads early — before we save any bytes to disk.

    Raises ValueError if:
      - the extension isn't in the allowed list, or
      - the file is bigger than the configured max size.
    """
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
    Write the uploaded bytes to a per-session folder.

    Layout: storage/<session_id>/<label>.<ext>
    (label is a short key like "data_model_doc" so we don't collide with
    other file kinds in the same session.)

    Returns the absolute path to the saved file so the caller can remember it.
    """
    session_dir = settings.storage_path / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(filename).suffix.lower()
    dest = session_dir / f"{label}{ext}"
    dest.write_bytes(content)
    logger.info("Saved upload '%s' → %s (%d bytes)", label, dest, len(content))
    return str(dest)


def delete_session_files(session_id: str) -> None:
    """
    Wipe all files (and the folder) for a session.

    Called when the user clicks Reset in the UI, so uploads don't accumulate.
    Silent no-op if the session folder never existed.
    """
    session_dir = settings.storage_path / session_id
    if session_dir.exists():
        for f in session_dir.iterdir():
            f.unlink(missing_ok=True)
        session_dir.rmdir()
        logger.info("Cleaned up session files for %s", session_id)
