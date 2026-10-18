"""AsyncOpenAI 包装类：主 LLM 遇到异常/超时/429/500/断连时自动无缝切换备用模型。

用法（替换原 AsyncOpenAI(...) 即可，其余代码不变）：

    from app.utils.llm_fallback import create_main_llm_client

    self.client = create_main_llm_client()
    # 调用代码完全不变，支持普通与流式模式：
    response = await self.client.chat.completions.create(model=..., messages=...)
"""
import logging
import time
from dataclasses import dataclass
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


@dataclass
class FallbackTarget:
    client: AsyncOpenAI
    model: str
    reasoning_effort: Optional[str] = None
    name: str = "fallback"
    # 该备用目标是否优先于主模型使用（主模型长期限流时的"事实主力"）。
    preferred_first: bool = False


# 主模型熔断状态（进程内，按 tag 隔离）。
# 主模型配额耗尽（429）时每个请求都先打一次主模型、失败后再走备用链路，
# 实测每次白付 1.7~2.3 秒。这里记录"冷却截止时刻"：冷却期内直接走备用，
# 冷却结束后再放一个请求去试探主模型（半开），成功即恢复主链路。
_PRIMARY_COOLDOWN_UNTIL: dict[str, float] = {}
_PRIMARY_COOLDOWN_SECONDS = 60.0


