"""
AWS integration layer.

Fetches the latest Vault Configuration Report Excel from S3 and provides a
thin pass-through to the Bedrock Agent.  The agent (Claude 3 Sonnet) handles
intent recognition, tool orchestration, and output format on its own — this
module simply forwards the user's message and returns the raw response.
"""

from __future__ import annotations

import io
import json
import logging
import re
from typing import Any

from config import settings

logger = logging.getLogger(__name__)


# ─── helpers ──────────────────────────────────────────────────────────────────

def _boto_client(service: str):
    """Return a boto3 client; import is deferred so the app starts without AWS creds."""
    import boto3
    from botocore.config import Config
    # Bedrock Agent responses (with action groups) can take 2-3 minutes
    timeout_config = Config(read_timeout=300, connect_timeout=10, retries={"max_attempts": 0})
    kwargs: dict[str, Any] = {"region_name": settings.aws_region, "config": timeout_config}
    if settings.aws_access_key_id:
        kwargs["aws_access_key_id"] = settings.aws_access_key_id
        kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
    return boto3.client(service, **kwargs)


def _is_aws_configured() -> bool:
    return bool(settings.s3_config_bucket and settings.aws_region)


# ─── Excel parser ─────────────────────────────────────────────────────────────

def _parse_excel_to_text(excel_bytes: bytes) -> str:
    """Convert Excel bytes to plain text (all sheets concatenated)."""
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(excel_bytes), read_only=True, data_only=True)
    parts: list[str] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        parts.append(f"=== Sheet: {sheet_name} ===")
        for row in ws.iter_rows(values_only=True):
            cells = [str(c) if c is not None else "" for c in row]
            if any(cells):
                parts.append(" | ".join(cells))
    wb.close()
    return "\n".join(parts)


# ─── S3 ───────────────────────────────────────────────────────────────────────

async def fetch_config_report_from_s3(
    bucket: str | None = None,
    key: str | None = None,
) -> dict[str, Any]:
    """Download the latest Vault Configuration Report Excel from S3."""
    bucket = bucket or settings.s3_config_bucket
    prefix = settings.s3_vault_reports_prefix

    if not _is_aws_configured():
        logger.warning("AWS not configured — returning mock config report")
        return _mock_config_report()

    try:
        s3 = _boto_client("s3")
        response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        contents = response.get("Contents", [])
        excel_files = [
            obj for obj in contents
            if obj["Key"].lower().endswith((".xlsx", ".xlsm"))
        ]
        if not excel_files:
            logger.warning(
                "No Excel files found at s3://%s/%s — returning mock config report",
                bucket, prefix,
            )
            return _mock_config_report()
        latest = max(excel_files, key=lambda o: o["LastModified"])
        s3_key = latest["Key"]
        logger.info("Fetching latest config report: s3://%s/%s", bucket, s3_key)
        obj = s3.get_object(Bucket=bucket, Key=s3_key)
        excel_bytes = obj["Body"].read()
        report_text = _parse_excel_to_text(excel_bytes)
        logger.info("Parsed config report — %d chars from s3://%s/%s", len(report_text), bucket, s3_key)
        return {
            "source": "s3",
            "s3_key": s3_key,
            "report_text": report_text,
            "objects": [],
            "integrations": [],
        }
    except Exception as exc:
        logger.error("Failed to fetch config report from S3: %s", exc)
        raise


async def upload_document_to_s3(
    content: bytes,
    session_id: str,
    filename: str,
) -> str | None:
    """Upload a user-submitted document to the uploads bucket."""
    bucket = settings.s3_uploads_bucket
    if not bucket:
        logger.warning("S3_UPLOADS_BUCKET not configured — skipping document upload")
        return None
    import mimetypes
    s3_key = f"{settings.s3_uploads_prefix}{session_id}/{filename}"
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    s3 = _boto_client("s3")
    s3.put_object(Bucket=bucket, Key=s3_key, Body=content, ContentType=content_type)
    uri = f"s3://{bucket}/{s3_key}"
    logger.info("Uploaded document to %s", uri)
    return uri


# ─── Bedrock Agent invocation ────────────────────────────────────────────────

