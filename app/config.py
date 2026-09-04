from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    aws_region: str = "mock-aws_region"
    debug: bool = True
    enable_bedrock: bool = True
    enable_groq: bool = True
    groq_api_key: str = "mock-groq_api_key"
    host: str = "mock-host"
    log_level: str = "mock-log_level"
    mock_mode: bool = True
    parser_fallback_only: bool = True
    port: int = 8000
    supabase_key: str = "mock-supabase_key"
    supabase_url: str = "mock-supabase_url"

settings = Settings()
