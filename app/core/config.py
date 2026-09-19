from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "Aibo"
    app_env: str = "development"
    host: str = "127.0.0.1"
    port: int = 8000
    data_dir: str = "./data"
    worker_poll_seconds: float = 0.2
    llm_provider: str = "stub"
    llm_base_url: str = "https://api.openai.com/v1"
    llm_api_key: str = ""
    llm_model: str = "gpt-5.6-mini"
    api_key: str = ""
    session_ttl_seconds: int = 86400
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