# ─── Scope detection ─────────────────────────────────────────────────────────
# Map a phrase that may appear in the user message → human-readable scope
# description that we append as a hint to the agent. Kept narrow so chat-mode
# pass-through behavior is preserved when no scope keyword is present.
_SCOPE_PHRASES: tuple[tuple[str, str], ...] = (
    ("objects and fields", "objects and fields"),
    ("fields and objects", "objects and fields"),
    ("objects only", "objects"),
    ("just objects", "objects"),
    ("only objects", "objects"),
    ("fields only", "fields"),
    ("just fields", "fields"),
    ("only fields", "fields"),
    ("workflows only", "workflows"),
    ("just workflows", "workflows"),
    ("only workflows", "workflows"),
    ("integrations only", "integrations"),
    ("just integrations", "integrations"),
    ("only integrations", "integrations"),
    ("layouts only", "layouts"),
    ("just layouts", "layouts"),
    ("only layouts", "layouts"),
    ("picklists only", "picklists"),
    ("just picklists", "picklists"),
    ("only picklists", "picklists"),
    ("reports only", "reports"),
    ("just reports", "reports"),
    ("only reports", "reports"),
    ("sdk jobs only", "SDK jobs"),
    ("just sdk", "SDK jobs"),
    ("only sdk", "SDK jobs"),
    ("lifecycles only", "lifecycles"),
    ("validation only", "validation rules"),
    ("security only", "security and roles"),
)


def _detect_scope_hint(message: str) -> str | None:
    """
    Return a short scope description if the user's message asks for a
    specific subset of components (e.g. "objects and fields"), else None.

    Catches three families of phrasings:
      1. Explicit phrases from _SCOPE_PHRASES (e.g. "workflows only").
      2. "objects AND fields" / "fields AND objects".
      3. "(list|share|give|show) ... CATEGORY" where CATEGORY is one of
         objects/fields/workflows/integrations/layouts/picklists/reports/
         SDK jobs/lifecycles/validation rules/security — and the word is
         NOT followed by " and " (so combo asks fall through to #2).
      4. "common CATEGORY" — e.g. "common objects".
    """
    import re as _re
    low = message.lower()

    # 1) Direct phrase matches first
    for phrase, scope_desc in _SCOPE_PHRASES:
        if phrase in low:
            return scope_desc

    # 2) "objects AND fields" patterns — both categories at once
    if _re.search(
        r'(which|what|list|show|give\s+me|share|provide)\s+(?:the\s+)?(?:list\s+of\s+)?(?:common\s+)?objects?\s+and\s+fields?',
        low,
    ):
        return "objects and fields"
    if _re.search(
        r'(which|what|list|show|give\s+me|share|provide)\s+(?:the\s+)?(?:list\s+of\s+)?(?:common\s+)?fields?\s+and\s+objects?',
        low,
    ):
        return "objects and fields"

    # Reusable building blocks for the broader patterns below
    _action = r'(?:list|share|give|show|provide|tell\s+me)'
    _optional_prefix = (
        r'(?:\s+me)?'                        # "list me"
        r'(?:\s+(?:me\s+)?the)?'             # "list the", "list me the"
        r'(?:\s+(?:a\s+)?list\s+of)?'        # "list of"
        r'(?:\s+(?:all|common|every|only))?' # "all", "common", "every", "only"
        r'(?:\s+the)?'                       # extra "the"
    )

    _categories = (
        (r'objects?',                'objects'),
        (r'fields?',                 'fields'),
        (r'workflows?',              'workflows'),
        (r'lifecycles?',             'lifecycles'),
        (r'integrations?',           'integrations'),
        (r'(?:page\s+)?layouts?',    'layouts'),
        (r'picklists?',              'picklists'),
        (r'reports?',                'reports'),
        (r'sdk(?:\s+jobs?)?',        'SDK jobs'),
        (r'validation(?:\s+rules?)?','validation rules'),
        (r'security(?:\s+settings?)?','security and roles'),
    )

    # 3) "(list|share|give|show) ... CATEGORY" — singular scope
    for cat_re, scope_desc in _categories:
        pattern = _action + _optional_prefix + r'\s+' + cat_re + r'\b(?!\s+and\s+)'
        if _re.search(pattern, low):
            return scope_desc

    # 4) "common CATEGORY" anywhere — e.g. "what are the common objects?"
    for cat_re, scope_desc in _categories:
        if _re.search(r'\bcommon\s+' + cat_re + r'\b(?!\s+and\s+)', low):
            return scope_desc

    return None


