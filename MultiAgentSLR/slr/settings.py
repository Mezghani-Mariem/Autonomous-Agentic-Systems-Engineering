import os
from pathlib import Path
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path("data")
    experiment_dir: Path = Path("experiments")
    provider: str = "ollama"
    groq_model: str = "openai/gpt-oss-20b"
    groq_key: str = ""
    ollama_model: str = "qwen2.5:7b"
    ollama_url: str = "http://localhost:11434"
    embedding_model: str = ""
    openalex_key: str = ""
    semantic_key: str = ""
    crossref_email: str = ""
    access_token: str = ""
    cache_ttl: int = 86400
    timeout: float = 25.0

    @classmethod
    def from_env(cls):
        load_dotenv()
        provider = os.getenv("LLM_PROVIDER", "ollama").lower()
        if provider not in {"ollama", "groq"}:
            raise ValueError("LLM_PROVIDER must be ollama or groq")
        return cls(
            data_dir=Path(os.getenv("SLR_DATA_DIR", "data")),
            experiment_dir=Path(os.getenv("SLR_EXPERIMENT_DIR", "experiments")),
            provider=provider,
            groq_model=os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
            groq_key=os.getenv("GROQ_API_KEY", ""),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5:7b"),
            ollama_url=os.getenv("OLLAMA_BASE_URL") or "http://localhost:11434",
            embedding_model=os.getenv("OLLAMA_EMBEDDING_MODEL", ""),
            openalex_key=os.getenv("OPENALEX_API_KEY", ""),
            semantic_key=os.getenv("SEMANTIC_SCHOLAR_API_KEY", ""),
            crossref_email=os.getenv("CROSSREF_EMAIL", ""),
            access_token=os.getenv("SLR_ACCESS_TOKEN", ""),
            cache_ttl=max(0, int(os.getenv("SLR_CACHE_TTL_SECONDS", "86400"))),
            timeout=float(os.getenv("SLR_REQUEST_TIMEOUT_SECONDS", "25")),
        )
