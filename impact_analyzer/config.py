from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Anthropic
    anthropic_api_key: str = ""

    # AWS
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    s3_config_bucket: str = ""
    s3_config_report_key: str = "config-reports/latest.json"

    aws_agent_lambda_arn: str = ""
    aws_agent_id: str = ""
    aws_agent_alias_id: str = ""

    # App
    app_env: str = "development"
    max_upload_mb: int = 50
    session_ttl_hours: int = 24
    storage_dir: str = "storage"
    mock_llm: bool = False

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def storage_path(self) -> Path:
        p = Path(self.storage_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024


settings = Settings()
