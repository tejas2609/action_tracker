from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://tracker:tracker@localhost:5432/tracker"
    demo_login_enabled: bool = True
    ai_provider: str = "groq"
    ai_base_url: str = "https://api.groq.com/"
    ai_model: str = "openai/gpt-oss-20b"
    ai_api_key: str = ""
    cors_origins: str = "http://localhost:4200,http://localhost:8080"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    ai_timeout_seconds: float = 120
    ai_max_output_tokens: int = 8192
    ai_json_mode: bool = True


settings = Settings()
