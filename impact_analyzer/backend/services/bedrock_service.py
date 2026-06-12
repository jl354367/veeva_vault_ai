"""
Amazon Bedrock Integration — Placeholder

PURPOSE
-------
This module adds two AI-powered capabilities on top of the existing
rule-based engine:

  1. enhance_impact_report()  — takes the structured 5-section markdown
     report produced by impact_service.py and asks Bedrock to add an
     executive summary, scenario-based risk narrative, and effort estimates.

  2. answer_vault_question()  — takes a user question + context chunks
     scraped from veevavault.help and asks Bedrock for a grounded,
     scenario-aware answer (handles "what would happen if…" style queries).

SETUP (3 steps)
---------------
Step 1 — AWS credentials
  Add to your .env file (see .env.example):
    AWS_ACCESS_KEY_ID=<your IAM key>
    AWS_SECRET_ACCESS_KEY=<your IAM secret>
    AWS_REGION=us-east-1          # change to your preferred region

Step 2 — Enable the model in the AWS Console
  Go to AWS Console → Amazon Bedrock → Model access → Request access for:
    • anthropic.claude-3-5-sonnet-20241022-v2:0   (recommended)
    OR
    • amazon.nova-pro-v1:0                         (AWS-native, slightly cheaper)
  Then set BEDROCK_MODEL_ID in your .env to match.

Step 3 — Install boto3
  pip install boto3>=1.35.0
  (already added to requirements.txt)

After completing these three steps, this service activates automatically —
no other code changes needed.

PLACEHOLDER BEHAVIOUR (when not yet configured)
------------------------------------------------
• is_configured()         → returns False
• enhance_impact_report() → returns the raw report unchanged (passthrough)
• answer_vault_question() → returns "" (caller falls back to rule-based answer)
"""

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Optional import — boto3 is only required when Bedrock is actually configured.
# The service degrades gracefully if boto3 is not installed.
# ─────────────────────────────────────────────────────────────────────────────
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
    _BOTO3_AVAILABLE = True
except ImportError:
    _BOTO3_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
# Model invocation helpers
# ─────────────────────────────────────────────────────────────────────────────

def _build_request_body(model_id: str, system_prompt: str, user_message: str) -> str:
    """
    Build the JSON request body for the chosen model family.

    TODO: BEDROCK INTEGRATION — if you add a new model family, add its
    request format here.  Currently supports:
      • Anthropic Claude  (model_id starts with "anthropic.")
      • Amazon Nova       (model_id starts with "amazon.nova")
    """
    if model_id.startswith("anthropic."):
        # Anthropic Messages API format for Bedrock
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_message}
            ],
        }
    elif model_id.startswith("amazon.nova"):
        # Amazon Nova Converse-style payload
        payload = {
            "schemaVersion": "messages-v1",
            "system": [{"text": system_prompt}],
            "messages": [
                {"role": "user", "content": [{"text": user_message}]}
            ],
            "inferenceConfig": {"max_new_tokens": 4096},
        }
    else:
        # Generic fallback — works for most Bedrock text models
        payload = {
            "prompt": f"{system_prompt}\n\nHuman: {user_message}\n\nAssistant:",
            "max_tokens_to_sample": 4096,
        }
    return json.dumps(payload)


def _parse_response_text(model_id: str, response_body: dict) -> str:
    """
    Extract the generated text from the model response dict.

    TODO: BEDROCK INTEGRATION — add a parser branch if you use a model
    whose response format differs from the two supported here.
    """
    if model_id.startswith("anthropic."):
        return response_body.get("content", [{}])[0].get("text", "")
    if model_id.startswith("amazon.nova"):
        return (
            response_body
            .get("output", {})
            .get("message", {})
            .get("content", [{}])[0]
            .get("text", "")
        )
    # Fallback: try common keys
    for key in ("completion", "outputText", "text", "output"):
        if key in response_body:
            return response_body[key]
    return ""


