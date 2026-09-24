from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@localhost:5432/safetycheck"
    #openai_api_key: str = ""
   # gemini_api_key: str = ""
   # gemini_model: str = "gemini-2.5-flash-lite"
    groq_api_key: str = ""
    groq_model: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    secret_key: str = "dev-secret-change-me"
    access_token_expire_minutes: int = 1440
    environment: str = "development"
    upload_dir: str = "uploads"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
