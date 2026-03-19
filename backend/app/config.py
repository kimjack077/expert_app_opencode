from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PG_HOST: str = "117.72.77.52"
    PG_PORT: int = 5432
    PG_DB: str = "db_expert_opencode"
    PG_USER: str = "ad_admin"
    PG_PASSWORD: str = "1234567890@sdtj"

    @property
    def DATABASE_URL(self) -> str:
        from urllib.parse import quote_plus

        password = quote_plus(self.PG_PASSWORD)
        return f"postgresql+asyncpg://{self.PG_USER}:{password}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        from urllib.parse import quote_plus

        password = quote_plus(self.PG_PASSWORD)
        return f"postgresql://{self.PG_USER}:{password}@{self.PG_HOST}:{self.PG_PORT}/{self.PG_DB}"

    SECRET_KEY: str = "efis-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    LLM_BASE_URL: str = "https://api.edgefn.net/v1"
    LLM_MODEL: str = "DeepSeek-V3.2"
    LLM_API_KEY: str = "sk-PJHqVIOVEgya3CAu12682eFb2cBe4aBcB2396625E1Bc7cA3"
    LLM_MAX_TOKENS: int = 8192
    LLM_TEMPERATURE: float = 1.0
    LLM_TOP_P: float = 0.95
    LLM_TIMEOUT: int = 180

    # Embedding model for RAG (NVIDIA API - backup)
    NVIDIA_API_KEY: str = "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"
    NVIDIA_EMBEDDING_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_EMBEDDING_MODEL: str = "nvidia/nv-embed-v1"

    # Primary Embedding model for RAG (BGE-M3 via OpenAI-compatible API)
    EMBEDDING_BASE_URL: str = "https://api.edgefn.net/v1"
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_API_KEY: str = "sk-PJHqVIOVEgya3CAu12682eFb2cBe4aBcB2396625E1Bc7cA3"

    MINIMAX_BASE_URL: str = "https://api.edgefn.net/v1"
    MINIMAX_API_KEY: str = "sk-PJHqVIOVEgya3CAu12682eFb2cBe4aBcB2396625E1Bc7cA3"
    MINIMAX_MODEL: str = "DeepSeek-V3.2"
    MINIMAX_GROUP_ID: str = ""

    # Vision/Multimodal LLM for image analysis (Qwen3.5 Plus)
    VISION_LLM_BASE_URL: str = "https://coding.dashscope.aliyuncs.com/v1"
    VISION_LLM_MODEL: str = "qwen3.5-plus"
    VISION_LLM_API_KEY: str = "sk-sp-473938c68b6d4027b4c0f7754c8028db"

    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024

    DEBUG: bool = True

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
