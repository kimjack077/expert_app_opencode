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
    def effective_pg_host(self) -> str:
        host = self.PG_HOST
        # 当部署在线上云服务器自身时，PostgreSQL 与 FastAPI 进程同机运行，
        # 直接走 127.0.0.1 回环网络，消除公网 NAT loopback 延迟与丢包风险。
        # 本地开发环境因不存在 /home/ubuntu/expert_app，依然安全连向远程 PG_HOST。
        if host in ("49.232.213.79", "localhost", "127.0.0.1"):
            if Path("/home/ubuntu/expert_app").exists():
                return "127.0.0.1"
        return host

    @property
    def DATABASE_URL(self) -> str:
        from urllib.parse import quote_plus

        password = quote_plus(self.PG_PASSWORD)
        return f"postgresql+asyncpg://{self.PG_USER}:{password}@{self.effective_pg_host}:{self.PG_PORT}/{self.PG_DB}"

    @property
    def DATABASE_URL_SYNC(self) -> str:
        from urllib.parse import quote_plus

        password = quote_plus(self.PG_PASSWORD)
        return f"postgresql://{self.PG_USER}:{password}@{self.effective_pg_host}:{self.PG_PORT}/{self.PG_DB}"

    SECRET_KEY: str = "efis-secret-key-change-in-production-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # 连接池 checkout 探活（每次取用连接先 SELECT 1）。
    # None（默认）= 按连接目标自动判定：
    #   · 回环/本机（线上 FastAPI 与 PG 同机，成本 <1ms）→ 开启，保留 BUG-17 对
    #     「空闲连接被中间链路断开」的防护；
    #   · 远程主机（本地开发连公网库，单次往返 50~800ms）→ 关闭，省掉每个请求
    #     都要白付一次的网络往返。
    # 需要固定行为时显式设 True/False 覆盖。
    # 关闭的代价：连接闲置较久后第一个请求可能拿到死连接报错（重试即恢复），
    # pool_recycle=1800 仍会每 30 分钟主动回收兜底。
    DB_POOL_PRE_PING: bool | None = None

    @property
    def db_pool_pre_ping(self) -> bool:
        """见 ``DB_POOL_PRE_PING`` 说明：未显式配置时按连接目标自动判定。"""
        if self.DB_POOL_PRE_PING is not None:
            return self.DB_POOL_PRE_PING
        return self.effective_pg_host in ("127.0.0.1", "localhost", "::1")

    # 鉴权用户缓存 TTL（秒）：get_current_user 每个请求原本都要 SELECT users
    # 一次，本地连公网远程库时等于每请求白付一次网络往返。缓存期内（默认 60s）
    # 直接从进程内快照构造用户对象。0 = 禁用缓存（恢复每请求查库）。
    # 一致性约定：本进程内的登出 / 改密 / 改角色 / 删用户会主动失效缓存；
    # 跨进程或直接在库里改数据，最长 TTL 秒后生效（可接受，见 security.py）。
    AUTH_USER_CACHE_TTL_SECONDS: int = 60

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

    # 主模型：AMD Radeon 云（DeepSeek-V4-Flash）
    LLM_BASE_URL: str = "https://developer.amd.com.cn/radeon/api/v1"
    LLM_PROVIDER: str = "amd"
    LLM_MODEL: str = "DeepSeek-V4-Flash"
    LLM_API_KEY: str = "rc-7306d58389263eb712f29dc61c4e2fcf16eb31293f5e7089"
    LLM_MAX_TOKENS: int = 65536
    LLM_TEMPERATURE: float = 0.3
    LLM_TOP_P: float = 0.95
    LLM_TIMEOUT: int = 180
    # DeepSeek 系列模型的思考模式开关。
    # **默认开启**：思考质量直接影响判定/建议的准确性，关闭会明显影响效果。
    # 只在确有需要时临时置 False（例如压测、或某类端点对首包时延极敏感）。
    # Evidence multi-clause agent 有自己的覆盖逻辑，不受本开关影响。
    LLM_ENABLE_THINKING: bool = True
    # 主模型的思考强度：low / medium / high。默认 medium。
    LLM_REASONING_EFFORT: str = "medium"

    # AMD 端点上的其它多模态模型（文本 + 图片），可被简报生成直接选用，并作为视觉备用。
    LLM_EXTRA_MODELS: str = "MiMo-V2.6-Flash,Qwen3.8-Flash-Next"

    # 备用链（顺序即优先级）。备用目标统一限制输出预算：
    # 部分网关（实测 SenseNova）在声明 64k max_tokens 时直接返回 429。
    LLM_FALLBACK_MAX_TOKENS: int = 8192

    # 第 1 备用：EdgeFN DeepSeek-V4-Flash（跨供应商容灾）
    LLM_FALLBACK1_NAME: str = "EdgeFN-DeepSeek-V4-Flash"
    LLM_FALLBACK1_BASE_URL: str = "https://api.edgefn.net/v1"
    LLM_FALLBACK1_MODEL: str = "DeepSeek-V4-Flash"
    LLM_FALLBACK1_API_KEY: str = "sk-PJHqVIOVEgya3CAu12682eFb2cBe4aBcB2396625E1Bc7cA3"
    LLM_FALLBACK1_REASONING_EFFORT: str = "medium"

    # 第 2 备用：SenseNova deepseek-v4-flash
    LLM_FALLBACK2_NAME: str = "SenseNova-DeepSeek-V4-Flash"
    LLM_FALLBACK2_BASE_URL: str = "https://token.sensenova.cn/v1"
    LLM_FALLBACK2_MODEL: str = "deepseek-v4-flash"
    LLM_FALLBACK2_API_KEY: str = "sk-QGka5gp5QYBxJXL6UeJwPpwL7b7pZZPR"
    LLM_FALLBACK2_REASONING_EFFORT: str = "medium"

    # 第 3 备用：SenseNova sensenova-6.8-flash-lite（独立配额抗 429）
    LLM_FALLBACK3_NAME: str = "SenseNova-6.8-Flash-Lite"
    LLM_FALLBACK3_BASE_URL: str = "https://token.sensenova.cn/v1"
    LLM_FALLBACK3_MODEL: str = "sensenova-6.8-flash-lite"
    LLM_FALLBACK3_API_KEY: str = "sk-QGka5gp5QYBxJXL6UeJwPpwL7b7pZZPR"
    LLM_FALLBACK3_REASONING_EFFORT: str = "medium"

    # 第 4 备用：讯飞 MaaS xopqwen36v35b
    LLM_FALLBACK4_NAME: str = "Xunfei-xopqwen36v35b"
    LLM_FALLBACK4_BASE_URL: str = "https://maas-api.cn-huabei-1.xf-yun.com/v2"
    LLM_FALLBACK4_MODEL: str = "xopqwen36v35b"
    LLM_FALLBACK4_API_KEY: str = "76893fbd7cfbeffe6e201416647a83bd:MjUyMjY4YjY1NmVhODQxM2UwYjYyODMy"
    LLM_FALLBACK4_REASONING_EFFORT: str = "medium"

    # 第 5 备用：Agnes agnes-3.0-flash
    LLM_FALLBACK5_NAME: str = "Agnes-3.0-Flash"
    LLM_FALLBACK5_BASE_URL: str = "https://apihub.agnes-ai.com/v1"
    LLM_FALLBACK5_MODEL: str = "agnes-3.0-flash"
    LLM_FALLBACK5_API_KEY: str = "sk-PzYYnjm47YA4Wocto2DdQs87pkEvlQgaYIDhFAItikBFhdtR"
    LLM_FALLBACK5_REASONING_EFFORT: str = "medium"

    # 第 6 备用：AntLing Ling-3.1-flash
    LLM_FALLBACK6_NAME: str = "AntLing-Ling-3.1-Flash"
    LLM_FALLBACK6_BASE_URL: str = "https://api.ant-ling.com/v1"
    LLM_FALLBACK6_MODEL: str = "Ling-3.1-flash"
    LLM_FALLBACK6_API_KEY: str = "sk-studio-7b4c7dd4b4b545fc87ad8eea2171e4aa"
    LLM_FALLBACK6_REASONING_EFFORT: str = "medium"

    @property
    def effective_llm_reasoning_effort(self) -> str | None:
        """主模型实际使用的 reasoning_effort。

        开关关闭时显式传 ``none``（而不是不传）——DeepSeek 兼容网关在不传该参数时
        会回落到默认思考模式，"关闭"就变成了空操作。
        """
        if not self.LLM_ENABLE_THINKING:
            return "none"
        effort = (self.LLM_REASONING_EFFORT or "").strip().lower()
        return effort or "medium"

    @property
    def extra_models(self) -> list[str]:
        return [m.strip() for m in self.LLM_EXTRA_MODELS.split(",") if m.strip()]

    @property
    def llm_fallback_targets(self) -> list[dict]:
        """按 LLM_FALLBACK1..6 的顺序返回已配置的备用目标。"""
        targets: list[dict] = []
        for index in range(1, 7):
            base_url = getattr(self, f"LLM_FALLBACK{index}_BASE_URL", "")
            model = getattr(self, f"LLM_FALLBACK{index}_MODEL", "")
            api_key = getattr(self, f"LLM_FALLBACK{index}_API_KEY", "")
            if not (base_url and model and api_key):
                continue
            targets.append(
                {
                    "name": getattr(self, f"LLM_FALLBACK{index}_NAME", "")
                    or f"Fallback{index}",
                    "base_url": base_url,
                    "model": model,
                    "api_key": api_key,
                    "reasoning_effort": getattr(
                        self, f"LLM_FALLBACK{index}_REASONING_EFFORT", "medium"
                    )
                    or None,
                    "max_tokens": int(
                        getattr(self, f"LLM_FALLBACK{index}_MAX_TOKENS", 0)
                        or self.LLM_FALLBACK_MAX_TOKENS
                    ),
                }
            )
        return targets

    @property
    def has_llm_backup(self) -> bool:
        """是否配置了任意备用 LLM。"""
        return bool(self.llm_fallback_targets)

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

    # Vision/multimodal model（SenseNova deepseek-flash 已验证支持图片输入）
    VISION_LLM_BASE_URL: str = "https://token.sensenova.cn/v1"
    VISION_LLM_MODEL: str = "deepseek-flash"
    VISION_LLM_API_KEY: str = "sk-QGka5gp5QYBxJXL6UeJwPpwL7b7pZZPR"
    VISION_LLM_ENABLE_THINKING: bool = True
    VISION_LLM_REASONING_EFFORT: str = "medium"
    VISION_LLM_FALLBACK_MAX_TOKENS: int = 4096

    # 视觉备用：AMD 端点上的多模态模型（按优先级排列）
    VISION_LLM_FALLBACK1_NAME: str = "AMD-DeepSeek-V4-Flash-Vision-Exp"
    VISION_LLM_FALLBACK1_BASE_URL: str = "https://developer.amd.com.cn/radeon/api/v1"
    VISION_LLM_FALLBACK1_MODEL: str = "DeepSeek-V4-Flash-Vision-Exp"
    VISION_LLM_FALLBACK1_API_KEY: str = "rc-7306d58389263eb712f29dc61c4e2fcf16eb31293f5e7089"
    VISION_LLM_FALLBACK1_REASONING_EFFORT: str = "medium"

    VISION_LLM_FALLBACK2_NAME: str = "AMD-Qwen3.8-Flash-Next"
    VISION_LLM_FALLBACK2_BASE_URL: str = "https://developer.amd.com.cn/radeon/api/v1"
    VISION_LLM_FALLBACK2_MODEL: str = "Qwen3.8-Flash-Next"
    VISION_LLM_FALLBACK2_API_KEY: str = "rc-7306d58389263eb712f29dc61c4e2fcf16eb31293f5e7089"
    VISION_LLM_FALLBACK2_REASONING_EFFORT: str = "medium"

    VISION_LLM_FALLBACK3_NAME: str = "AMD-MiMo-V2.6-Flash"
    VISION_LLM_FALLBACK3_BASE_URL: str = "https://developer.amd.com.cn/radeon/api/v1"
    VISION_LLM_FALLBACK3_MODEL: str = "MiMo-V2.6-Flash"
    VISION_LLM_FALLBACK3_API_KEY: str = "rc-7306d58389263eb712f29dc61c4e2fcf16eb31293f5e7089"
    VISION_LLM_FALLBACK3_REASONING_EFFORT: str = "medium"

    @property
    def effective_vision_reasoning_effort(self) -> str | None:
        if not self.VISION_LLM_ENABLE_THINKING:
            return "none"
        effort = (self.VISION_LLM_REASONING_EFFORT or "").strip().lower()
        return effort or "medium"

    @property
    def vision_fallback_targets(self) -> list[dict]:
        targets: list[dict] = []
        for index in range(1, 4):
            base_url = getattr(self, f"VISION_LLM_FALLBACK{index}_BASE_URL", "")
            model = getattr(self, f"VISION_LLM_FALLBACK{index}_MODEL", "")
            api_key = getattr(self, f"VISION_LLM_FALLBACK{index}_API_KEY", "")
            if not (base_url and model and api_key):
                continue
            targets.append(
                {
                    "name": getattr(self, f"VISION_LLM_FALLBACK{index}_NAME", "")
                    or f"VisionFallback{index}",
                    "base_url": base_url,
                    "model": model,
                    "api_key": api_key,
                    "reasoning_effort": getattr(
                        self, f"VISION_LLM_FALLBACK{index}_REASONING_EFFORT", "medium"
                    )
                    or None,
                    "max_tokens": self.VISION_LLM_FALLBACK_MAX_TOKENS,
                }
            )
        return targets

    # AI 文档解析辅助录入专用模型（AMD DeepSeek-V4-Flash，流式稳定、速度快）
    AI_EXTRACT_LLM_BASE_URL: str = "https://developer.amd.com.cn/radeon/api/v1"
    AI_EXTRACT_LLM_MODEL: str = "DeepSeek-V4-Flash"
    AI_EXTRACT_LLM_API_KEY: str = "rc-7306d58389263eb712f29dc61c4e2fcf16eb31293f5e7089"
    # 推理力度：low/medium/high/none/空（仅推理模型生效）
    # - deepseek-flash / DeepSeek-V4-Flash：设 low/medium/high 控制思考深度
    AI_EXTRACT_LLM_REASONING_EFFORT: str = "medium"
    # 解析长文档需要更高输出预算，但仍低于部分网关的 429 阈值
    AI_EXTRACT_LLM_FALLBACK_MAX_TOKENS: int = 16000

    @property
    def has_ai_extract_llm_backup(self) -> bool:
        """AI 解析与主对话共用同一条备用供应商链。"""
        return bool(self.llm_fallback_targets)

    @property
    def ai_extract_is_thinking_model(self) -> bool:
        """判断当前 AI_EXTRACT 模型是否为推理模型（需要 thinking 开关控制）。"""
        model = (self.AI_EXTRACT_LLM_MODEL or "").lower()
        # deepseek-flash / DeepSeek-V4 / DeepSeek-R1 等带 reasoning_content 的推理模型
        return "v4" in model or "r1" in model or "reasoning" in model or "flash" in model

    @property
    def ai_extract_is_sensenova_reasoning_model(self) -> bool:
        """判断是否为 SenseNova 6.x 推理模型（用 reasoning_effort 直接控制）。"""
        model = (self.AI_EXTRACT_LLM_MODEL or "").lower()
        return "sensenova" in model and "6.8" in model

    @property
    def ai_extract_reasoning_kwargs(self) -> dict:
        """返回给 OpenAI SDK create() 的推理相关参数。

        - deepseek-flash / DeepSeek-V4-Flash: 传 reasoning_effort=low/medium/high
          （none 时不传，DeepSeek 默认 medium，sensenova 也默认 medium）
        - 降级时统一在 llm_fallback 中置为 none 快速响应
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
