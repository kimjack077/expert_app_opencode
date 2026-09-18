"""AsyncOpenAI 包装类：主 LLM 遇到异常/超时/429/500/断连时自动无缝切换备用模型。

用法（替换原 AsyncOpenAI(...) 即可，其余代码不变）：

    from app.utils.llm_fallback import create_main_llm_client

    self.client = create_main_llm_client()
    # 调用代码完全不变，支持普通与流式模式：
    response = await self.client.chat.completions.create(model=..., messages=...)
"""
import logging
from typing import Any, Optional, AsyncGenerator

import httpx
from openai import (
    AsyncOpenAI,
    APIError,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    APIStatusError,
    InternalServerError,
)

from app.config import settings

logger = logging.getLogger(__name__)

# 触发降级的异常类型：包含限流、超时、连接断开、服务器 5xx、无效请求体及网络协议错误
FALLBACK_EXC = (
    APIError,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    APIStatusError,
    InternalServerError,
    httpx.HTTPError,
    httpx.TimeoutException,
    httpx.ConnectError,
    httpx.RemoteProtocolError,
)

# 标记属性：降级发生后盖在响应对象上，供调用方记账时识别真实服务模型（BUG-15）
FALLBACK_FLAG = "_efis_fallback_used"
ACTUAL_MODEL_ATTR = "_efis_actual_model"
FALLBACK_REASON_ATTR = "_efis_fallback_reason"


def mark_fallback_response(response: Any, backup_model: Optional[str], reason: str) -> Any:
    """在（非流式）响应对象上记录「本次由备用模型提供服务」的痕迹。"""
    actual = backup_model or getattr(response, "model", None)
    for attr, value in (
        (FALLBACK_FLAG, True),
        (ACTUAL_MODEL_ATTR, actual),
        (FALLBACK_REASON_ATTR, reason[:500]),
    ):
        try:
            setattr(response, attr, value)
        except Exception:  # pragma: no cover - 个别 SDK 模型可能冻结属性
            logger.debug("无法在响应对象上写入 %s", attr, exc_info=True)
    return response


def was_fallback(response: Any) -> bool:
    return bool(getattr(response, FALLBACK_FLAG, False))


def served_model(response: Any, requested: Optional[str] = None) -> str:
    """取本次调用真实服务模型名：优先降级标记，其次响应体 model，最后请求时的模型名。"""
    marked = getattr(response, ACTUAL_MODEL_ATTR, None)
    if marked:
        return str(marked)
    body_model = getattr(response, "model", None)
    if body_model:
        return str(body_model)
    return str(requested or "")


def fallback_reason(response: Any) -> str:
    return str(getattr(response, FALLBACK_REASON_ATTR, "") or "")


class _CompletionsProxy:
    """代理 completions.create，主模型失败或异常时自动切换备用 client 并替换 model 名。"""

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

    def _prepare_backup_kwargs(self, kwargs: dict) -> dict:
        backup_kwargs = dict(kwargs)
        if self._backup_model and "model" in backup_kwargs:
            backup_kwargs["model"] = self._backup_model
        # 移除 reasoning_effort，避免对端网关报 400 (例如 none 不合法)
        backup_kwargs.pop("reasoning_effort", None)
        # 移除 stream_options 避免网关兼容性问题
        backup_kwargs.pop("stream_options", None)
        return backup_kwargs

    async def create(self, *args: Any, **kwargs: Any):
        if not self._backup:
            return await self._primary.chat.completions.create(*args, **kwargs)

        is_stream = bool(kwargs.get("stream"))
        if is_stream:
            return self._stream_with_fallback(*args, **kwargs)

        try:
            return await self._primary.chat.completions.create(*args, **kwargs)
        except Exception as e:
            backup_kwargs = self._prepare_backup_kwargs(kwargs)
            reason = f"{type(e).__name__}: {e}"
            logger.warning(
                f"[{self._tag}] 主模型调用失败 ({reason}); "
                f"正在自动切换至备用模型: {self._backup_model}"
            )
            print(
                f"[{self._tag}] primary failed ({type(e).__name__}: {e}); "
                f"switching to backup model={self._backup_model}"
            )
            response = await self._backup.chat.completions.create(*args, **backup_kwargs)
            return mark_fallback_response(response, self._backup_model, reason)

    async def _stream_with_fallback(self, *args: Any, **kwargs: Any) -> AsyncGenerator:
        """流式 fallback 生成器：在建连或首包阶段失败时自动无缝降级到备用模型。"""
        streamed_any = False
        try:
            primary_stream = await self._primary.chat.completions.create(*args, **kwargs)
            async for chunk in primary_stream:
                streamed_any = True
                yield chunk
        except Exception as e:
            if streamed_any:
                logger.error(f"[{self._tag}] 主模型流式传输中途中断 ({type(e).__name__}: {e})")
                raise

            backup_kwargs = self._prepare_backup_kwargs(kwargs)
            logger.warning(
                f"[{self._tag}] 主模型流式连接失败 ({type(e).__name__}: {e}); "
                f"正在自动降级切换至备用模型: {self._backup_model}"
            )
            print(
                f"[{self._tag}] primary stream failed ({type(e).__name__}: {e}); "
                f"switching to backup model={self._backup_model}"
            )
            backup_stream = await self._backup.chat.completions.create(*args, **backup_kwargs)
            async for chunk in backup_stream:
                yield chunk


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
    """AsyncOpenAI 包装类：主模型异常/超时/限流自动切换备用模型。

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
        return getattr(self._primary, name)


def create_main_llm_client() -> LLMClientWithFallback:
    """创建主 LLM 客户端，配置了备用模型时自动启用降级。"""
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
    """创建 AI 文档解析 LLM 客户端，配置了备用模型时自动启用降级。"""
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