async def invoke_agent(
    session_id: str,
    user_message: str,
    bedrock_session_id: str | None = None,
) -> dict[str, Any]:
    """
    Invoke the Bedrock Agent with the user's raw message.

    The agent (Claude) handles intent recognition, tool calls, and output
    format itself. The bedrock_session_id is reused across turns so the
    agent retains conversation memory and doesn't re-fetch documents.

    Returns:
        {
          "status":              "ok" | "error" | "not_configured",
          "response":            <raw text from agent in whatever format Claude chose>,
          "bedrock_session_id":  <session id to pass on next turn>,
          "error":               <error string when status == error>,
        }
    """
    if not settings.aws_agent_id:
        return {
            "status": "not_configured",
            "response": "Bedrock Agent is not configured. Set AWS_AGENT_ID and AWS_AGENT_ALIAS_ID in .env.",
        }

    import uuid as _uuid
    bedrock = _boto_client("bedrock-agent-runtime")
    bedrock_session_id = bedrock_session_id or str(_uuid.uuid4())

    # Send the user's message verbatim — same as the AWS Bedrock console
    # does. The only nudge we add is an emphatic SCOPE hint when the user
    # asks for a narrow subset (e.g. "objects only", "workflows only",
    # "common objects", "share the fields"); Nova Pro otherwise drifts
    # into listing every category in the report.
    scope_hint = _detect_scope_hint(user_message)
    if scope_hint:
        # All categories — used to spell out what NOT to include.
        all_cats = {
            "objects", "fields", "workflows", "lifecycles", "integrations",
            "layouts", "picklists", "reports", "SDK jobs",
            "validation rules", "security and roles",
        }
        excluded = sorted(
            c for c in all_cats
            if c.lower() not in scope_hint.lower()
        )
        input_text = (
            f"{user_message}\n\n"
            f"IMPORTANT — STRICT SCOPE: the user is asking for {scope_hint} ONLY. "
            f"Your response MUST contain ONLY {scope_hint}. "
            f"Do NOT include any of these other categories: "
            f"{', '.join(excluded)}. "
            f"If you start writing a section header for one of those, "
            f"stop immediately and remove it."
        )
    else:
        input_text = user_message

    logger.info(
        "Invoking Bedrock Agent agentId=%s aliasId=%s session=%s",
        settings.aws_agent_id, settings.aws_agent_alias_id, bedrock_session_id,
    )

    try:
        response = bedrock.invoke_agent(
            agentId=settings.aws_agent_id,
            agentAliasId=settings.aws_agent_alias_id,
            sessionId=bedrock_session_id,
            inputText=input_text,
        )
        agent_text = _collect_bedrock_stream(response)
        logger.info("Agent responded — %d chars", len(agent_text))
        return {
            "status": "ok",
            "response": agent_text,
            "bedrock_session_id": bedrock_session_id,
        }
    except Exception as exc:
        logger.error("Bedrock Agent invocation failed: %s", exc)
        return {
            "status": "error",
            "response": f"Sorry, I hit an error talking to the agent: {exc}",
            "error": str(exc),
            "bedrock_session_id": bedrock_session_id,
        }