class _CompletionsProxy:
    """代理 completions.create，主模型失败或异常时自动按优先级尝试备用 client 链。"""

    def __init__(
        self,
        primary: AsyncOpenAI,
        backups: list[FallbackTarget],
        tag: str = "LLM-Fallback",
        primary_reasoning_effort: Optional[str] = None,
    ):
        self._primary = primary
        self._backups = backups
        self._tag = tag
        self._primary_reasoning_effort = primary_reasoning_effort

    def _primary_available(self) -> bool:
        until = _PRIMARY_COOLDOWN_UNTIL.get(self._tag, 0.0)
        return time.monotonic() >= until

    def _trip_primary_breaker(self) -> None:
        _PRIMARY_COOLDOWN_UNTIL[self._tag] = time.monotonic() + _PRIMARY_COOLDOWN_SECONDS

    def _reset_primary_breaker(self) -> None:
        _PRIMARY_COOLDOWN_UNTIL.pop(self._tag, None)

    @property
    def _preferred_backups(self) -> list[FallbackTarget]:
        return [t for t in self._backups if t.preferred_first]

    def _cooldown_chain(self) -> list[FallbackTarget]:
        """冷却期的尝试顺序：首选备用优先，其余备用随后（去重）。"""
        ordered = self._preferred_backups + [
            t for t in self._backups if not t.preferred_first
        ]
        return ordered

    async def _call_preferred(self, args: tuple, kwargs: dict):
        last_exc: Exception | None = None
        for target in self._cooldown_chain():
            try:
                target_kwargs = self._prepare_target_kwargs(target, kwargs)
                print(
                    f"[{self._tag}] 主模型冷却中，直接使用备用 {target.name} "
                    f"({target.model}, reasoning_effort={target.reasoning_effort})"
                )
                response = await target.client.chat.completions.create(
                    *args, **target_kwargs
                )
                return mark_fallback_response(
                    response, target.model, "primary cooldown"
                )
            except Exception as exc:
                last_exc = exc
                print(f"[{self._tag}] 备用 {target.name} 失败: {exc}")
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("no backup configured")

    async def _stream_preferred(self, args: tuple, kwargs: dict):
        last_exc: Exception | None = None
        for target in self._cooldown_chain():
            try:
                target_kwargs = self._prepare_target_kwargs(target, kwargs)
                print(
                    f"[{self._tag}] 主模型冷却中，流式直接使用备用 {target.name} "
                    f"({target.model}, reasoning_effort={target.reasoning_effort})"
                )
                stream = await target.client.chat.completions.create(
                    *args, **target_kwargs
                )
                async for chunk in stream:
                    yield chunk
                return
            except Exception as exc:
                last_exc = exc
                print(f"[{self._tag}] 备用流 {target.name} 失败: {exc}")
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("no backup configured")

    def _primary_kwargs(self, kwargs: dict) -> dict:
        """主模型调用参数：按配置注入思考强度。

        由 ``LLM_ENABLE_THINKING`` / ``LLM_REASONING_EFFORT`` 控制，默认开启且为
        medium。注意：**不要**为了缩短首包而默认关闭思考——DeepSeek 系列的
        判定/建议质量依赖思考，关闭会明显影响效果。
        只有显式把开关设为 False 时才传 ``none``（不传的话网关会回落到默认思考，
        "关闭"会变成空操作）。
        """
        primary_kwargs = dict(kwargs)
        if self._primary_reasoning_effort:
            primary_kwargs.setdefault("reasoning_effort", self._primary_reasoning_effort)
        return primary_kwargs

    @property
    def _backup(self) -> Optional[AsyncOpenAI]:
        return self._backups[0].client if self._backups else None

    @property
    def _backup_model(self) -> Optional[str]:
        return self._backups[0].model if self._backups else None

    def _prepare_target_kwargs(self, target: FallbackTarget, kwargs: dict) -> dict:
        target_kwargs = dict(kwargs)
        if target.model:
            target_kwargs["model"] = target.model
        if target.reasoning_effort:
            target_kwargs["reasoning_effort"] = target.reasoning_effort
        else:
            target_kwargs.pop("reasoning_effort", None)
        # 移除 stream_options 避免对端网关兼容性问题
        target_kwargs.pop("stream_options", None)
        return target_kwargs

    async def create(self, *args: Any, **kwargs: Any):
        if not self._backups:
            return await self._primary.chat.completions.create(
                *args, **self._primary_kwargs(kwargs)
            )

        is_stream = bool(kwargs.get("stream"))
        if is_stream:
            return self._stream_with_fallback(*args, **kwargs)

        primary_reason = "primary cooldown (recent rate limit)"
        if not self._primary_available() and self._preferred_backups:
            # 主模型处于限流冷却期：直接把"首选备用"当作主模型调用，
            # 跳过必然会失败的备用链头部（实测备用 #1 首包 2.8~26s）。
            return await self._call_preferred(args, kwargs)
        if self._primary_available():
            try:
                response = await self._primary.chat.completions.create(
                    *args, **self._primary_kwargs(kwargs)
                )
                self._reset_primary_breaker()
                return response
            except Exception as e:
                primary_reason = f"{type(e).__name__}: {e}"
                if isinstance(e, RateLimitError):
                    self._trip_primary_breaker()
                    print(
                        f"[{self._tag}] 主模型触发限流，{_PRIMARY_COOLDOWN_SECONDS:.0f}s 内直接走备用链路"
                    )

        logger.warning(
            f"[{self._tag}] 主模型调用失败 ({primary_reason})，开始尝试备用链路..."
        )
        print(f"[{self._tag}] primary failed ({primary_reason}); initiating fallback chain...")

        last_exc: Exception = RuntimeError(primary_reason)
        for idx, target in enumerate(self._backups, start=1):
            try:
                target_kwargs = self._prepare_target_kwargs(target, kwargs)
                logger.warning(
                    f"[{self._tag}] 正在自动切换至第 {idx} 备用模型: {target.name} ({target.model}), "
                    f"reasoning_effort={target.reasoning_effort}"
                )
                print(
                    f"[{self._tag}] switching to fallback #{idx} ({target.name}): "
                    f"model={target.model}, reasoning_effort={target.reasoning_effort}"
                )
                response = await target.client.chat.completions.create(*args, **target_kwargs)
                return mark_fallback_response(response, target.model, primary_reason)
            except Exception as fb_exc:
                last_exc = fb_exc
                fb_reason = f"{type(fb_exc).__name__}: {fb_exc}"
                logger.warning(
                    f"[{self._tag}] 第 {idx} 备用模型 ({target.model}) 调用失败: {fb_reason}"
                )
                print(f"[{self._tag}] fallback #{idx} ({target.model}) failed: {fb_reason}")

        raise last_exc

    async def _stream_with_fallback(self, *args: Any, **kwargs: Any) -> AsyncGenerator:
        """流式 fallback 生成器：在建连或首包阶段失败时自动无缝降级到备用模型链。"""
        streamed_any = False
        primary_error: Optional[Exception] = None
        if not self._primary_available() and self._preferred_backups:
            async for chunk in self._stream_preferred(args, kwargs):
                streamed_any = True
                yield chunk
            return
        if self._primary_available():
            try:
                primary_stream = await self._primary.chat.completions.create(
                    *args, **self._primary_kwargs(kwargs)
                )
                async for chunk in primary_stream:
                    streamed_any = True
                    yield chunk
                self._reset_primary_breaker()
                return
            except Exception as e:
                primary_error = e
                if isinstance(e, RateLimitError):
                    self._trip_primary_breaker()
                    print(
                        f"[{self._tag}] 主模型触发限流，{_PRIMARY_COOLDOWN_SECONDS:.0f}s 内直接走备用链路"
                    )
        e = primary_error or RuntimeError("primary cooldown (recent rate limit)")
        if streamed_any:
            logger.error(f"[{self._tag}] 主模型流式传输中途中断 ({type(e).__name__}: {e})")
            raise e

        primary_reason = f"{type(e).__name__}: {e}"
        logger.warning(
            f"[{self._tag}] 主模型流式连接失败 ({primary_reason})，开始尝试备用链路..."
        )
        print(f"[{self._tag}] primary stream failed ({primary_reason}); initiating fallback chain...")

        last_exc: Exception = e
        for idx, target in enumerate(self._backups, start=1):
            try:
                target_kwargs = self._prepare_target_kwargs(target, kwargs)
                logger.warning(
                    f"[{self._tag}] 正在自动降级切换至第 {idx} 备用流: {target.name} ({target.model}), "
                    f"reasoning_effort={target.reasoning_effort}"
                )
                print(
                    f"[{self._tag}] switching to fallback stream #{idx} ({target.name}): "
                    f"model={target.model}, reasoning_effort={target.reasoning_effort}"
                )
                backup_stream = await target.client.chat.completions.create(*args, **target_kwargs)
                async for chunk in backup_stream:
                    streamed_any = True
                    yield chunk
                return
            except Exception as fb_exc:
                if streamed_any:
                    logger.error(f"[{self._tag}] 备用模型 #{idx} 流式传输中途中断: {fb_exc}")
                    raise
                last_exc = fb_exc
                print(f"[{self._tag}] fallback stream #{idx} ({target.model}) failed: {fb_exc}")

        raise last_exc


