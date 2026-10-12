"""统一 LLM 调用网关。

目标：把散落在 agent_service / evidence_agent_service / audit_agent 里三份重复的
「建客户端 + 调 create + 记 LLMCallLog」收敛到一处，并引入：

1. **模型分层**（LLMTier）：简单意图走 cheap，常规推理走 standard，多模态走 vision。
2. **统一记账**：无论谁调用，都以一致字段写入 LLMCallLog（成本可观测的前提）。
3. **一致的 JSON 解析/修复**：结构化输出统一走 complete_json。

设计上不强制现有代码立刻迁移——新特性（规划器、多模态融合、反馈回流）全部走网关，
旧路径可按需逐步接入，避免一次性大改动带来的回归风险。
"""

from __future__ import annotations

import json
import re
import time
from enum import Enum
from typing import Any, AsyncGenerator, Optional

from openai import AsyncOpenAI

from app.config import settings
from app.utils.llm_fallback import create_main_llm_client


class LLMTier(str, Enum):
    CHEAP = "cheap"        # 意图分类 / 规划步骤 / 列举——可用小模型
    STANDARD = "standard"  # 对话 / 报告 / 证据判定
    VISION = "vision"      # 多模态（照片）


class LLMGateway:
    def __init__(self) -> None:
        self._text_client = create_main_llm_client()
        # 视觉模型可能是独立 endpoint / key
        self._vision_client = AsyncOpenAI(
            api_key=settings.VISION_LLM_API_KEY or settings.LLM_API_KEY,
            base_url=settings.VISION_LLM_BASE_URL or settings.LLM_BASE_URL,
            timeout=settings.LLM_TIMEOUT,
        )

    def _resolve(self, tier: LLMTier) -> tuple[Any, str]:
        if tier == LLMTier.VISION:
            return self._vision_client, settings.VISION_LLM_MODEL
        if tier == LLMTier.CHEAP:
            return self._text_client, settings.cheap_model
        return self._text_client, settings.standard_model

    async def complete(
        self,
        *,
        messages: list[dict],
        tier: LLMTier = LLMTier.STANDARD,
        call_type: str = "agent_generic",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        json_mode: bool = False,
        db: Any = None,
        user_id: Optional[str] = None,
        record_id: Optional[str] = None,
    ) -> str:
        """一次性补全，返回文本内容，并（若给了 db）统一记账。"""
        client, model = self._resolve(tier)
        started = time.monotonic()
        content = ""
        tokens = 0
        error_text: Optional[str] = None
        try:
            kwargs: dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens or settings.LLM_MAX_TOKENS,
                "temperature": settings.LLM_TEMPERATURE if temperature is None else temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}
            resp = await client.chat.completions.create(**kwargs)
            content = (resp.choices[0].message.content or "") if resp.choices else ""
            tokens = getattr(getattr(resp, "usage", None), "total_tokens", 0) or 0
            return content
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            await self._log(
                db=db, user_id=user_id, record_id=record_id, call_type=call_type,
                model=model, prompt=self._prompt_digest(messages), response=content,
                tokens=tokens, duration_ms=int((time.monotonic() - started) * 1000),
                error_text=error_text,
            )

    async def complete_json(
        self,
        *,
        messages: list[dict],
        tier: LLMTier = LLMTier.STANDARD,
        call_type: str = "agent_json",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        db: Any = None,
        user_id: Optional[str] = None,
    ) -> Any:
        """结构化补全：强制 json_object，返回已解析对象（解析失败抛 ValueError）。"""
        raw = await self.complete(
            messages=messages, tier=tier, call_type=call_type, max_tokens=max_tokens,
            temperature=0.3 if temperature is None else temperature,
            json_mode=True, db=db, user_id=user_id,
        )
        return self._parse_json(raw)

    async def stream(
        self,
        *,
        messages: list[dict],
        tier: LLMTier = LLMTier.STANDARD,
        call_type: str = "agent_stream",
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        db: Any = None,
        user_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """流式补全，逐块 yield 文本；结束后统一记账。"""
        client, model = self._resolve(tier)
        started = time.monotonic()
        collected = ""
        tokens = 0
        error_text: Optional[str] = None
        try:
            stream = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens or settings.LLM_MAX_TOKENS,
                temperature=settings.LLM_TEMPERATURE if temperature is None else temperature,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for chunk in stream:
                usage = getattr(chunk, "usage", None)
                if usage and getattr(usage, "total_tokens", None):
                    tokens = usage.total_tokens
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    collected += delta
                    yield delta
        except Exception as exc:
            error_text = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            await self._log(
                db=db, user_id=user_id, record_id=None, call_type=call_type,
                model=model, prompt=self._prompt_digest(messages), response=collected,
                tokens=tokens, duration_ms=int((time.monotonic() - started) * 1000),
                error_text=error_text,
            )

    # ---- 内部 ----

    @staticmethod
    def _prompt_digest(messages: list[dict]) -> str:
        # 记账里保存最后一条 user 消息即可，避免把整段系统提示反复入库
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return str(msg.get("content", ""))[:8000]
        return json.dumps(messages, ensure_ascii=False)[:8000]

    @staticmethod
    def _parse_json(raw: str) -> Any:
        if not raw or not raw.strip():
            raise ValueError("LLM 返回空内容")
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 去掉 ```json 包裹后重试
            m = re.search(r"```(?:json)?\s*(.+?)```", raw, re.S)
            if m:
                try:
                    return json.loads(m.group(1))
                except json.JSONDecodeError:
                    pass
            # 截取首个 { 到末个 } 的片段兜底
            start, end = raw.find("{"), raw.rfind("}")
            if 0 <= start < end:
                return json.loads(raw[start:end + 1])
            raise ValueError("LLM 返回无法解析为 JSON")

    @staticmethod
    async def _log(
        *, db: Any, user_id: Optional[str], record_id: Optional[str], call_type: str,
        model: str, prompt: str, response: str, tokens: int, duration_ms: int,
        error_text: Optional[str],
    ) -> None:
        if db is None:
            return
        try:
            from app.models.audit import LLMCallLog

            db.add(LLMCallLog(
                user_id=user_id,
                record_id=record_id or None,
                call_type=call_type,
                prompt=prompt,
                response=response,
                model=model,
                tokens_used=tokens,
                duration_ms=duration_ms,
                is_success="false" if error_text else "true",
                error_msg=error_text,
            ))
            await db.flush()
        except Exception as exc:  # 记账失败不能影响主流程
            print(f"[LLMGateway] failed to log call: {exc}")


llm_gateway = LLMGateway()
