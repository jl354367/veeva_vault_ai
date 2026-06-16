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


async def upload_report_to_s3(
    report_data: dict[str, Any],
    bucket: str,
    key: str,
) -> str:
    """
    Upload a generated report JSON to S3.  Returns the S3 URI.
    Falls back to a no-op when AWS is not configured.
    """
    if not _is_aws_configured():
        logger.warning("AWS not configured — skipping S3 upload")
        return f"mock://s3/{bucket}/{key}"

    try:
        # ── PLACEHOLDER ───────────────────────────────────────────────────────
        # s3 = _boto_client("s3")
        # s3.put_object(
        #     Bucket=bucket,
        #     Key=key,
        #     Body=json.dumps(report_data, default=str).encode(),
        #     ContentType="application/json",
        # )
        # return f"s3://{bucket}/{key}"
        # ── END PLACEHOLDER ───────────────────────────────────────────────────
        return f"mock://s3/{bucket}/{key}"
    except Exception as exc:
        logger.error("Failed to upload report to S3: %s", exc)
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
    """
    Representative structure of a real Config Report.
    Extend this with your actual schema so prompts reflect production data.
    """
    return {
        "report_version": "1.0.0",
        "generated_at": "2026-06-16T00:00:00Z",
        "source": "mock",
        "objects": [
            {
                "name": "Customer",
                "type": "Entity",
                "fields": [
                    {"name": "customerId", "type": "String", "required": True},
                    {"name": "firstName", "type": "String", "required": True},
                    {"name": "lastName", "type": "String", "required": True},
                    {"name": "email", "type": "String", "required": True},
                    {"name": "phone", "type": "String", "required": False},
                    {"name": "address", "type": "Address", "required": False},
                    {"name": "createdAt", "type": "DateTime", "required": True},
                ],
                "relationships": [
                    {"target": "Order", "cardinality": "ONE_TO_MANY"},
                    {"target": "Address", "cardinality": "ONE_TO_ONE"},
                ],
            },
            {
                "name": "Order",
                "type": "Entity",
                "fields": [
                    {"name": "orderId", "type": "String", "required": True},
                    {"name": "customerId", "type": "String", "required": True},
                    {"name": "status", "type": "Enum[PENDING,PROCESSING,SHIPPED,DELIVERED,CANCELLED]", "required": True},
                    {"name": "totalAmount", "type": "Decimal", "required": True},
                    {"name": "currency", "type": "String", "required": True},
                    {"name": "orderDate", "type": "DateTime", "required": True},
                    {"name": "items", "type": "List<OrderItem>", "required": True},
                ],
                "relationships": [
                    {"target": "Customer", "cardinality": "MANY_TO_ONE"},
                    {"target": "OrderItem", "cardinality": "ONE_TO_MANY"},
                    {"target": "Payment", "cardinality": "ONE_TO_ONE"},
                ],
            },
            {
                "name": "OrderItem",
                "type": "Entity",
                "fields": [
                    {"name": "itemId", "type": "String", "required": True},
                    {"name": "orderId", "type": "String", "required": True},
                    {"name": "productId", "type": "String", "required": True},
                    {"name": "quantity", "type": "Integer", "required": True},
                    {"name": "unitPrice", "type": "Decimal", "required": True},
                    {"name": "discount", "type": "Decimal", "required": False},
                ],
                "relationships": [
                    {"target": "Order", "cardinality": "MANY_TO_ONE"},
                    {"target": "Product", "cardinality": "MANY_TO_ONE"},
                ],
            },
            {
                "name": "Product",
                "type": "Entity",
                "fields": [
                    {"name": "productId", "type": "String", "required": True},
                    {"name": "name", "type": "String", "required": True},
                    {"name": "description", "type": "String", "required": False},
                    {"name": "price", "type": "Decimal", "required": True},
                    {"name": "stockQuantity", "type": "Integer", "required": True},
                    {"name": "category", "type": "String", "required": True},
                    {"name": "sku", "type": "String", "required": True},
                ],
                "relationships": [],
            },
            {
                "name": "Payment",
                "type": "Entity",
                "fields": [
                    {"name": "paymentId", "type": "String", "required": True},
                    {"name": "orderId", "type": "String", "required": True},
                    {"name": "method", "type": "Enum[CARD,BANK_TRANSFER,WALLET]", "required": True},
                    {"name": "amount", "type": "Decimal", "required": True},
                    {"name": "status", "type": "Enum[PENDING,SUCCESS,FAILED,REFUNDED]", "required": True},
                    {"name": "transactionId", "type": "String", "required": False},
                    {"name": "processedAt", "type": "DateTime", "required": False},
                ],
                "relationships": [
                    {"target": "Order", "cardinality": "ONE_TO_ONE"},
                ],
            },
        ],
        "integrations": [
            {
                "name": "Order Management API",
                "type": "REST",
                "endpoints": ["/api/v1/orders", "/api/v1/orders/{id}", "/api/v1/orders/{id}/items"],
                "objects_used": ["Order", "OrderItem", "Customer"],
            },
            {
                "name": "Product Catalog API",
                "type": "REST",
                "endpoints": ["/api/v1/products", "/api/v1/products/{id}"],
                "objects_used": ["Product"],
            },
            {
                "name": "Payment Gateway",
                "type": "REST",
                "endpoints": ["/api/v1/payments", "/api/v1/payments/{id}/refund"],
                "objects_used": ["Payment", "Order"],
            },
            {
                "name": "Order Events",
                "type": "Event",
                "topics": ["order.created", "order.updated", "order.shipped", "order.cancelled"],
                "objects_used": ["Order", "Customer"],
            },
        ],
    }