async def invoke_agent_broad(
    session_id: str,
    user_message: str,
    bedrock_session_id: str | None = None,
) -> dict[str, Any]:
    """
    For broad queries that exceed Nova Pro's output token limit, split the
    request into 3 scoped calls and merge the resulting impacted_objects.

    Each scoped call returns a short enough response to fit in the token
    budget, then we deduplicate by (object_name, change_type, field_name)
    and merge the impacted_areas arrays.
    """
    scopes = [
        "workflows and lifecycle impacts only",
        "integrations and api impacts only",
        "objects fields page layouts security validation rules reports templates only",
    ]

    merged: dict[tuple, dict] = {}
    # Use a FRESH Bedrock session for each scoped call. If we reused the
    # parent session, the agent could carry over prose/table mode from
    # earlier conversation turns and return non-JSON answers, causing the
    # merge to fail. Each scoped call must start clean so the instruction's
    # JSON output contract applies.
    final_bedrock_sid = bedrock_session_id

    for scope in scopes:
        logger.info("Broad query — scoped call: %s", scope)
        result = await invoke_agent(
            session_id=session_id,
            user_message=scope,
            bedrock_session_id=None,  # fresh session per scoped call
        )
        # Track only the LAST scoped session id so follow-up turns can resume
        # if the user wants to continue from the merged report context.
        final_bedrock_sid = result.get("bedrock_session_id", final_bedrock_sid)

        structured = try_extract_report_json(result.get("response", ""))
        if not structured:
            logger.warning("Scoped call '%s' returned no parseable JSON", scope)
            continue

        for obj in structured.get("impacted_objects", []):
            key = (
                (obj.get("object_name") or "").lower(),
                (obj.get("change_type") or "").lower(),
                (obj.get("field_name") or "").lower(),
            )
            if key not in merged:
                merged[key] = dict(obj)
                merged[key].setdefault("impacted_areas", [])
            else:
                existing = merged[key].setdefault("impacted_areas", [])
                seen = {a.get("area_name", "").lower() for a in existing}
                for area in obj.get("impacted_areas", []):
                    if area.get("area_name", "").lower() not in seen:
                        existing.append(area)
                        seen.add(area.get("area_name", "").lower())

    all_objects = list(merged.values())
    if not all_objects:
        return {
            "status": "ok",
            "response": (
                "I couldn't extract impacted objects from any of the scoped queries. "
                "Try asking for a specific area — e.g., \"workflow impacts only\"."
            ),
            "bedrock_session_id": final_bedrock_sid,
        }

    total_areas = sum(len(o.get("impacted_areas", [])) for o in all_objects)
    combined = {
        "session_id": session_id,
        "summary": {
            "total_changes": len(all_objects),
            "total_impacted_areas": total_areas,
        },
        "impacted_objects": all_objects,
    }

    prose = (
        f"Analysis complete — found {len(all_objects)} changes affecting "
        f"{total_areas} configuration areas (aggregated from 3 scoped queries)."
    )
    return {
        "status": "ok",
        "response": f"{prose}\n\n{json.dumps(combined, ensure_ascii=False)}",
        "bedrock_session_id": final_bedrock_sid,
    }


def try_extract_report_json(text: str) -> dict[str, Any] | None:
    """
    Best-effort extraction of a Vault impact report JSON from the agent's
    response. Returns None if no valid impacted_objects JSON is found.

    The agent may respond in prose, table, or JSON. When it includes a JSON
    block (because the user asked for an export or by default), we extract
    it here so the frontend can render the structured report panel.
    """
    if not text or "impacted_objects" not in text:
        return None
    result = _parse_agent_json(text)
    if result:
        result = _normalize_to_new_schema(result)
    return result


def _normalize_to_new_schema(report: dict) -> dict:
    """
    Convert old-shape agent response to new shape if needed.
    Handles the case where the agent returns legacy keys
    (impacted_fields, severity, recommendations) instead of the
    new schema (impacted_areas, risk, recommendation).
    """
    if not isinstance(report, dict):
        return report

    for obj in report.get("impacted_objects", []) or []:
        # If already new shape with populated areas, skip
        if obj.get("impacted_areas"):
            continue

        areas = []
        old_fields = obj.get("impacted_fields", []) or []

        for f in old_fields:
            risk = (f.get("severity") or obj.get("overall_severity") or "MEDIUM").upper()
            old_def = f.get("old_definition", "") or ""
            new_def = f.get("new_definition", "") or ""
            change_desc = f.get("change_type", "") or ""
            desc = f.get("notes") or f"{change_desc}: {old_def} → {new_def}".strip(": → ")

            recs = obj.get("recommendations", []) or []
            recommendation = "; ".join(recs) if recs else "Review impacted field."

            areas.append({
                "area_type": "field",
                "area_name": f.get("field_name", ""),
                "description": desc,
                "risk": risk,
                "recommendation": recommendation,
            })

        # Old-shape integrations
        for i in (obj.get("impacted_integrations", []) or []):
            recs = obj.get("recommendations", []) or []
            areas.append({
                "area_type": "integration",
                "area_name": i.get("integration_name", ""),
                "description": i.get("notes") or f"Integration impact on {i.get('integration_name', '')}",
                "risk": (i.get("severity") or obj.get("overall_severity") or "MEDIUM").upper(),
                "recommendation": "; ".join(recs) if recs else "Review impacted integration.",
            })

        # No impacted_fields/integrations but object-level description exists →
        # create one area from object-level info
        if not areas and obj.get("description"):
            recs = obj.get("recommendations", []) or []
            areas.append({
                "area_type": obj.get("object_type", "other"),
                "area_name": obj.get("object_name", ""),
                "description": obj.get("description", ""),
                "risk": (obj.get("overall_severity") or "MEDIUM").upper(),
                "recommendation": "; ".join(recs) if recs else "Review change.",
            })

        obj["impacted_areas"] = areas

        # Promote first impacted_field to top-level field_name
        if old_fields and not obj.get("field_name"):
            obj["field_name"] = old_fields[0].get("field_name", "")
            obj["change_type"] = obj.get("change_type") or old_fields[0].get("change_type", "")

    return report


