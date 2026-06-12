from fastapi import APIRouter, Request
from models import ChatRequest, ChatResponse
from services.impact_service import generate_impact_report
from services.integration_analysis_service import keyword_search

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    release_dfs: dict = getattr(request.app.state, "uploaded_release_dfs", {})
    config_dfs:  dict = getattr(request.app.state, "uploaded_impact_config_dfs", {})

    if not release_dfs or not config_dfs:
        return ChatResponse(
            response=(
                "Both Data Model Change file and Configuration Report are required for impact analysis.\n\n"
                "Please upload:\n"
                "1. **Data Model Change document** (.xlsx)\n"
                "2. **Configuration Report** (.xlsx) — your Vault configuration export\n\n"
                "Use the upload buttons above to provide both files."
            ),
            sources=[], mode="impact",
        )

    latest_release = list(release_dfs.keys())[-1]
    latest_config  = list(config_dfs.keys())[-1]

    # Stage 1 — rule-based structured report
    report = generate_impact_report(release_dfs[latest_release], config_dfs[latest_config])

    # Bedrock enhancement (optional)
    bedrock = getattr(request.app.state, "bedrock", None)
    if bedrock and bedrock.is_configured():
        release_name = latest_release.rsplit(".", 1)[0] if "." in latest_release else latest_release
        report = bedrock.enhance_impact_report(report, release_name=release_name)

    # Cache for Stage 2 and Q&A
    request.app.state.cached_impact_report = report

    return ChatResponse(response=report, sources=[], mode="impact")


@router.post("/ask", response_model=ChatResponse)
async def ask_endpoint(req: ChatRequest, request: Request):
    """
    Q&A endpoint: answer questions about the Stage 1 + Stage 2 reports.
    Uses Bedrock when configured; falls back to keyword search otherwise.
    """
    impact_report      = getattr(request.app.state, "cached_impact_report", "")
    integration_report = getattr(request.app.state, "cached_integration_report", "")

    if not impact_report:
        return ChatResponse(
            response=(
                "No analysis has been run yet.\n\n"
                "Please upload the **Data Model Change document** and **Configuration Report**, "
                "then run the Stage 1 analysis first."
            ),
            sources=[], mode="qa",
        )

    bedrock = getattr(request.app.state, "bedrock", None)
    if bedrock and bedrock.is_configured():
        answer = bedrock.answer_question(
            question=req.message,
            impact_report=impact_report,
            integration_report=integration_report,
            history=[m.model_dump() for m in req.history],
        )
        if answer.strip():
            return ChatResponse(response=answer, sources=[], mode="qa")

    # Fallback: keyword search across both reports
    answer = keyword_search(req.message, impact_report, integration_report)
    return ChatResponse(response=answer, sources=[], mode="qa")
