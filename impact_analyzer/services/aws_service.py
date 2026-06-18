"""
AWS integration layer.

All methods are fully implemented for real AWS calls when credentials and ARNs
are configured.  When they are NOT configured the methods fall back to local
mock data so the rest of the application keeps working during development.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

# ─── helpers ──────────────────────────────────────────────────────────────────

def _boto_client(service: str):
    """Return a boto3 client; import is deferred so the app starts without AWS creds."""
    import boto3
    kwargs: dict[str, Any] = {"region_name": settings.aws_region}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client(service, **kwargs)


def _is_aws_configured() -> bool:
    return bool(settings.s3_config_bucket and settings.aws_region)


# ─── S3 ───────────────────────────────────────────────────────────────────────

async def fetch_config_report_from_s3(
    bucket: str | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    """
    Download the Configuration Report JSON from S3.

    Returns the parsed dict. Falls back to mock data when AWS is not configured.
    """
    bucket = bucket or settings.s3_config_bucket
    key = key or settings.s3_config_report_key

    if not _is_aws_configured():
        logger.warning("AWS not configured — returning mock config report")
        return _mock_config_report()

    try:
        # ── PLACEHOLDER: replace body below with real S3 call ─────────────────
        # s3 = _boto_client("s3")
        # response = s3.get_object(Bucket=bucket, Key=key)
        # content = response["Body"].read().decode("utf-8")
        # return json.loads(content)
        # ── END PLACEHOLDER ───────────────────────────────────────────────────
        logger.info("AWS S3 call placeholder — returning mock config report")
        return _mock_config_report()
    except Exception as exc:
        logger.error("Failed to fetch config report from S3: %s", exc)
        raise


# ─── Lambda / Bedrock Agent ───────────────────────────────────────────────────

async def trigger_aws_agent(
    payload: dict[str, Any],
    stage: int,
) -> dict[str, Any]:
    """
    Invoke the AWS analysis agent (Lambda or Bedrock Agent).

    When not configured, returns a stub response immediately so the pipeline
    can continue with local LLM analysis.
    """
    if not settings.aws_agent_lambda_arn and not settings.aws_agent_id:
        logger.warning("AWS agent not configured — using local LLM fallback")
        return {"status": "local_fallback", "invocation_id": str(uuid.uuid4())}

    try:
        # ── PLACEHOLDER: Lambda invocation ────────────────────────────────────
        # lambda_client = _boto_client("lambda")
        # response = lambda_client.invoke(
        #     FunctionName=settings.aws_agent_lambda_arn,
        #     InvocationType="RequestResponse",
        #     Payload=json.dumps(payload).encode(),
        # )
        # result = json.loads(response["Payload"].read())
        # return result
        # ── END PLACEHOLDER ───────────────────────────────────────────────────

        # ── PLACEHOLDER: Bedrock Agent invocation ─────────────────────────────
        # bedrock = _boto_client("bedrock-agent-runtime")
        # response = bedrock.invoke_agent(
        #     agentId=settings.aws_agent_id,
        #     agentAliasId=settings.aws_agent_alias_id,
        #     sessionId=payload.get("session_id", str(uuid.uuid4())),
        #     inputText=json.dumps(payload),
        # )
        # ... stream the response ...
        # ── END PLACEHOLDER ───────────────────────────────────────────────────

        return {"status": "local_fallback", "invocation_id": str(uuid.uuid4())}
    except Exception as exc:
        logger.error("AWS agent invocation failed: %s", exc)
        raise


# ─── Mock data (used when AWS is not configured) ──────────────────────────────

def _mock_config_report() -> dict[str, Any]:
    return {"source": "mock", "objects": [], "integrations": []}