# ─────────────────────────────────────────────────────────────────────────────
# BedrockService
# ─────────────────────────────────────────────────────────────────────────────

class BedrockService:
    """
    Thin wrapper around Amazon Bedrock Runtime.

    All public methods are safe to call even when Bedrock is not configured —
    they return passthrough / empty values and log a debug message.
    """

    def __init__(self) -> None:
        # ── TODO: BEDROCK SETUP — fill these in .env, not here ────────────────
        self.region:     str = os.getenv("AWS_REGION", "us-east-1")
        self.model_id:   str = os.getenv(
            "BEDROCK_MODEL_ID",
            "anthropic.claude-3-5-sonnet-20241022-v2:0",   # ← change to match what you enabled
        )
        self._access_key:  str | None = os.getenv("AWS_ACCESS_KEY_ID")
        self._secret_key:  str | None = os.getenv("AWS_SECRET_ACCESS_KEY")
        self._session_token: str | None = os.getenv("AWS_SESSION_TOKEN")  # optional, for temp creds
        self._client = None

    # ── Configuration check ───────────────────────────────────────────────────

    def is_configured(self) -> bool:
        """Returns True only when both boto3 is available AND AWS credentials are set."""
        return _BOTO3_AVAILABLE and bool(self._access_key and self._secret_key)

    def status(self) -> dict:
        """Health-check payload returned by /api/bedrock-status."""
        return {
            "configured": self.is_configured(),
            "boto3_available": _BOTO3_AVAILABLE,
            "region": self.region,
            "model_id": self.model_id,
            "credentials_present": bool(self._access_key and self._secret_key),
        }

    # ── Internal client factory ───────────────────────────────────────────────

    def _get_client(self):
        """
        Lazily create and cache the boto3 bedrock-runtime client.

        TODO: BEDROCK SETUP — if you use an IAM role (EC2/ECS/Lambda) instead
        of explicit keys, remove aws_access_key_id / aws_secret_access_key from
        the constructor call below and boto3 will pick up the role credentials
        automatically from the instance metadata service.
        """
        if self._client is None:
            kwargs: dict = {"region_name": self.region}
            if self._access_key:
                kwargs["aws_access_key_id"] = self._access_key
            if self._secret_key:
                kwargs["aws_secret_access_key"] = self._secret_key
            if self._session_token:
                kwargs["aws_session_token"] = self._session_token

            # TODO: BEDROCK INTEGRATION — swap to "bedrock-runtime" for invoke_model,
            # or "bedrock-runtime" with converse() API.  Both work; invoke_model is
            # used here for maximum model compatibility.
            self._client = boto3.client("bedrock-runtime", **kwargs)
        return self._client

    # ── Core invocation ───────────────────────────────────────────────────────

    def _invoke(self, system_prompt: str, user_message: str) -> str:
        """
        Low-level Bedrock call.  Returns model text or "" on any error.

        TODO: BEDROCK INTEGRATION — this is the single call site.  If you want
        streaming responses, replace client.invoke_model() with
        client.invoke_model_with_response_stream() and yield chunks.
        """
        if not self.is_configured():
            logger.debug("BedrockService not configured — skipping invoke.")
            return ""

        try:
            client = self._get_client()
            body   = _build_request_body(self.model_id, system_prompt, user_message)

            response = client.invoke_model(
                modelId     = self.model_id,
                body        = body,
                contentType = "application/json",
                accept      = "application/json",
            )

            response_body = json.loads(response["body"].read())
            return _parse_response_text(self.model_id, response_body)

        except Exception as exc:  # noqa: BLE001
            # Never crash the caller — log and return empty string so the
            # rule-based fallback takes over.
            logger.warning("Bedrock invoke failed: %s", exc)
            return ""

    # ── Public API ────────────────────────────────────────────────────────────

    def enhance_impact_report(
        self,
        raw_report: str,
        release_name: str = "",
    ) -> str:
        """
        Wrap the structured 5-section impact report with AI-generated narrative.

        When Bedrock IS configured:
          • Adds an Executive Summary (3-5 bullets) before Section 1.
          • Adds scenario-based risk commentary after each impacted section.
          • Adds rough effort estimates (T-shirt sizing) to Recommended Actions.

        When Bedrock is NOT configured:
          • Returns raw_report unchanged (existing behaviour preserved).

        TODO: BEDROCK INTEGRATION — tune the system prompt below once you have
        access to a real release + config pair so you can verify the output
        quality.  The current prompt is a solid starting point.
        """
        if not self.is_configured():
            return raw_report

        release_label = f" for **{release_name}**" if release_name else ""

        system_prompt = (
            "You are a senior Veeva Vault administrator and release consultant. "
            "You help customers understand the operational impact of Veeva platform "
            "upgrades on their existing Vault configurations.\n\n"
            "Your tone is professional, precise, and action-oriented. "
            "Avoid marketing language. Focus on concrete risks and next steps."
        )

        user_message = (
            f"Below is an automated impact analysis report{release_label}.\n\n"
            "Please enhance it by:\n"
            "1. Adding a concise **Executive Summary** (3-5 bullet points) at the very top "
            "summarising the most critical risks and recommended actions.\n"
            "2. For each section that has items, add a short **Scenario Risk** paragraph "
            "(2-3 sentences) explaining what could go wrong if the team does NOT act on "
            "these items before the upgrade.\n"
            "3. Append rough **effort estimates** (XS/S/M/L/XL) to each Recommended Action.\n\n"
            "Keep all existing markdown tables and section headers intact. "
            "Return the full enhanced report as valid GitHub-Flavored Markdown.\n\n"
            "--- REPORT START ---\n\n"
            f"{raw_report}\n\n"
            "--- REPORT END ---"
        )

        enhanced = self._invoke(system_prompt, user_message)
        return enhanced if enhanced.strip() else raw_report

    def answer_vault_question(
        self,
        question: str,
        context_chunks: list[str],
        mode: str = "help",
    ) -> str:
        """
        Answer a user question using Bedrock + context from veevavault.help.

        Handles scenario-based / "what-if" questions that the rule-based
        keyword engine cannot answer well.

        When Bedrock IS configured:
          • Grounds the answer in the provided context_chunks (RAG).
          • Handles scenario questions: "What would happen if…", "How should I
            approach…", "What is the risk of…"
          • Returns a well-structured markdown answer.

        When Bedrock is NOT configured:
          • Returns "" so the caller falls back to the existing keyword engine.

        TODO: BEDROCK INTEGRATION — adjust MAX_CONTEXT_CHARS if your model
        supports a larger context window (Claude 3.5 supports 200K tokens).
        """
        if not self.is_configured():
            return ""

        MAX_CONTEXT_CHARS = 12_000
        context_text = "\n\n---\n\n".join(context_chunks)[:MAX_CONTEXT_CHARS]

        system_prompt = (
            "You are VaultBot, an expert Veeva Vault assistant. "
            "You help Vault administrators and business analysts understand "
            "Veeva platform features, configuration, and best practices.\n\n"
            "Rules:\n"
            "- Answer ONLY from the provided context. If the context doesn't cover "
            "the question, say so clearly and suggest where to look.\n"
            "- For scenario/what-if questions, reason step-by-step about consequences.\n"
            "- Format answers as clean GitHub-Flavored Markdown.\n"
            "- Be concise. Prefer bullet points over paragraphs where possible."
        )

        user_message = (
            f"## Context from veevavault.help\n\n{context_text}\n\n"
            f"## Question\n\n{question}"
        )

        return self._invoke(system_prompt, user_message)

    def enhance_integration_report(
        self,
        integration_report: str,
        impact_report: str = "",
    ) -> str:
        """
        Enhance the Stage 2 integration analysis with per-integration narrative
        and concrete remediation guidance.

        When Bedrock IS configured:
          • Adds a short narrative per Critical/High integration explaining
            exactly what will break and why.
          • Suggests concrete remediation steps (field mapping updates,
            connection config changes, test cases).
          • Estimates effort per integration (XS/S/M/L/XL).

        When Bedrock is NOT configured:
          • Returns integration_report unchanged.
        """
        if not self.is_configured():
            return integration_report

        context = ""
        if impact_report:
            context = (
                f"## Stage 1 Impact Report (for reference)\n\n"
                f"{impact_report[:6000]}\n\n"
            )

        system_prompt = (
            "You are a senior Veeva Vault integration architect. "
            "You specialize in Veeva Vault integrations — Spark Messaging, "
            "VaulttoVault, connection loaders, ETL pipelines, and REST API integrations.\n\n"
            "Your tone is technical, precise, and action-oriented."
        )

        user_message = (
            f"{context}"
            "## Stage 2 Integration Analysis (enhance this)\n\n"
            f"{integration_report}\n\n"
            "For each Critical and High Risk integration, please add:\n"
            "1. A **Risk Narrative** (2-3 sentences): what specifically will break "
            "and the business impact if not addressed.\n"
            "2. **Remediation Steps** (numbered list): concrete actions the integration "
            "team must take — field mapping updates, config changes, test scenarios.\n"
            "3. **Effort Estimate** (XS/S/M/L/XL with brief justification).\n\n"
            "Keep all existing tables and section headers intact. "
            "Return valid GitHub-Flavored Markdown."
        )

        enhanced = self._invoke(system_prompt, user_message)
        return enhanced if enhanced.strip() else integration_report

    def answer_question(
        self,
        question: str,
        impact_report: str,
        integration_report: str,
        history: list[dict],
    ) -> str:
        """
        Answer a free-form question about the final report using Bedrock.

        Handles:
          • "Which integrations need changes before upgrade?"
          • "Explain the risk to the Submission Loader"
          • "What is the estimated effort for the ETL pipeline?"
          • "What would happen if we skip the integration review?"
          • Any scenario-based or clarification question

        When Bedrock IS configured: returns a grounded markdown answer.
        When NOT configured: returns "" (caller uses keyword fallback).

        History format: [{"role": "user"|"assistant", "content": "..."}]
        """
        if not self.is_configured():
            return ""

        MAX_REPORT_CHARS = 20_000
        context = ""
        if impact_report:
            context += f"## Stage 1 — Impact Report\n\n{impact_report[:10_000]}\n\n"
        if integration_report:
            context += f"## Stage 2 — Integration Analysis\n\n{integration_report[:10_000]}\n\n"
        context = context[:MAX_REPORT_CHARS]

        # Build conversation history for multi-turn
        history_text = ""
        for msg in history[-6:]:  # last 3 turns
            role = "User" if msg.get("role") == "user" else "Assistant"
            history_text += f"\n**{role}:** {msg.get('content', '')}\n"

        system_prompt = (
            "You are VaultBot, an expert Veeva Vault release advisor. "
            "You have full knowledge of the Veeva platform — objects, fields, "
            "lifecycles, workflows, integrations, and release management.\n\n"
            "You are given the impact analysis report and integration analysis "
            "for a specific Veeva release. Answer questions grounded in these reports.\n\n"
            "Rules:\n"
            "- Base answers on the provided reports. If something isn't covered, say so.\n"
            "- For scenario questions ('what would happen if...'), reason through "
            "consequences step by step.\n"
            "- Keep answers concise and actionable. Use bullet points where possible.\n"
            "- Format as GitHub-Flavored Markdown."
        )

        user_message = (
            f"## Current Reports\n\n{context}\n\n"
            + (f"## Conversation so far\n{history_text}\n\n" if history_text else "")
            + f"## New Question\n\n{question}"
        )

        return self._invoke(system_prompt, user_message)
