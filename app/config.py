from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM: any OpenAI-compatible server (Ollama now; vLLM or the LLM gateway later)
    llm_base_url: str = "http://localhost:11434/v1"
    llm_api_key: str = "ollama"
    gen_model: str = "qwen2.5:7b"
    fast_model: str = "qwen2.5:3b"

    # Embeddings
    embed_base_url: str = "http://localhost:11434/v1"
    embed_model: str = "bge-m3"
    embed_dim: int = 1024

    # Reranker (runs locally on CPU, downloaded on first use)
    rerank_model: str = "Xenova/ms-marco-MiniLM-L-12-v2"

    # Agent: reranker scores above relevant_score are kept without asking the LLM,
    # below irrelevant_score are dropped without asking; only the middle is LLM-graded.
    # 3.0 from the eval: real answers mostly score 3-7, a junk video chunk scored 2.0
    relevant_score: float = 3.0
    irrelevant_score: float = -8.0
    max_retries: int = 2

    # Tracing: Phoenix (run it with `uvx arize-phoenix serve`, UI at http://localhost:6006)
    phoenix_url: str = "http://localhost:6006"

    # Database
    database_url: str = "postgresql://kosh:kosh@localhost:5433/kosh"


@lru_cache
def get_settings() -> Settings:
    return Settings()
