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

    # DeepSeek V4 (via EdgeFN / SenseNova): up to 1024K context, JSON Output / Tool Calls.
    LLM_BASE_URL: str = "https://api.edgefn.net/v1"
    LLM_PROVIDER: str = "edgefn"
    LLM_MODEL: str = "DeepSeek-V4-Flash-0731"
    LLM_API_KEY: str = "sk-PJHqVIOVEgya3CAu12682eFb2cBe4aBcB2396625E1Bc7cA3"
    LLM_MAX_TOKENS: int = 128000
    LLM_TEMPERATURE: float = 0.3
    LLM_TOP_P: float = 0.95
    LLM_TIMEOUT: int = 180
    # When True, DeepSeek-compatible calls may use thinking mode (slower, reasoning_content).
    # Evidence multi-clause agent always forces thinking off regardless of this flag.
    LLM_ENABLE_THINKING: bool = False

    # 备用 LLM（主模型 429/超时/异常自动降级用，edgefn 网关 + DeepSeek-V3.2 非推理模型）
    LLM_BACKUP_BASE_URL: str = "https://api.edgefn.net/v1"
    LLM_BACKUP_MODEL: str = "DeepSeek-V3.2"
    LLM_BACKUP_API_KEY: str = "sk-PJHqVIOVEgya3CAu12682eFb2cBe4aBcB2396625E1Bc7cA3"

    @property
    def has_llm_backup(self) -> bool:
        """是否配置了备用 LLM。"""
        return bool(self.LLM_BACKUP_BASE_URL and self.LLM_BACKUP_MODEL and self.LLM_BACKUP_API_KEY)

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

    # AI 文档解析辅助录入专用模型（SenseNova 网关，流式稳定、速度快）
    AI_EXTRACT_LLM_BASE_URL: str = "https://token.sensenova.cn/v1"
    AI_EXTRACT_LLM_MODEL: str = "sensenova-6.8-flash-lite"
    AI_EXTRACT_LLM_API_KEY: str = "sk-QGka5gp5QYBxJXL6UeJwPpwL7b7pZZPR"
    # 推理力度：low/medium/high/none/空（仅推理模型生效）
    # - sensenova-6.8-flash-lite / DeepSeek-V4-Flash：设 low/medium/high 控制思考深度
    # - 非推理模型（DeepSeek-V3.2）：留空或 none，不传 reasoning_effort
    # - DeepSeek 思考模式默认开启无法关闭；none/空时不传 reasoning_effort，走 DeepSeek 默认 medium
    AI_EXTRACT_LLM_REASONING_EFFORT: str = "medium"

    # AI 文档解析备用 LLM（主模型 429/超时/断连自动降级，edgefn 网关 + DeepSeek-V3.2 非推理模型）
    AI_EXTRACT_LLM_BACKUP_BASE_URL: str = "https://api.edgefn.net/v1"
    AI_EXTRACT_LLM_BACKUP_MODEL: str = "DeepSeek-V3.2"
    AI_EXTRACT_LLM_BACKUP_API_KEY: str = "sk-PJHqVIOVEgya3CAu12682eFb2cBe4aBcB2396625E1Bc7cA3"

    @property
    def has_ai_extract_llm_backup(self) -> bool:
        """是否配置了 AI 解析备用 LLM。"""
        return bool(
            self.AI_EXTRACT_LLM_BACKUP_BASE_URL
            and self.AI_EXTRACT_LLM_BACKUP_MODEL
            and self.AI_EXTRACT_LLM_BACKUP_API_KEY
        )

    @property
    def ai_extract_is_thinking_model(self) -> bool:
        """判断当前 AI_EXTRACT 模型是否为推理模型（需要 thinking 开关控制）。"""
        model = (self.AI_EXTRACT_LLM_MODEL or "").lower()
        # DeepSeek-V4 / DeepSeek-R1 等带 reasoning_content 的推理模型
        return "v4" in model or "r1" in model or "reasoning" in model

    @property
    def ai_extract_is_sensenova_reasoning_model(self) -> bool:
        """判断是否为 SenseNova 6.x 推理模型（用 reasoning_effort 直接控制）。"""
        model = (self.AI_EXTRACT_LLM_MODEL or "").lower()
        return "sensenova" in model and "6.8" in model

    @property
    def ai_extract_reasoning_kwargs(self) -> dict:
        """返回给 OpenAI SDK create() 的推理相关参数。

        - sensenova-6.8-flash-lite / DeepSeek-V4-Flash: 传 reasoning_effort=low/medium/high
          （none 时不传，DeepSeek 默认 medium，sensenova 也默认 medium）
        - 非推理模型（DeepSeek-V3.2）: 返回空 dict
        - DeepSeek 关思考：官方未暴露关闭接口，思考模式默认开启无法关闭
        """
        effort = (self.AI_EXTRACT_LLM_REASONING_EFFORT or "").strip().lower()
        if not effort or effort == "none":
            return {}
        if self.ai_extract_is_sensenova_reasoning_model or self.ai_extract_is_thinking_model:
            return {"reasoning_effort": effort}
        return {}

    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024
    PROJECT_DOCUMENT_MAX_FILE_SIZE: int = 50 * 1024 * 1024

    DEBUG: bool = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