class _ChatProxy:
    def __init__(
        self,
        primary: AsyncOpenAI,
        backups: list[FallbackTarget],
        tag: str = "LLM-Fallback",
        primary_reasoning_effort: Optional[str] = None,
    ):
        self.completions = _CompletionsProxy(
            primary, backups, tag, primary_reasoning_effort
        )


class LLMClientWithFallback:
    """AsyncOpenAI 包装类：主模型异常/超时/限流自动多级降级备用模型。

    代理 chat.completions.create 调用，其他属性转发给 primary。
    """

    def __init__(
        self,
        primary: AsyncOpenAI,
        backups: Optional[list[FallbackTarget]] = None,
        tag: str = "LLM-Fallback",
        backup: Optional[AsyncOpenAI] = None,
        backup_model: Optional[str] = None,
        primary_reasoning_effort: Optional[str] = None,
    ):
        self._primary = primary
        target_list: list[FallbackTarget] = list(backups or [])
        if not target_list and backup and backup_model:
            target_list.append(
                FallbackTarget(
                    client=backup,
                    model=backup_model,
                    reasoning_effort="none",
                    name="LegacyBackup",
                )
            )
        self._backups = target_list
        self.chat = _ChatProxy(
            primary, self._backups, tag, primary_reasoning_effort
        )

    @property
    def _backup(self) -> Optional[AsyncOpenAI]:
        return self._backups[0].client if self._backups else None

    @property
    def _backup_model(self) -> Optional[str]:
        return self._backups[0].model if self._backups else None

    def __getattr__(self, name: str):
        return getattr(self._primary, name)


