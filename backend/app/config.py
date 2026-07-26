from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), extra="ignore")

    PG_HOST: str = "49.232.213.79"
    PG_PORT: int = 5432
    PG_DB: str = "db_expert_claude"
    PG_USER: str = "ad_admin_claude"
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

    # CORS 来源白名单（逗号分隔）。
    # 不能用 "*" 搭配 allow_credentials=True —— 该组合违反 CORS 规范，
    # 浏览器会直接拒绝带凭据的请求。
    # 覆盖演示文档中列出的全部地址：Web 管理端 3000、H5 5174（生产 5173）、
    # mobile-app 3001、API 8000，localhost 与 127.0.0.1 两种写法都要在内，
    # 否则浏览器会以 CORS 失败的形式打断演示。
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://localhost:3001,http://localhost:5173,"
        "http://localhost:5174,http://localhost:8000,"
        "http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:5173,"
        "http://127.0.0.1:5174,http://127.0.0.1:8000,"
        "http://49.232.213.79,http://49.232.213.79:3000,"
        "http://49.232.213.79:3001,http://49.232.213.79:5173,"
        "http://49.232.213.79:5174,http://49.232.213.79:8000"
    )

    @property
    def CORS_ORIGIN_LIST(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # DeepSeek V4 (via SenseNova): 1M context, up to 64K output, JSON Output / Tool Calls.
    # Thinking mode is optional; structured JSON agents should disable thinking for speed.
    LLM_BASE_URL: str = "https://token.sensenova.cn/v1"
    LLM_PROVIDER: str = "sensenova"
    LLM_MODEL: str = "deepseek-v4-flash"
    LLM_API_KEY: str = ""
    LLM_MAX_TOKENS: int = 8192
    LLM_TEMPERATURE: float = 1.0
    LLM_TOP_P: float = 0.95
    LLM_TIMEOUT: int = 180
    # When True, DeepSeek-compatible calls may use thinking mode (slower, reasoning_content).
    # Evidence multi-clause agent always forces thinking off regardless of this flag.
    LLM_ENABLE_THINKING: bool = False

    # 模型分层（共享 Agent 运行时使用）。
    # cheap：简单意图（列任务、意图分类、规划步骤）——可指向更小/更快的模型；
    # standard：常规推理（对话、报告）；vision：多模态。
    # 默认三档都指向主文本模型/视觉模型，保证零配置也能工作；
    # 想省钱就把 LLM_CHEAP_MODEL 指到一个小模型即可。
    LLM_CHEAP_MODEL: str = ""   # 空则回退到 LLM_MODEL
    LLM_STANDARD_MODEL: str = ""  # 空则回退到 LLM_MODEL

    @property
    def cheap_model(self) -> str:
        return self.LLM_CHEAP_MODEL or self.LLM_MODEL

    @property
    def standard_model(self) -> str:
        return self.LLM_STANDARD_MODEL or self.LLM_MODEL

    # 主动性：后台扫描间隔（秒）。0 或负数关闭主动巡检。
    PROACTIVE_SCAN_INTERVAL_SECONDS: int = 1800
    # 主动提醒：距上次审核多少天视为"到期需复审"
    PROACTIVE_REAUDIT_DUE_DAYS: int = 330

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

    # Vision/multimodal model uses a separate setting because text-only models
    # cannot process inspection photos.
    VISION_LLM_BASE_URL: str = "https://token.sensenova.cn/v1"
    VISION_LLM_MODEL: str = "sensenova-6.7-flash-lite"
    VISION_LLM_API_KEY: str = ""

    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024
    PROJECT_DOCUMENT_MAX_FILE_SIZE: int = 50 * 1024 * 1024

    DEBUG: bool = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
