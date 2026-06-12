import asyncio
from fastapi import APIRouter, Request
from models import ChatRequest, ChatResponse
from services.llm_service import get_llm, active_backend
from services.help_fetcher import fetch_vault_help

router = APIRouter()

_WEB_TIMEOUT = 20.0


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(req: ChatRequest, request: Request):
    mode    = req.mode or "help"
    history = [m.model_dump() for m in req.history] if req.history else []
    llm     = get_llm()

    # ── Fetch context based on mode ───────────────────────────────────────────

    if mode == "help":
        # Retrieve relevant Veeva help page content (local TF-IDF → live web fallback)
        try:
            context_chunks = await asyncio.wait_for(
                fetch_vault_help(req.message), timeout=_WEB_TIMEOUT
            )
        except (asyncio.TimeoutError, Exception):
            context_chunks = []

    elif mode in ("config", "onboard"):
        # Query the in-memory RAG (ChromaDB) for relevant chunks from uploaded data
        rag = getattr(request.app.state, "rag", None)
        if rag:
            context_chunks = rag.query(req.message, mode=mode, n_results=5)
        else:
            context_chunks = []

    else:
        context_chunks = []

    # ── Generate response ─────────────────────────────────────────────────────

    response_text = llm.chat(
        message        = req.message,
        context_chunks = context_chunks,
        mode           = mode,
        history        = history,
    )

    return ChatResponse(
        response = response_text,
        sources  = [],
        mode     = mode,
    )


@router.get("/chat/backend")
async def get_backend():
    """Return the active LLM backend name — useful for debugging."""
    return {"backend": active_backend()}
