"""
Stage 1 router.

Endpoints:
  POST /stage1/upload          – upload Data Model Changes Document
  POST /stage1/run             – trigger analysis (synchronous)
  POST /stage1/chat            – conversational chat with the Bedrock Agent
  GET  /stage1/status/{sid}    – lightweight status poll
  GET  /stage1/report/{sid}    – fetch the completed report
"""

from __future__ import annotations

import asyncio
import json
import logging
import re

from fastapi import APIRouter, HTTPException, UploadFile, File, Form

from models.schemas import (
    AnalysisStatus,
    Stage1Report,
    Stage1RunResponse,
)
from services import analysis_service
from services.analysis_service import _build_metadata, _build_summary, _build_impacted_objects
from services.aws_service import upload_document_to_s3
from utils.file_utils import save_upload, validate_upload

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/stage1", tags=["Stage 1 — Data Model Impact"])


# ─── Upload ───────────────────────────────────────────────────────────────────

@router.post("/upload", summary="Upload Data Model Changes Document")
async def upload_data_model_doc(
    file: UploadFile = File(..., description="PDF, DOCX, or TXT document"),
    session_id: str | None = Form(None, description="Reuse an existing session"),
):
    """
    Upload the Data Model Changes Document.

    - Creates a new session if `session_id` is not provided.
    - Returns the `session_id` to be used in subsequent calls.
    """
    content = await file.read()

    try:
        validate_upload(file.filename or "upload", len(content))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not session_id:
        session_id = analysis_service.create_session()

    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        session_id = analysis_service.create_session()
        session = analysis_service.get_session(session_id)

    file_path = save_upload(session_id, "data_model_doc", file.filename or "upload", content)
    session.uploaded_files["data_model_doc"] = file_path
    session.metadata["data_model_doc_name"] = file.filename or "upload"

    s3_uri: str | None = None
    try:
        s3_uri = await upload_document_to_s3(content, session_id, file.filename or "upload")
        if s3_uri:
            session.metadata["data_model_doc_s3_uri"] = s3_uri
    except Exception as exc:
        logger.warning("S3 upload failed (local copy still saved): %s", exc)

    return {
        "session_id": session_id,
        "filename": file.filename,
        "size_bytes": len(content),
        "s3_uri": s3_uri,
        "message": "Data model document uploaded successfully.",
    }


# ─── Run (synchronous full analysis) ──────────────────────────────────────────

