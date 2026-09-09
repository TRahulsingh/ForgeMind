from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    google_api_key: str = ""
    github_token: str = ""
    api_key: str = "demo-key-123"
    langchain_tracing_v2: bool = False
    langchain_api_key: str = ""
    langchain_project: str = "autonomous-ai-engineer"
    database_path: str = "./app.db"
    chroma_path: str = "./chroma_db"
    checkpoint_path: str = "./checkpoints.db"
    output_path: str = "./output"

    model_config = {"env_file": ".env", "extra": "allow"}

settings = Settings()

# Ensure dirs
for p in [settings.output_path, settings.chroma_path]:
    Path(p).mkdir(parents=True, exist_ok=True)