def create_main_llm_client() -> LLMClientWithFallback:
    """创建主 LLM 客户端，配置了多级备用模型时自动启用按序降级。

    备用顺序沿用项目既定配置：先同供应商的 SenseNova flash-lite（独立配额抗 429），
    再跨供应商的 EdgeFN DeepSeek-V4-Flash（容灾兜底）。
    """
    primary = AsyncOpenAI(
        base_url=settings.LLM_BASE_URL,
        api_key=settings.LLM_API_KEY,
        timeout=settings.LLM_TIMEOUT,
    )
    backups: list[FallbackTarget] = []

    # 第 1 备用：商汤 sensenova-6.8-flash-lite，独立配额抗 429，思考模式 medium
    if settings.has_llm_fallback1:
        client1 = AsyncOpenAI(
            base_url=settings.LLM_FALLBACK1_BASE_URL,
            api_key=settings.LLM_FALLBACK1_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        backups.append(
            FallbackTarget(
                client=client1,
                model=settings.LLM_FALLBACK1_MODEL,
                reasoning_effort=settings.LLM_FALLBACK1_REASONING_EFFORT,
                name="SenseNova-Fallback1",
            )
        )
        print(
            f"[LLM-Fallback] #1 backup configured: "
            f"{settings.LLM_FALLBACK1_BASE_URL} / {settings.LLM_FALLBACK1_MODEL} "
            f"(reasoning_effort={settings.LLM_FALLBACK1_REASONING_EFFORT})"
        )

    # 第 2 备用：EdgeFN DeepSeek-V4-Flash，跨供应商容灾
    if settings.has_llm_fallback2:
        client2 = AsyncOpenAI(
            base_url=settings.LLM_FALLBACK2_BASE_URL,
            api_key=settings.LLM_FALLBACK2_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        backups.append(
            FallbackTarget(
                client=client2,
                model=settings.LLM_FALLBACK2_MODEL,
                reasoning_effort=settings.LLM_FALLBACK2_REASONING_EFFORT,
                name="EdgeFN-Fallback2",
            )
        )
        print(
            f"[LLM-Fallback] #2 backup configured: "
            f"{settings.LLM_FALLBACK2_BASE_URL} / {settings.LLM_FALLBACK2_MODEL} "
            f"(reasoning_effort={settings.LLM_FALLBACK2_REASONING_EFFORT})"
        )
    elif settings.has_llm_backup and not backups:
        client_legacy = AsyncOpenAI(
            base_url=settings.LLM_BACKUP_BASE_URL,
            api_key=settings.LLM_BACKUP_API_KEY,
            timeout=settings.LLM_TIMEOUT,
        )
        backups.append(
            FallbackTarget(
                client=client_legacy,
                model=settings.LLM_BACKUP_MODEL,
                reasoning_effort="none",
                name="Legacy-Backup",
            )
        )

    return LLMClientWithFallback(
        primary=primary,
        backups=backups,
        tag="LLM-Fallback",
        primary_reasoning_effort=settings.effective_llm_reasoning_effort,
    )


def create_ai_extract_llm_client() -> LLMClientWithFallback:
    """创建 AI 文档解析 LLM 客户端，配置了多级备用模型时自动启用按序降级。"""
    primary_timeout = httpx.Timeout(connect=15.0, read=600.0, write=60.0, pool=15.0)
    primary = AsyncOpenAI(
        base_url=settings.AI_EXTRACT_LLM_BASE_URL,
        api_key=settings.AI_EXTRACT_LLM_API_KEY,
        timeout=primary_timeout,
    )
    backups: list[FallbackTarget] = []

    # 第 1 备用：商汤 sensenova-6.8-flash-lite，思考模式 medium
    if settings.has_ai_extract_llm_fallback1:
        client1 = AsyncOpenAI(
            base_url=settings.AI_EXTRACT_LLM_FALLBACK1_BASE_URL,
            api_key=settings.AI_EXTRACT_LLM_FALLBACK1_API_KEY,
            timeout=primary_timeout,
        )
        backups.append(
            FallbackTarget(
                client=client1,
                model=settings.AI_EXTRACT_LLM_FALLBACK1_MODEL,
                reasoning_effort=settings.AI_EXTRACT_LLM_FALLBACK1_REASONING_EFFORT,
                name="SenseNova-AIExtract-Fallback1",
            )
        )
        print(
            f"[AIExtract-Fallback] #1 backup configured: "
            f"{settings.AI_EXTRACT_LLM_FALLBACK1_BASE_URL} / "
            f"{settings.AI_EXTRACT_LLM_FALLBACK1_MODEL} "
            f"(reasoning_effort={settings.AI_EXTRACT_LLM_FALLBACK1_REASONING_EFFORT})"
        )

    # 第 2 备用：EdgeFN DeepSeek-V4-Flash，关闭思考模式快速响应
    if settings.has_ai_extract_llm_fallback2:
        client2 = AsyncOpenAI(
            base_url=settings.AI_EXTRACT_LLM_FALLBACK2_BASE_URL,
            api_key=settings.AI_EXTRACT_LLM_FALLBACK2_API_KEY,
            timeout=primary_timeout,
        )
        backups.append(
            FallbackTarget(
                client=client2,
                model=settings.AI_EXTRACT_LLM_FALLBACK2_MODEL,
                reasoning_effort=settings.AI_EXTRACT_LLM_FALLBACK2_REASONING_EFFORT,
                name="EdgeFN-AIExtract-Fallback2",
            )
        )
        print(
            f"[AIExtract-Fallback] #2 backup configured: "
            f"{settings.AI_EXTRACT_LLM_FALLBACK2_BASE_URL} / "
            f"{settings.AI_EXTRACT_LLM_FALLBACK2_MODEL} "
            f"(reasoning_effort={settings.AI_EXTRACT_LLM_FALLBACK2_REASONING_EFFORT})"
        )
    elif settings.has_ai_extract_llm_backup and not backups:
        client_legacy = AsyncOpenAI(
            base_url=settings.AI_EXTRACT_LLM_BACKUP_BASE_URL,
            api_key=settings.AI_EXTRACT_LLM_BACKUP_API_KEY,
            timeout=primary_timeout,
        )
        backups.append(
            FallbackTarget(
                client=client_legacy,
                model=settings.AI_EXTRACT_LLM_BACKUP_MODEL,
                reasoning_effort="none",
                name="Legacy-AIExtract-Backup",
            )
        )

    # AI 文档抽取对结构还原质量敏感，默认保留其思考配置
    # （AI_EXTRACT_LLM_REASONING_EFFORT），不套用主对话模型的 none。
    return LLMClientWithFallback(
        primary=primary,
        backups=backups,
        tag="AIExtract-Fallback",
        primary_reasoning_effort=settings.AI_EXTRACT_LLM_REASONING_EFFORT or None,
    )