@router.post("/run", response_model=Stage1RunResponse, summary="Run Stage 1 Analysis")
async def run_stage1(
    session_id: str = Form(..., description="session_id from /stage1/upload"),
):
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if "data_model_doc" not in session.uploaded_files:
        raise HTTPException(
            status_code=400,
            detail="No data model document in session. Call /stage1/upload first.",
        )

    existing = session.stage1_report
    if existing and existing.status == AnalysisStatus.RUNNING:
        return Stage1RunResponse(
            session_id=session_id,
            status=AnalysisStatus.RUNNING,
            message="Analysis already in progress.",
        )

    try:
        report = await analysis_service.run_stage1(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        logger.error("Stage 1 pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {exc}")

    return Stage1RunResponse(
        session_id=session_id,
        status=report.status,
        message="Stage 1 analysis completed successfully.",
        report=report,
    )


# ─── Status ───────────────────────────────────────────────────────────────────

@router.get("/status/{session_id}", summary="Poll Stage 1 Analysis Status")
async def get_stage1_status(session_id: str):
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    report = session.stage1_report
    if not report:
        return {"session_id": session_id, "status": "not_started"}

    return {
        "session_id": session_id,
        "status": report.status,
        "created_at": report.created_at,
        "error": report.error,
    }


# Pure greetings — handled directly in the backend so the agent isn't tempted
# to launch a full analysis just because a session_id is in the context.
# Kept intentionally tiny — anything else still goes to the agent.
_GREETINGS = {
    "hi", "hello", "hey", "howdy", "yo",
    "good morning", "good afternoon", "good evening",
    "thanks", "thank you", "thx", "ty",
}


def _is_pure_greeting(message: str) -> bool:
    return message.strip().lower().rstrip("!.?") in _GREETINGS


def _enforce_scope(text: str, user_message: str) -> str:
    """
    Post-process safety net: if the user asked for a specific category
    (e.g. "objects only") but the agent included other category sections
    in its response, strip the extra sections.

    Operates on Markdown/prose where category headers look like:
      Objects:
      Fields:
      Workflows:
      ## Objects
      **Fields**

    Conservative — only fires when (a) we can identify the requested
    scope from the user's message, and (b) the response actually has
    multiple category headers. Tables, JSON, and short answers are
    left alone.
    """
    if not text or len(text) < 100:
        return text

    # Reuse the same scope detection as the backend → keeps behavior aligned
    from services.aws_service import _detect_scope_hint  # local import to avoid circular
    scope = _detect_scope_hint(user_message)
    if not scope:
        return text

    # Map scope description → set of acceptable category header keywords
    scope_to_keep: dict[str, set[str]] = {
        "objects": {"object", "objects"},
        "fields": {"field", "fields"},
        "workflows": {"workflow", "workflows"},
        "lifecycles": {"lifecycle", "lifecycles"},
        "integrations": {"integration", "integrations", "integration rule", "integration rules"},
        "layouts": {"layout", "layouts", "page layout", "page layouts"},
        "picklists": {"picklist", "picklists"},
        "reports": {"report", "reports"},
        "SDK jobs": {"sdk", "sdk job", "sdk jobs"},
        "validation rules": {"validation", "validation rule", "validation rules"},
        "security and roles": {"security", "role", "roles", "permission", "permissions"},
        "objects and fields": {"object", "objects", "field", "fields"},
    }
    keep = scope_to_keep.get(scope)
    if not keep:
        return text

    # All known category headers (lowercased) — for detecting drift
    all_categories = {
        "object", "objects", "field", "fields", "workflow", "workflows",
        "lifecycle", "lifecycles", "integration", "integrations",
        "integration rule", "integration rules", "layout", "layouts",
        "page layout", "page layouts", "picklist", "picklists",
        "report", "reports", "sdk", "sdk job", "sdk jobs",
        "validation", "validation rule", "validation rules",
        "security", "role", "roles", "permission", "permissions",
    }

    def _header_keyword(line: str) -> str | None:
        """Return the canonical category keyword if the line is a header, else None."""
        s = line.strip()
        if not s:
            return None
        # Strip common header decoration: **, ##, leading bullets, trailing :
        s = re.sub(r'^[#\-*]+\s*', '', s)
        s = re.sub(r'\*+', '', s)
        s = s.rstrip(":").rstrip().lower()
        if s in all_categories:
            return s
        return None

    lines = text.split("\n")
    # Locate header lines + their indices
    header_indices: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        kw = _header_keyword(line)
        if kw:
            header_indices.append((i, kw))

    # Only enforce when there are 2+ section headers (multi-category response)
    if len(header_indices) < 2:
        return text

    # Walk sections and drop those whose header isn't in `keep`
    kept_lines: list[str] = []
    cut_count = 0
    for idx, (line_idx, kw) in enumerate(header_indices):
        next_idx = header_indices[idx + 1][0] if idx + 1 < len(header_indices) else len(lines)
        if kw in keep:
            kept_lines.extend(lines[line_idx:next_idx])
        else:
            cut_count += 1

    # Preserve any preamble before the first header
    preamble_end = header_indices[0][0]
    preamble = lines[:preamble_end]
    result = "\n".join(preamble + kept_lines).rstrip()

    if cut_count > 0:
        logger.info("Scope enforcement: stripped %d out-of-scope section(s)", cut_count)

    return result if result else text


def _ensure_intro_line(text: str, user_message: str) -> str:
    """
    If a chat-mode response starts directly with a table or column-header
    row (no conversational intro), prepend a short context sentence based
    on what the user asked. Matches the AWS console's behavior where the
    agent typically writes an intro line before a table.
    """
    if not text:
        return text
    stripped = text.lstrip()
    if not stripped:
        return text

    # Detect response that starts with a markdown table or a header row
    first_line = stripped.split("\n", 1)[0].strip()
    starts_with_table = (
        first_line.startswith("|")
        or (first_line.count("\t") >= 2)
        or bool(re.match(r'^[A-Z][\w /]+\s*\|', first_line))
        or bool(re.match(r'^(Object|Object Name|Field|Component|Severity|Category|#)\s+\|', first_line))
    )
    if not starts_with_table:
        return text

    msg_low = user_message.lower()
    if "table" in msg_low or "tabular" in msg_low:
        if "full" in msg_low and ("analysis" in msg_low or "impact" in msg_low):
            intro = "Here is the full impact analysis in tabular form:"
        elif "severity" in msg_low or "critical" in msg_low or "high" in msg_low:
            intro = "Here are the impacts grouped by severity:"
        elif "workflow" in msg_low:
            intro = "Here are the impacted workflows:"
        elif "integration" in msg_low:
            intro = "Here are the impacted integrations:"
        elif "field" in msg_low:
            intro = "Here are the impacted fields:"
        elif "object" in msg_low:
            intro = "Here are the impacted objects:"
        elif "impact" in msg_low or "matched" in msg_low or "components" in msg_low:
            intro = "Here is the impact summary:"
        else:
            intro = "Here is the requested table:"
    else:
        intro = "Here are the results:"

    return f"{intro}\n\n{stripped}"


def _detect_truncated_table(text: str) -> bool:
    """
    Detect that a markdown TABLE was cut off mid-row. Conservative —
    only fires when:
      - A markdown table is present (a header row followed by a `---`
        separator row), AND
      - The LAST line of the response is an incomplete row of that table
        (fewer pipes than the header, no trailing `|`).

    Bullet lists, prose, and lists that happen to end with a Vault API
    name are NOT flagged. Only true mid-row table cut-offs.
    """
    if not text:
        return False
    stripped = text.rstrip()
    if len(stripped) < 200:
        return False

    lines = [l for l in stripped.split("\n") if l.strip()]
    if len(lines) < 4:
        return False

    # Identify the markdown table header: a line with pipes immediately
    # followed by a separator row (---|---|---). Without a true table,
    # we don't flag.
    header_pipes = 0
    for i in range(len(lines) - 1):
        cur, nxt = lines[i], lines[i + 1]
        if cur.count("|") >= 3 and "---" in nxt and "|" in nxt:
            header_pipes = cur.count("|")
            break

    if header_pipes < 3:
        return False  # no real markdown table — don't flag

    last = lines[-1].rstrip()
    last_pipes = last.count("|")
    if last_pipes == 0:
        return False  # last line isn't a table row at all (e.g. closing prose)

    # Pipe-count mismatch with header → row was cut mid-cell
    if last_pipes < header_pipes - 1:
        return True
    if not last.endswith("|") and last_pipes < header_pipes:
        return True

    return False


def _dedupe_agent_response(text: str) -> str:
    """
    Trim duplicate sections from agent responses.

    Nova Pro sometimes lists items, then re-emits the SAME content in a
    different shape (comma-separated, "grouped by category", etc.). This
    helper detects two duplication patterns and trims the redundant tail.

    Conservative — only fires when the response is >200 chars.
    """
    if not text or len(text) < 200:
        return text

    # Pattern 1 — explicit "grouped by category" / "in summary" prefaces
    dedup_markers = (
        "here are the impacted components grouped",
        "here are the matching components grouped",
        "here are the differences grouped",
        "here are the components grouped",
        "here are the affected components grouped",
        "here is the same information",
        "here is the same list",
        "here is the list grouped",
        "to summarize the above",
        "in summary, the impacted",
        "in summary, the matching",
        "in summary, the affected",
    )
    lower = text.lower()
    for marker in dedup_markers:
        idx = lower.find(marker)
        if idx > 200:
            trimmed = text[:idx].rstrip()
            logger.info(
                "Dedup: trimmed %d chars of repeated content (marker: %r)",
                len(text) - len(trimmed), marker,
            )
            return trimmed

    # Pattern 2 — Vault category headers appearing more than once.
    # If "Objects:", "Fields:", "Workflows:", etc. show up a second time,
    # the agent has started re-listing the same data in another shape.
    # Cut at the second occurrence of any category header.
    category_headers = (
        "Objects:", "Fields:", "Workflows:", "Integrations:", "Layouts:",
        "Page Layouts:", "SDK Jobs:", "Picklists:", "Reports:",
        "Integration Rules:", "Object Workflows:", "Object Lifecycles:",
        "Permission Sets:", "Lifecycles:",
    )
    seen: dict[str, int] = {}
    earliest_dup = -1
    for header in category_headers:
        # Find both occurrences of this header (case-sensitive)
        first = text.find(header)
        if first == -1:
            continue
        second = text.find(header, first + len(header))
        if second != -1 and second > 200:
            if earliest_dup == -1 or second < earliest_dup:
                earliest_dup = second

    if earliest_dup != -1:
        trimmed = text[:earliest_dup].rstrip()
        logger.info(
            "Dedup: trimmed %d chars of repeated category-header content",
            len(text) - len(trimmed),
        )
        return trimmed

    return text


def _looks_incomplete(text: str) -> bool:
    """
    Detect a chat-mode response that was cut off mid-content. Common
    Nova Pro failure modes:
      - Ends with a Vault API name (e.g. "...application__v") and no punctuation
      - Ends with a single short orphan line (no sentence terminator)
      - Ends with a trailing comma or colon
    """
    if not text:
        return True
    stripped = text.strip()
    if len(stripped) < 60:
        # Short responses are usually intentional (e.g. one-sentence answers)
        return False
    # Ends in a Vault API name pattern with no following text or punctuation
    if re.search(r'\w+__[vc]\s*$', stripped):
        return True
    # Ends with a trailing punctuation that signals more content was coming
    if stripped[-1] in ',:':
        return True
    # Last line is short and has no terminating punctuation
    last_line = stripped.split('\n')[-1].strip()
    if 0 < len(last_line) < 80 and last_line[-1] not in '.!?:";)]}*`>"':
        return True
    return False


def _is_degenerate_response(text: str) -> bool:
    """
    Detect Nova Pro output failures. Conservative — only catches clear
    garbage, not legitimate long lists or tables.

    Triggers:
      - Empty or near-empty responses
      - Long runs of the same 1-3 char token (e.g. ' " " " " " ...')
      - Rationale leakage with no answer ("The User's goal is...")
      - Same non-trivial line appearing more than 8 times
      - Same 100-char block appearing more than 8 times in a long response
    """
    if not text or len(text.strip()) < 5:
        return True
    stripped = text.strip()

    # Run of >= 80 repetitions of the same 1-3 char token
    if re.search(r'(.{1,3})\1{80,}', stripped):
        return True

    # Rationale leak with no JSON object anywhere
    rationale_markers = ("The User's goal", "The user is asking", "I will now", "Let me analyze")
    if any(m in stripped for m in rationale_markers) and "{" not in stripped:
        return True

    # Skip line/block repetition checks for markdown tables and numbered lists —
    # they legitimately have many short, similarly-shaped lines.
    looks_like_table_or_list = (
        stripped.count("|") > 10
        or re.search(r'^\s*\d+[\t.)]\s', stripped, flags=re.MULTILINE) is not None
    )

    # Line-level repetition — same MEANINGFUL line appearing >8 times.
    # Skip short table-cell markers like '|', '---', etc.
    from collections import Counter
    lines = [l.strip() for l in stripped.split("\n") if l.strip()]
    if len(lines) > 20 and not looks_like_table_or_list:
        most_common = Counter(lines).most_common(1)[0]
        line, count = most_common
        if count > 8 and len(line) > 10:
            return True

    # Block-level repetition — only for very long responses, larger windows,
    # higher threshold. Avoids false positives on legitimate long content.
    if len(stripped) > 1500 and not looks_like_table_or_list:
        windows: dict[str, int] = {}
        step = 30
        size = 100
        for i in range(0, len(stripped) - size, step):
            w = stripped[i:i + size]
            windows[w] = windows.get(w, 0) + 1
            if windows[w] > 8:
                return True

    return False


def _greeting_reply(message: str) -> str:
    lowered = message.strip().lower().rstrip("!.?")
    if lowered in {"thanks", "thank you", "thx", "ty"}:
        return "You're welcome! Let me know when you're ready to run an analysis."
    return (
        "Hello! I'm VaultBot, your Veeva Vault impact analyst. "
        "Ask me to analyze your data model changes — I can produce a full report "
        "or drill into specific areas (workflows, integrations, layouts, etc.)."
    )


# ─── Chat (thin pass-through to Bedrock Agent) ────────────────────────────────

@router.post("/chat", summary="Chat with the Vault Impact agent")
async def stage1_chat(
    session_id: str = Form(...),
    message: str = Form(...),
):
    """
    Thin pass-through to the Bedrock Agent.
    The agent decides intent, format, and response — the backend does not
    rewrite the user's message or interpret keywords, with one exception:
    pure greetings are answered directly so the agent isn't accidentally
    triggered into full analysis by a stale session_id.
    """
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    if _is_pure_greeting(message):
        return {
            "session_id": session_id,
            "message": message,
            "response": _greeting_reply(message),
            "status": "ok",
        }

    from services import aws_service

    # Pass-through to the agent — same behavior as the Bedrock console.
    # Same Bedrock session across all turns (preserves conversation context).
    # No mode switching, no message reshaping, no auto-retries.
    result = await aws_service.invoke_agent(
        session_id=session_id,
        user_message=message,
        bedrock_session_id=session.metadata.get("bedrock_session_id"),
    )

    if result.get("bedrock_session_id"):
        session.metadata["bedrock_session_id"] = result["bedrock_session_id"]

    # Detect whether the user explicitly asked for a structured JSON
    # export — only then do we attempt to populate the report panel.
    msg_lower = message.lower()
    explicit_export_signals = (
        "as json", "in json", "json format", "give me json", "show me json",
        "json export", "export as json", "export the analysis",
        "structured report", "machine-readable", "machine readable",
        "run a full analysis", "run full analysis", "run analysis",
        "run a full impact analysis", "run an impact analysis",
        "full impact analysis", "complete impact analysis",
    )
    is_analysis = any(s in msg_lower for s in explicit_export_signals)

    raw_response = result.get("response", "")

    # Detect Nova Pro degenerate output — character runs, rationale leakage,
    # or looping/repetition where the model lists the same content many times.
    if _is_degenerate_response(raw_response):
        logger.warning("Degenerate response detected from agent — suppressing")
        return {
            "session_id": session_id,
            "message": message,
            "response": (
                "The agent got stuck in a loop or returned an unusable response. "
                "This usually happens on very open-ended questions about the Configuration Report. "
                "Try being more specific — for example:\n\n"
                "- *\"List the workflow names in my Vault\"*\n"
                "- *\"What integrations does my config have?\"*\n"
                "- *\"Show me the fields on the registration__v object\"*\n"
                "- *\"Run a full impact analysis\"*"
            ),
            "status": "degenerate",
        }

    # Chat-mode safety net: if the agent returned JSON for a conversational
    # question, retry once on a fresh Bedrock session with an explicit
    # "respond as plain text" hint. This is what makes the UI match the
    # console — Nova Pro is inconsistent and sometimes emits JSON for
    # ordinary questions like "Which components are impacted?".
    if not is_analysis:
        is_json_shaped = (
            raw_response.lstrip().startswith("{")
            or raw_response.lstrip().startswith("[")
            or '"impacted_objects"' in raw_response
            or '"objects":' in raw_response
            or '"impacted_fields"' in raw_response
        )
        if is_json_shaped:
            logger.info("Chat-mode response was JSON-shaped — auto-retrying as plain text")
            retry_msg = (
                f"{message}\n\n"
                f"Respond as plain text — a bullet list, short prose, or markdown table. "
                f"Group items by category (Objects / Fields / Workflows / Integrations / "
                f"Layouts / SDK Jobs / Picklists / Reports). Use brief one-line entries. "
                f"Do NOT output JSON, do NOT use a structured response format. "
                f"This is a conversational question, not a request for a structured report."
            )
            retry_result = await aws_service.invoke_agent(
                session_id=session_id,
                user_message=retry_msg,
                bedrock_session_id=None,  # fresh session — no JSON-mode carry-over
            )
            retry_text = retry_result.get("response", "")
            if retry_result.get("bedrock_session_id"):
                session.metadata["bedrock_session_id"] = retry_result["bedrock_session_id"]
            retry_is_json = (
                retry_text.lstrip().startswith("{")
                or retry_text.lstrip().startswith("[")
                or '"impacted_objects"' in retry_text
            )
            if retry_text and not retry_is_json:
                raw_response = retry_text

    # Only extract structured JSON when the user EXPLICITLY asked for a
    # JSON export / structured report.
    structured = aws_service.try_extract_report_json(raw_response) if is_analysis else None

    if structured:
        chat_text = re.sub(
            r'\{[\s\S]*?"impacted_objects"[\s\S]*\}', '', raw_response,
        ).strip()
        chat_text = re.sub(r'```(?:json)?', '', chat_text).strip()
        chat_text = re.sub(r'```', '', chat_text).strip()
        if not chat_text or len(chat_text) < 15:
            total = len(structured.get("impacted_objects", []))
            total_areas = sum(
                len(o.get("impacted_areas", []))
                for o in structured.get("impacted_objects", [])
            )
            chat_text = (
                f"Analysis complete — found {total} impacted objects across "
                f"{total_areas} configuration areas. See the detailed report below."
            )
    else:
        chat_text = raw_response

        # Last-ditch strip: if a chat-mode response STILL has JSON in it
        # (the retry above also failed), remove the JSON block entirely so
        # the chat bubble shows whatever prose surrounded it.
        if not is_analysis and (
            raw_response.lstrip().startswith("{")
            or '"impacted_objects"' in raw_response
        ):
            cleaned = re.sub(r'\{[\s\S]*', '', raw_response).strip()
            if len(cleaned) >= 15:
                chat_text = cleaned
            else:
                chat_text = (
                    "The agent returned an unexpected format. Try rephrasing — "
                    "for example *\"Which workflows are impacted?\"* or "
                    "*\"List the impacted fields.\"*"
                )

    # Final cleanup: trim any "grouped by category" duplicate sections
    # that Nova Pro sometimes appends (violates RULE 11). Applied to all
    # chat-mode responses; analysis-mode summaries are too short to need it.
    if not is_analysis:
        chat_text = _dedupe_agent_response(chat_text)

    # Post-process safety net for scope drift. The backend already
    # appends a "STRICT SCOPE" hint to the agent's message, but Nova Pro
    # sometimes still lists every category. This step deterministically
    # removes out-of-scope section headers and their content.
    if not is_analysis:
        chat_text = _enforce_scope(chat_text, message)

    # If the agent dove straight into a table without a conversational
    # intro (which Nova Pro sometimes does), prepend a short context
    # sentence so the chat bubble reads like the console output.
    if not is_analysis:
        chat_text = _ensure_intro_line(chat_text, message)

    # If a chat-mode table was cut off mid-row by the token limit, auto-
    # continue: wait briefly and ask the agent to resume from where it
    # stopped, then merge the results. Capped at 2 retries to keep
    # latency bounded and avoid infinite loops.
    if not is_analysis and _detect_truncated_table(chat_text):
        MAX_CONTINUATIONS = 2
        for attempt in range(MAX_CONTINUATIONS):
            logger.info(
                "Truncated table detected — auto-continuing (attempt %d/%d)",
                attempt + 1, MAX_CONTINUATIONS,
            )
            # Brief pause so we don't hammer Bedrock back-to-back
            await asyncio.sleep(1.2)

            # Drop the last (incomplete) table row so the continuation
            # picks up cleanly.
            lines = chat_text.split("\n")
            if lines and lines[-1].count("|") > 0 and not lines[-1].rstrip().endswith("|"):
                lines.pop()
            cleaned_so_far = "\n".join(lines).rstrip()

            continuation_prompt = (
                "Continue the table from your previous response. "
                "Output ONLY the missing rows that follow the last one you "
                "completed — do NOT repeat any rows already shown, and do "
                "NOT output the table header or any intro sentence. Use the "
                "same `|`-separated format with the same column order. "
                "If you are about to run out of space again, stop at a "
                "complete row (do not cut off mid-cell)."
            )
            try:
                cont_result = await aws_service.invoke_agent(
                    session_id=session_id,
                    user_message=continuation_prompt,
                    bedrock_session_id=session.metadata.get("bedrock_session_id"),
                )
            except Exception as exc:
                logger.warning("Auto-continuation call failed: %s", exc)
                break

            if cont_result.get("bedrock_session_id"):
                session.metadata["bedrock_session_id"] = cont_result["bedrock_session_id"]

            cont_text = (cont_result.get("response") or "").strip()
            if not cont_text or _is_degenerate_response(cont_text):
                logger.info("Continuation returned no usable content — stopping")
                break

            # Merge — the cleaned_so_far already ends without a trailing
            # newline, and cont_text starts with a row, so put one newline
            # between them.
            chat_text = f"{cleaned_so_far}\n{cont_text}"

            if not _detect_truncated_table(chat_text):
                logger.info("Table is now complete after %d continuation(s)", attempt + 1)
                break

        # If after MAX_CONTINUATIONS attempts the table is STILL truncated,
        # fall back to the original note so the user knows.
        if _detect_truncated_table(chat_text):
            chat_text = chat_text.rstrip() + (
                "\n\n_⚠️ The response is very long. Ask for a narrower view — "
                "e.g. **\"show only critical and high severity\"** or "
                "**\"workflow impacts only\"** — to get the rest._"
            )

    response_payload = {
        "session_id": session_id,
        "message": message,
        "response": chat_text,
        "status": result.get("status", "ok"),
    }

    if structured:
        report = Stage1Report(
            session_id=session_id,
            status=AnalysisStatus.COMPLETED,
            data_model_doc_name=session.metadata.get("data_model_doc_name", "unknown"),
            config_report_source="bedrock-agent",
        )
        report.raw_llm_analysis = json.dumps(structured)
        report.analysis_metadata = _build_metadata(structured.get("metadata", {}))
        report.summary = _build_summary(structured.get("summary", {}))
        report.impacted_objects = _build_impacted_objects(structured.get("impacted_objects", []))
        report.no_impact_confirmed = structured.get("no_impact_confirmed", [])
        session.stage1_report = report
        response_payload["report"] = report.model_dump(mode="json")

    return response_payload


# ─── Report ───────────────────────────────────────────────────────────────────

@router.get("/report/{session_id}", response_model=Stage1Report, summary="Get Stage 1 Report")
async def get_stage1_report(session_id: str):
    try:
        session = analysis_service.get_session(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    report = session.stage1_report
    if not report:
        raise HTTPException(
            status_code=404,
            detail="Stage 1 report not found. Run the analysis first.",
        )

    return report
