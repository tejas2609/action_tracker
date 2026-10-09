from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    environment: str = "development"
    allowed_hosts: str = "localhost,127.0.0.1,testserver"
    max_request_bytes: int = Field(default=1048576, ge=1024, le=10000000)
    data_encryption_keys: str = ""
    worker_concurrency: int = Field(default=4, ge=1, le=32)
    worker_lease_seconds: int = Field(default=300, ge=300, le=3600)
    ai_concurrency: int = Field(default=4, ge=1, le=32)
    ai_max_input_characters: int = 100000
    ai_classification_output_tokens: int = 2500
    ai_candidate_limit: int = Field(default=20, ge=1, le=40)
    search_generate_answer: bool = False
    session_hours: int = Field(default=8, ge=1, le=24)
    login_attempts_per_minute: int = Field(default=10, ge=1, le=100)
    max_graph_nodes: int = Field(default=2000, ge=100, le=10000)
    log_level: str = "INFO"
    database_pool_size: int = Field(default=5, ge=1, le=50)
    database_max_overflow: int = Field(default=10, ge=0, le=50)
    database_pool_timeout: int = Field(default=30, ge=1, le=60)
    database_url: str = "postgresql+psycopg://tracker:tracker@localhost:5432/tracker"
    demo_login_enabled: bool = False
    ai_provider: str = "groq"
    ai_base_url: str = "https://api.groq.com/"
    ai_model: str = "openai/gpt-oss-20b"
    ai_api_key: str = ""
    cors_origins: str = "http://localhost:4200,http://localhost:8080"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    ai_timeout_seconds: float = 120
    ai_max_output_tokens: int = 8192
    ai_json_mode: bool = True
    google_client_id: str = ""
    google_client_secret: str = ""

    google_redirect_uri: str = "http://localhost:8000/api/integrations/gmail/callback"

    frontend_url: str = "http://localhost:4200"

    integration_token_key: str = ""

    oauth_cookie_secure: bool = False


settings = Settings()
