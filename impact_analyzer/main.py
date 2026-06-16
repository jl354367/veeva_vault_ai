"""
Impact Analyzer — FastAPI application entry point.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from config import settings
from routers import chat, stage1, stage2
from services import analysis_service
from utils.file_utils import delete_session_files

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.DEBUG if settings.app_env == "development" else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Impact Analyzer starting up (env=%s)", settings.app_env)
    if not settings.anthropic_api_key:
        logger.warning(
            "ANTHROPIC_API_KEY is not set — LLM calls will fail. "
            "Set it in .env or as an environment variable."
        )
    yield
    logger.info("Impact Analyzer shutting down")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Impact Analyzer",
    description=(
        "Two-stage impact analysis tool.\n\n"
        "**Stage 1** — upload a Data Model Changes Document; the system fetches the "
        "Configuration Report from S3 and produces a detailed impact report showing "
        "which objects and fields are affected.\n\n"
        "**Stage 2** — upload an Integration Specification Document; the system "
        "combines it with the Stage 1 report to produce a final integration impact "
        "report with migration steps.\n\n"
        "**Q&A** — ask plain-language questions about either report and get "
        "grounded, context-aware answers."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.app_env == "development" else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Global error handler ─────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url, exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Check server logs."},
    )


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(stage1.router)
app.include_router(stage2.router)
app.include_router(chat.router)


# ─── Health / root ────────────────────────────────────────────────────────────

@app.get("/", tags=["UI"], include_in_schema=False)
async def serve_ui():
    """Serve the frontend so it runs on the same origin as the API (no CORS issues)."""
    ui_file = Path(__file__).parent / "index.html"
    return FileResponse(str(ui_file), media_type="text/html")


@app.get("/api", tags=["Health"])
async def root():
    return {
        "service": "Impact Analyzer",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.delete("/session/{session_id}", tags=["Session"], summary="Reset / delete a session")
async def delete_session(session_id: str):
    """
    Clear all state for the given session — in-memory data and uploaded files.
    Called by the frontend Reset button.
    """
    try:
        analysis_service._sessions.pop(session_id, None)
        delete_session_files(session_id)
    except Exception as exc:
        logger.warning("Error cleaning up session %s: %s", session_id, exc)
    return {"deleted": session_id}


@app.get("/health", tags=["Health"])
async def health():
    checks = {
        "anthropic_api_key": bool(settings.anthropic_api_key),
        "aws_s3_configured": bool(settings.s3_config_bucket),
        "aws_agent_configured": bool(settings.aws_agent_lambda_arn or settings.aws_agent_id),
        "storage_writable": _check_storage(),
    }
    status = "healthy" if all(checks.values()) else "degraded"
    return {"status": status, "checks": checks}


def _check_storage() -> bool:
    try:
        test = settings.storage_path / ".write_test"
        test.write_text("ok")
        test.unlink()
        return True
    except Exception:
        return False


# ─── Dev runner ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
