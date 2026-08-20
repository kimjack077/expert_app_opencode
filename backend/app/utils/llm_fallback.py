"""AsyncOpenAI 包装类：主 LLM 遇 429/超时自动切换备用模型。

用法（替换原 AsyncOpenAI(...) 即可，其余代码不变）：

    from app.utils.llm_fallback import create_main_llm_client

    self.client = create_main_llm_client()
    # 调用代码不变：
    response = await self.client.chat.completions.create(model=..., messages=...)
"""
from typing import Any, Optional

import httpx
from openai import AsyncOpenAI, APIConnectionError, APITimeoutError, RateLimitError

from app.config import settings


# 触发降级的异常类型：限流、网关超时、连接失败。
# 不捕获 APIStatusError(500/502/503)，避免对端短暂故障导致误切。
FALLBACK_EXC = (RateLimitError, APITimeoutError, APIConnectionError)


class _CompletionsProxy:
    """代理 completions.create，主模型失败时切换备用 client 并替换 model 名。"""

    def __init__(
        self,
        primary: AsyncOpenAI,
        backup: Optional[AsyncOpenAI],
        backup_model: Optional[str],
        tag: str = "LLM-Fallback",
    ):
        self._primary = primary
        self._backup = backup
        self._backup_model = backup_model
        self._tag = tag

    async def create(self, *args: Any, **kwargs: Any):
        try:
            return await self._primary.chat.completions.create(*args, **kwargs)
        except FALLBACK_EXC as e:
            if not self._backup:
                raise
            backup_kwargs = dict(kwargs)
            if self._backup_model and "model" in backup_kwargs:
                backup_kwargs["model"] = self._backup_model
            # 备用模型强制关闭思考模式：降级场景优先快速响应
            backup_kwargs["reasoning_effort"] = "none"
            # 备用模型不传 stream_options.include_usage，避免网关兼容性问题
            backup_kwargs.pop("stream_options", None)
            print(
                f"[{self._tag}] primary failed ({type(e).__name__}): {e}; "
                f"switching to backup model={self._backup_model}, reasoning_effort=none"
            )
            return await self._backup.chat.completions.create(*args, **backup_kwargs)


class _ChatProxy:
    def __init__(
        self,
        primary: AsyncOpenAI,
        backup: Optional[AsyncOpenAI],
        backup_model: Optional[str],
        tag: str = "LLM-Fallback",
    ):
        self.completions = _CompletionsProxy(primary, backup, backup_model, tag)


class LLMClientWithFallback:
    """AsyncOpenAI 包装类：主模型 429/超时自动切换备用模型。

    代理 chat.completions.create 调用，其他属性转发给 primary。
    """

    def __init__(
        self,
        primary: AsyncOpenAI,
        backup: Optional[AsyncOpenAI] = None,
        backup_model: Optional[str] = None,
        tag: str = "LLM-Fallback",
    ):
        self._primary = primary
        self._backup = backup
        self.chat = _ChatProxy(primary, backup, backup_model, tag)

    def __getattr__(self, name: str):
        # 未显式代理的属性（base_url、api_key、models 等）直接读 primary
        return getattr(self._primary, name)


def create_main_llm_client() -> LLMClientWithFallback:
    """创建主 LLM 客户端，配置了备用模型时自动启用降级。

    读 settings 中的 LLM_BASE_URL/MODEL/API_KEY 作为主，
    LLM_BACKUP_BASE_URL/MODEL/API_KEY 作为备用（可选）。
    """
    primary = AsyncOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        timeout=settings.LLM_TIMEOUT,
    )
    backup: Optional[AsyncOpenAI] = None
    if settings.has_llm_backup:
        backup = AsyncOpenAI(
            base_url=settings.LLM_BACKUP_BASE_URL,
            api_key=settings.LLM_BACKUP_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        print(
            f"[LLM-Fallback] backup configured: "
            f"{settings.LLM_BACKUP_BASE_URL} / {settings.LLM_BACKUP_MODEL}"
        )
    return LLMClientWithFallback(
        primary=primary,
        backup=backup,
        backup_model=settings.LLM_BACKUP_MODEL if settings.has_llm_backup else None,
        tag="LLM-Fallback",
    )


def create_ai_extract_llm_client() -> LLMClientWithFallback:
    """创建 AI 文档解析 LLM 客户端，配置了备用模型时自动启用降级。

    与主 LLM 区别：使用 AI_EXTRACT_LLM_* 配置、长超时（read=600s）、独立备用模型。
    降级时备用模型强制 reasoning_effort=none。
    """
    # AI 解析需要长读超时（大文档流式响应慢）
    primary_timeout = httpx.Timeout(connect=15.0, read=600.0, write=60.0, pool=15.0)
    primary = AsyncOpenAI(
        base_url=settings.AI_EXTRACT_LLM_BASE_URL,
        api_key=settings.AI_EXTRACT_LLM_API_KEY,
        timeout=primary_timeout,
    )
    backup: Optional[AsyncOpenAI] = None
    if settings.has_ai_extract_llm_backup:
        backup = AsyncOpenAI(
            base_url=settings.AI_EXTRACT_LLM_BACKUP_BASE_URL,
            api_key=settings.AI_EXTRACT_LLM_BACKUP_API_KEY,
            timeout=primary_timeout,
        )
        print(
            f"[AIExtract-Fallback] backup configured: "
            f"{settings.AI_EXTRACT_LLM_BACKUP_BASE_URL} / "
            f"{settings.AI_EXTRACT_LLM_BACKUP_MODEL}"
        )
    return LLMClientWithFallback(
        primary=primary,
        backup=backup,
        backup_model=(
            settings.AI_EXTRACT_LLM_BACKUP_MODEL
            if settings.has_ai_extract_llm_backup
            else None
        ),
        tag="AIExtract-Fallback",
    )

