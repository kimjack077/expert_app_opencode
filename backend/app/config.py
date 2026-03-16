from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    PG_HOST: str = "62.234.0.182"
    PG_PORT: int = 5432
    PG_DB: str = "db_expert_opencode"
    PG_USER: str = "db_admin"
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

    MINIMAX_BASE_URL: str = "https://api.edgefn.net/v1"
    MINIMAX_API_KEY: str = "sk-PJHqVIOVEgya3CAu12682eFb2cBe4aBcB2396625E1Bc7cA3"
    MINIMAX_MODEL: str = "DeepSeek-V3.2"
    MINIMAX_GROUP_ID: str = ""

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
