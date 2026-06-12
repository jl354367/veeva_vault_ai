"""
Amazon Bedrock LLM client for VaultBot.

This module is used by llm_service.BedrockLLM when LLM_BACKEND=bedrock.
It is intentionally NOT imported at module load time — only when Bedrock is active —
so the app starts cleanly even if boto3 is not installed.

──────────────────────────────────────────────────────────────────────────────
SETUP GUIDE
──────────────────────────────────────────────────────────────────────────────

1. Install the AWS SDK:
       pip install boto3

2. Set these variables in backend/.env (see .env.example for the full template):

       LLM_BACKEND=bedrock

       AWS_ACCESS_KEY_ID=AKIA...          ← your IAM access key
       AWS_SECRET_ACCESS_KEY=...          ← your IAM secret key
       AWS_REGION=us-east-1               ← region where your Bedrock model is enabled
       BEDROCK_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0

3. Make sure the IAM user / role has the Bedrock policy:
       Action:   bedrock:InvokeModel
       Resource: arn:aws:bedrock:<region>::foundation-model/<model-id>

4. Enable the model in your AWS account:
       AWS Console → Amazon Bedrock → Model access → Request access

5. Flip the switch and restart the backend — no other code changes needed.

──────────────────────────────────────────────────────────────────────────────
SUPPORTED MODELS (set BEDROCK_MODEL_ID to one of these)
──────────────────────────────────────────────────────────────────────────────

  anthropic.claude-3-5-sonnet-20241022-v2:0   ← default (best quality)
  anthropic.claude-3-5-haiku-20241022-v1:0    ← faster / cheaper
  anthropic.claude-3-haiku-20240307-v1:0
  anthropic.claude-3-sonnet-20240229-v1:0
  amazon.titan-text-express-v1
  meta.llama3-8b-instruct-v1:0
  meta.llama3-70b-instruct-v1:0
  mistral.mistral-7b-instruct-v0:2
  mistral.mixtral-8x7b-instruct-v0:1

──────────────────────────────────────────────────────────────────────────────
"""

import os

# ── Env vars (read once at import time) ───────────────────────────────────────

AWS_ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION            = os.getenv("AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID      = os.getenv(
    "BEDROCK_MODEL_ID",
    "anthropic.claude-3-5-sonnet-20241022-v2:0",
)
MAX_TOKENS = int(os.getenv("BEDROCK_MAX_TOKENS", "2048"))

# ── System prompts per mode ────────────────────────────────────────────────────

_SYSTEM_PROMPTS: dict[str, str] = {
    "help": (
        "You are VaultBot, an expert Veeva Vault assistant. "
        "Your job is to answer questions about Veeva Vault features, configuration, and best practices.\n\n"

        "CONTEXT USAGE:\n"
        "- You will receive relevant excerpts from veevavault.help documentation in the <context> block.\n"
        "- Always prefer information from the context over your general training knowledge.\n"
        "- If the context answers the question, base your response primarily on it.\n"
        "- If the context is not relevant, fall back to your Veeva Vault knowledge.\n"
        "- Cite the source URL when the context was used (e.g. *Source: platform.veevavault.help/...*)\n\n"

        "SCENARIO & SITUATION-BASED QUESTIONS:\n"
        "- When the user describes a situation ('I need to...', 'We want to...', 'Our team is trying to...'),\n"
        "  identify the relevant Vault features and explain the best approach.\n"
        "- Provide practical, step-by-step guidance including Vault menu paths where relevant.\n"
        "- Consider trade-offs (e.g. Atomic Security vs Dynamic Access Control).\n"
        "- If the question implies a workflow or multi-step process, lay it out clearly.\n\n"

        "RESPONSE STYLE:\n"
        "- Use **markdown** formatting: headers (##), bullet points, numbered steps, bold key terms.\n"
        "- For conceptual questions: definition + key points + example.\n"
        "- For how-to questions: numbered steps with Admin menu paths.\n"
        "- For scenario questions: situation analysis → recommended approach → implementation steps.\n"
        "- Keep answers focused and practical. Avoid padding.\n"
        "- Professional but approachable tone."
    ),

    "config": (
        "You are VaultBot in Configuration Analysis mode. "
        "You are an expert Veeva Vault administrator helping users understand their specific Vault configuration.\n\n"

        "CONTEXT USAGE:\n"
        "- You will receive relevant sections of the user's Vault configuration in the <context> block.\n"
        "- Always ground your answer in the actual configuration data provided.\n"
        "- Cite specific names, counts, and settings from the context.\n"
        "- If information is not in the context, say so clearly.\n\n"

        "SCENARIO & SITUATION-BASED QUESTIONS:\n"
        "- When the user asks 'what if...' or 'how should we...' questions about their config,\n"
        "  analyse the current setup and give specific, actionable recommendations.\n"
        "- Highlight potential risks or conflicts in the configuration when you spot them.\n\n"

        "RESPONSE STYLE:\n"
        "- Structured summaries with sections: Document Types, Lifecycles, Roles, Workflows, etc.\n"
        "- Use tables for lists of items (names, counts, states).\n"
        "- Be specific — reference actual names from the config, not generic examples.\n"
        "- Flag anomalies (e.g. missing lifecycle states, orphaned roles) proactively."
    ),

    "onboard": (
        "You are VaultBot in Onboarding mode. "
        "You are a friendly, senior Veeva consultant helping a new team member get up to speed "
        "on this specific Vault implementation.\n\n"

        "CONTEXT USAGE:\n"
        "- You will receive onboarding documentation and project-specific notes in the <context> block.\n"
        "- Use the context to answer questions about this team's processes, environment, and decisions.\n\n"

        "RESPONSE STYLE:\n"
        "- Welcoming, encouraging tone — this is someone's first time.\n"
        "- Explain Vault terminology with simple definitions when introducing it.\n"
        "- Connect the specific setup to general Vault concepts so the new person builds a mental model.\n"
        "- Suggest follow-up questions or next topics proactively.\n"
        "- Keep explanations clear and jargon-light unless the person is already technical."
    ),
}


