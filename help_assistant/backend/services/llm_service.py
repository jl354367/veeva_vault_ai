"""
LLM backend abstraction for VaultBot.

Mirrors the storage.py pattern — swap between backends via a single env var.

──────────────────────────────────────────────────────────────────────────────
QUICK START
──────────────────────────────────────────────────────────────────────────────

  # backend/.env

  LLM_BACKEND=demo        ← default, no API key needed (keyword-based engine)
  LLM_BACKEND=bedrock     ← Amazon Bedrock (requires AWS credentials)

──────────────────────────────────────────────────────────────────────────────
ADDING A NEW BACKEND (e.g. OpenAI, Azure OpenAI, Google Vertex)
──────────────────────────────────────────────────────────────────────────────

  1. Create services/openai_service.py  (see bedrock_service.py as a reference)
  2. Subclass BaseLLM below and implement chat()
  3. Add a branch in get_llm()

──────────────────────────────────────────────────────────────────────────────
"""

import os
from abc import ABC, abstractmethod

# Which backend to use — read once at import time
LLM_BACKEND: str = os.getenv("LLM_BACKEND", "demo").lower().strip()


# ── Abstract interface ─────────────────────────────────────────────────────────

class BaseLLM(ABC):
    """
    All LLM backends implement this single method.

    Parameters
    ----------
    message       : The latest user message.
    context_chunks: Retrieved content chunks (Veeva help pages, config data, etc.)
                    already fetched by the router before calling chat().
    mode          : "help" | "config" | "onboard"
    history       : Prior conversation turns as [{role, content}, ...].

    Returns
    -------
    A markdown-formatted string to display in the chat UI.
    """

    @abstractmethod
    def chat(
        self,
        message:        str,
        context_chunks: list[str],
        mode:           str,
        history:        list[dict],
    ) -> str: ...

    @property
    def name(self) -> str:
        return self.__class__.__name__


# ── Demo backend (built-in keyword engine, no API key needed) ──────────────────

class DemoLLM(BaseLLM):
    """
    Uses the built-in keyword-scoring engine from claude_service.py.
    No external API calls — works offline and out of the box.

    Limitations compared to Bedrock:
    - Cannot reason across context or history
    - Answers scenario/situation questions by keyword matching only
    - No language understanding — exact term matches required
    """

    def chat(
        self,
        message:        str,
        context_chunks: list[str],
        mode:           str,
        history:        list[dict],
    ) -> str:
        from services import claude_service  # noqa: PLC0415
        return claude_service.chat(message, context_chunks, mode)


# ── Amazon Bedrock backend ─────────────────────────────────────────────────────

class BedrockLLM(BaseLLM):
    """
    Amazon Bedrock — production-quality LLM responses.

    Supports scenario-based answers, full conversation history,
    and uses retrieved Veeva help content as grounded context (RAG).

    Setup: see services/bedrock_service.py for the full configuration guide.
    Required .env vars:
        LLM_BACKEND=bedrock
        AWS_ACCESS_KEY_ID=...
        AWS_SECRET_ACCESS_KEY=...
        AWS_REGION=us-east-1
        BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
    """

    def chat(
        self,
        message:        str,
        context_chunks: list[str],
        mode:           str,
        history:        list[dict],
    ) -> str:
        # Import lazily so the app starts even if boto3 is not installed
        from services.bedrock_service import invoke_bedrock  # noqa: PLC0415
        return invoke_bedrock(message, context_chunks, mode, history)


# ────────────────────────────────────────────────────────────────────────────
#  ▼▼▼  ADD FUTURE BACKENDS HERE  ▼▼▼
#
# class AzureOpenAILLM(BaseLLM):
#     """Azure OpenAI — set LLM_BACKEND=azure_openai in .env"""
#     def chat(self, message, context_chunks, mode, history) -> str:
#         from services.azure_openai_service import invoke_azure   # create this file
#         return invoke_azure(message, context_chunks, mode, history)
#
# class GeminiLLM(BaseLLM):
#     """Google Gemini — set LLM_BACKEND=gemini in .env"""
#     def chat(self, message, context_chunks, mode, history) -> str:
#         from services.gemini_service import invoke_gemini         # create this file
#         return invoke_gemini(message, context_chunks, mode, history)
# ────────────────────────────────────────────────────────────────────────────


# ── Factory ────────────────────────────────────────────────────────────────────

_BACKENDS: dict[str, type[BaseLLM]] = {
    "demo":    DemoLLM,
    "bedrock": BedrockLLM,
    # "azure_openai": AzureOpenAILLM,
    # "gemini":       GeminiLLM,
}


def get_llm() -> BaseLLM:
    """
    Return the configured LLM backend instance.

    Reads LLM_BACKEND from the environment (set in backend/.env).
    Defaults to DemoLLM if the value is unrecognised.
    """
    backend_cls = _BACKENDS.get(LLM_BACKEND, DemoLLM)
    return backend_cls()


def active_backend() -> str:
    """Return the name of the currently active backend (for logging / health checks)."""
    return LLM_BACKEND if LLM_BACKEND in _BACKENDS else "demo"