# ─── Streaming + JSON extraction helpers ─────────────────────────────────────

def _collect_bedrock_stream(response: dict) -> str:
    """Read all chunks from a Bedrock Agent streaming response into one string."""
    chunks = []
    for event in response.get("completion", []):
        chunk = event.get("chunk", {})
        if "bytes" in chunk:
            chunks.append(chunk["bytes"].decode("utf-8"))
    return "".join(chunks)


def _parse_agent_json(text: str) -> dict[str, Any] | None:
    """
    Extract JSON from agent response. Handles:
      - Prose preamble before JSON
      - Markdown code fences (```json ... ```)
      - Truncated JSON (token-limit truncation)
      - Trailing text after JSON
      - Legacy keys (normalised back to the new schema)
    """
    if not text or "impacted_objects" not in text:
        return None

    # Strip markdown code fences (Nova Pro sometimes wraps JSON in them)
    cleaned = re.sub(r'```(?:json)?\s*', '', text)
    cleaned = cleaned.replace('```', '')

    # Find the JSON object using bracket-depth tracking
    for m in re.finditer(r'\{\s*"', cleaned):
        start = m.start()
        depth = 0
        in_str = False
        esc = False
        end = -1
        for i in range(start, len(cleaned)):
            c = cleaned[i]
            if esc:
                esc = False
                continue
            if c == '\\' and in_str:
                esc = True
                continue
            if c == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if c == '{':
                depth += 1
            elif c == '}':
                depth -= 1
                if depth == 0:
                    end = i
                    break

        candidate = cleaned[start:end + 1] if end != -1 else cleaned[start:]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict) and "impacted_objects" in parsed:
                return _normalize_to_new_schema(parsed)
        except json.JSONDecodeError:
            repaired = _repair_truncated_json(candidate)
            if repaired and "impacted_objects" in repaired:
                return _normalize_to_new_schema(repaired)
            continue

    return None


def _repair_truncated_json(text: str) -> dict[str, Any] | None:
    """
    Repair JSON that was truncated at a token limit by auto-closing any
    open strings, arrays, and objects. Best-effort — returns None if even
    the patched text won't parse.
    """
    text = text.rstrip()

    # If we ended mid-string, close it
    quote_count = 0
    for i, c in enumerate(text):
        if c == '"' and (i == 0 or text[i-1] != '\\'):
            quote_count += 1
    if quote_count % 2 != 0:
        text += '"'

    # Remove trailing comma or partial value
    text = re.sub(r',\s*$', '', text)
    text = re.sub(r':\s*$', ': null', text)

    # Count open vs close brackets and close them
    open_curly = text.count('{') - text.count('}')
    open_square = text.count('[') - text.count(']')
    text += ']' * max(open_square, 0)
    text += '}' * max(open_curly, 0)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _extract_nested_dict(text: str, key: str) -> dict[str, Any] | None:
    """Extract the first JSON object for a given key from a text fragment."""
    pos = text.find(key)
    if pos == -1:
        return None
    brace = text.find("{", pos)
    if brace == -1:
        return None
    try:
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(text, brace)
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


# ─── Mock data (used when AWS is not configured) ──────────────────────────────

def _mock_config_report() -> dict[str, Any]:
    return {"source": "mock", "objects": [], "integrations": []}
