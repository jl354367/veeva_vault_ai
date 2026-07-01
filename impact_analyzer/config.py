"""
Configuration loader.

Reads all settings from the `.env` file (and environment variables) into
one `settings` object that the rest of the app imports. Nothing here
runs at request time — it's just a place to hold configuration.

Add a new setting: (1) declare a field on `Settings`, (2) put its value
in `.env` (and `.env.example`), (3) import `settings.your_new_field`
where needed.
"""
from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # ─── Anthropic (unused today — kept for possible future direct-Claude fallback) ─
    anthropic_api_key: str = ""

    # ─── AWS credentials & region ────────────────────────────────────────────────
    # Blank values mean "let boto3 pick up credentials from ~/.aws or IAM role"
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    # ─── S3 buckets/prefixes ─────────────────────────────────────────────────────
    # Where the Vault Configuration Report lives (written by an AWS Lambda)
    s3_config_bucket: str = ""
    s3_config_report_key: str = "config-reports/latest.json"
    s3_vault_reports_prefix: str = "vault-reports/"
    # Where user-uploaded Data Model Changes documents get pushed
    s3_uploads_bucket: str = ""
    s3_uploads_prefix: str = "data-model-changes/"

    # ─── Bedrock Agent (the AI that does the analysis) ───────────────────────────
    aws_agent_id: str = ""          # Agent identifier from the Bedrock console
    aws_agent_alias_id: str = ""    # Which agent version to hit (production alias)
    bedrock_model_id: str = "amazon.nova-micro-v1:0"  # informational only

    # ─── App runtime settings ────────────────────────────────────────────────────
    app_env: str = "development"    # "development" enables debug logging
    max_upload_mb: int = 50         # per-file upload cap
    session_ttl_hours: int = 24     # sessions older than this get purged
    storage_dir: str = "storage"    # local folder for uploaded files
    mock_llm: bool = False          # if True, use a fake local LLM instead of Bedrock

    # Pydantic reads from `.env` automatically; unknown env keys are ignored.
    model_config = {"env_file": ".env", "extra": "ignore"}

    # ─── Convenience properties ──────────────────────────────────────────────────

    @property
    def storage_path(self) -> Path:
        """Return the storage directory, creating it if it doesn't exist yet."""
        p = Path(self.storage_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def max_upload_bytes(self) -> int:
        """Upload cap in bytes (used by validators)."""
        return self.max_upload_mb * 1024 * 1024


# Single shared settings instance — every other file imports from here.
settings = Settings()