# ── Bedrock client factory (lazy — boto3 is optional) ─────────────────────────

def _get_client():
    """Create and return a boto3 bedrock-runtime client."""
    try:
        import boto3  # noqa: PLC0415
    except ImportError as e:
        raise RuntimeError(
            "boto3 is not installed. Run: pip install boto3"
        ) from e

    kwargs: dict = {"region_name": AWS_REGION}
    # Only pass explicit keys if they are set — otherwise boto3 uses its default
    # credential chain (env vars, ~/.aws/credentials, IAM role, etc.)
    if AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY:
        kwargs["aws_access_key_id"]     = AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = AWS_SECRET_ACCESS_KEY

    return boto3.client("bedrock-runtime", **kwargs)


# ── Context builder ────────────────────────────────────────────────────────────

def _build_context_block(context_chunks: list[str]) -> str:
    if not context_chunks:
        return ""
    chunks_text = "\n\n---\n\n".join(context_chunks[:5])  # cap at 5 chunks
    return f"\n\n<context>\n{chunks_text}\n</context>"


# ── History converter ──────────────────────────────────────────────────────────

def _build_messages(
    message: str,
    context_chunks: list[str],
    history: list[dict],
) -> list[dict]:
    """
    Build the Bedrock Converse API messages list.
    Injects context into the latest user turn.
    """
    messages: list[dict] = []

    # Add prior conversation history (skip the last user turn — we'll add it with context)
    for turn in history:
        role = turn.get("role", "user")
        if role not in ("user", "assistant"):
            continue
        messages.append({
            "role": role,
            "content": [{"text": turn.get("content", "")}],
        })

    # Build the current user message with context injected
    context_block = _build_context_block(context_chunks)
    user_text = message
    if context_block:
        user_text = (
            f"Use the following Veeva Help documentation as context for your answer:"
            f"{context_block}\n\n"
            f"Question: {message}"
        )

    messages.append({
        "role": "user",
        "content": [{"text": user_text}],
    })

    return messages


# ── Main invoke function ───────────────────────────────────────────────────────

def invoke_bedrock(
    message: str,
    context_chunks: list[str],
    mode: str = "help",
    history: list[dict] | None = None,
) -> str:
    """
    Call Amazon Bedrock and return the assistant's response as a string.

    Parameters
    ----------
    message       : The user's question or request.
    context_chunks: Retrieved Veeva help page excerpts (from help_fetcher or RAG).
    mode          : "help" | "config" | "onboard" — selects the system prompt.
    history       : Previous conversation turns [{role, content}, ...].

    Returns
    -------
    The model's text response, or a friendly error message on failure.
    """
    history = history or []
    system_prompt = _SYSTEM_PROMPTS.get(mode, _SYSTEM_PROMPTS["help"])

    try:
        client   = _get_client()
        messages = _build_messages(message, context_chunks, history)

        response = client.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={
                "maxTokens":   MAX_TOKENS,
                "temperature": 0.3,   # low temp for factual/technical answers
                "topP":        0.9,
            },
        )

        # Extract text from response
        output_message = response.get("output", {}).get("message", {})
        content_blocks = output_message.get("content", [])
        text_parts = [
            block["text"]
            for block in content_blocks
            if block.get("type") == "text" or "text" in block
        ]
        return "\n".join(text_parts).strip() or "No response generated."

    except RuntimeError as e:
        # boto3 not installed
        return (
            f"⚠️ **Bedrock not available:** {e}\n\n"
            "Set `LLM_BACKEND=demo` in your `.env` file to use the built-in keyword engine."
        )
    except Exception as e:
        err = str(e)
        # Provide actionable error messages for common issues
        if "credentials" in err.lower() or "NoCredentialsError" in err:
            return (
                "⚠️ **AWS credentials not configured.**\n\n"
                "Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `backend/.env`.\n"
                "See the setup guide in `services/bedrock_service.py`."
            )
        if "AccessDeniedException" in err or "UnauthorizedOperation" in err:
            return (
                f"⚠️ **AWS access denied for model `{BEDROCK_MODEL_ID}`.**\n\n"
                "Make sure:\n"
                "1. The IAM user has the `bedrock:InvokeModel` permission.\n"
                "2. The model is enabled in Amazon Bedrock → Model access.\n"
                f"3. You are using region `{AWS_REGION}` where the model is available."
            )
        if "ResourceNotFoundException" in err or "ValidationException" in err:
            return (
                f"⚠️ **Model ID not found: `{BEDROCK_MODEL_ID}`.**\n\n"
                "Check `BEDROCK_MODEL_ID` in your `.env`. "
                "See the supported models list in `services/bedrock_service.py`."
            )
        if "EndpointResolutionError" in err or "ConnectTimeoutError" in err:
            return (
                f"⚠️ **Could not connect to AWS Bedrock in region `{AWS_REGION}`.**\n\n"
                "Check your `AWS_REGION` setting and network connectivity."
            )
        # Generic fallback
        return (
            f"⚠️ **Bedrock error:** {err}\n\n"
            "Check your `backend/.env` settings. "
            "See the setup guide in `services/bedrock_service.py`."
        )
