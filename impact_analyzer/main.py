"""
Impact Analyzer — FastAPI application entry point.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from config import settings
from routers import stage1, stage2
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
    if not settings.aws_agent_id:
        logger.warning(
            "AWS_AGENT_ID is not set — Bedrock Agent path disabled, "
            "falling back to local LLM."
        )
    else:
        logger.info(
            "Bedrock Agent configured — agent_id=%s  alias_id=%s  region=%s",
            settings.aws_agent_id, settings.aws_agent_alias_id, settings.aws_region,
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


# ─── Health / root ────────────────────────────────────────────────────────────

@app.get("/", tags=["UI"], include_in_schema=False)
async def serve_ui():
    """Serve the frontend so it runs on the same origin as the API (no CORS issues)."""
    ui_file = Path(__file__).parent / "frontend" / "index.html"
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
        "aws_agent_configured": bool(settings.aws_agent_id),
        "aws_s3_configured": bool(settings.s3_config_bucket),
        "storage_writable": _check_storage(),
    }
    status = "healthy" if all(checks.values()) else "degraded"
    return {"status": status, "checks": checks}


@app.get("/health/bedrock", tags=["Health"])
async def health_bedrock():
    """Show loaded Bedrock config and verify the agent + alias exist in AWS."""
    config = {
        "aws_agent_id": settings.aws_agent_id or "(not set)",
        "aws_agent_alias_id": settings.aws_agent_alias_id or "(not set)",
        "aws_region": settings.aws_region,
        "bedrock_model_id": settings.bedrock_model_id,
    }
    if not settings.aws_agent_id or not settings.aws_agent_alias_id:
        return {**config, "agent_check": "skipped — not configured"}
    try:
        import boto3
        client = boto3.client(
            "bedrock-agent",
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id or None,
            aws_secret_access_key=settings.aws_secret_access_key or None,
        )
        agent_resp = client.get_agent(agentId=settings.aws_agent_id)
        alias_resp = client.get_agent_alias(
            agentId=settings.aws_agent_id,
            agentAliasId=settings.aws_agent_alias_id,
        )
        agent_status = agent_resp["agent"]["agentStatus"]
        alias_name   = alias_resp["agentAlias"]["agentAliasName"]
        alias_status = alias_resp["agentAlias"]["agentAliasStatus"]
        routing      = alias_resp["agentAlias"].get("routingConfiguration", [])
        version      = routing[0].get("agentVersion", "?") if routing else "?"
        return {
            **config,
            "agent_check": "ok",
            "agent_status": agent_status,
            "alias_name": alias_name,
            "alias_status": alias_status,
            "alias_points_to_version": version,
        }
    except Exception as exc:
        return {**config, "agent_check": "error", "detail": str(exc)}


@app.get("/health/lambda/{session_id}", tags=["Health"])
async def health_lambda(session_id: str = ""):
    """Test what the action group Lambda actually returns for both Excel files."""
    from services.aws_service import _boto_client
    import json as _json

    results = {}
    try:
        lam = _boto_client("lambda")

        def _invoke(api_path, params):
            payload = {
                "actionGroup": "VaultDocumentFetcher",
                "apiPath": api_path,
                "httpMethod": "GET",
                "parameters": [{"name": k, "value": v} for k, v in params.items()],
            }
            resp = lam.invoke(
                FunctionName="vault_action_groups",
                Payload=_json.dumps(payload).encode(),
            )
            raw = resp["Payload"].read().decode()
            try:
                body = _json.loads(raw)
                inner = body.get("response", {}).get("responseBody", {}).get("application/json", {}).get("body", "{}")
                return _json.loads(inner)
            except Exception:
                return {"raw": raw[:500]}

        results["data_model_doc"] = _invoke("/fetch-data-model-doc", {"session_id": session_id})
        results["config_report"]   = _invoke("/fetch-config-report", {})
        # Show only first 500 chars of content so response is readable
        for k in results:
            if "content" in results[k]:
                results[k]["content_preview"] = results[k].pop("content")[:500]
        return {"status": "ok", "results": results}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@app.get("/health/s3", tags=["Health"])
async def health_s3():
    """Actually connect to S3 and list the vault-reports prefix to verify credentials and bucket access."""
    from services.aws_service import _boto_client, _is_aws_configured

    if not _is_aws_configured():
        return {"status": "skipped", "reason": "S3_CONFIG_BUCKET not set"}

    try:
        s3 = _boto_client("s3")
        bucket = settings.s3_config_bucket
        prefix = settings.s3_vault_reports_prefix

        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix, MaxKeys=5)
        files = [
            {"key": obj["Key"], "last_modified": obj["LastModified"].isoformat(), "size_kb": obj["Size"] // 1024}
            for obj in response.get("Contents", [])
            if obj["Key"].lower().endswith((".xlsx", ".xlsm"))
        ]
        return {
            "status": "ok",
            "bucket": bucket,
            "prefix": prefix,
            "excel_files_found": len(files),
            "latest_files": files,
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


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
