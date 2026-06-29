"""base.py — 统一接口定义与响应数据类"""
import json
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional

from .config import ProviderConfig


@dataclass
class AIMessage:
    """统一消息格式"""
    role: str                               # "system" | "user" | "assistant"
    content: str


@dataclass
class AIResponse:
    """统一响应格式 — 所有 provider 返回这个"""
    content: str                            # 原始文本响应
    json_content: Optional[dict] = None     # 解析后的 JSON (若响应是 JSON)
    provider: str = ""                     # provider 名
    model: str = ""                        # 实际模型名
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0                    # 耗时毫秒
    raw: Optional[dict] = None             # 原始响应 (调试用)


class BaseProvider(ABC):
    """Provider 抽象基类

    所有 provider 实现 call() 方法, 输入统一, 输出统一
    """

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    def call(
        self,
        messages: list[AIMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> AIResponse:
        """调用模型

        Args:
            messages:    消息列表
            model:       指定模型 (None 则用 config.model)
            temperature: 温度 (None 则用 config.temperature)
            max_tokens:  最大输出 token (None 则用 config.max_tokens)
            json_mode:   是否强制 JSON 输出
        Returns:
            AIResponse
        """
        ...

    # ---- 公共工具方法 ----

    @staticmethod
    def parse_json(text: str) -> Optional[dict]:
        """容错 JSON 解析: 去除 markdown 代码块包裹"""
        if not text:
            return None
        cleaned = re.sub(
            r"^```(?:json)?\s*\n?|\n?```\s*$",
            "",
            text.strip(),
            flags=re.MULTILINE,
        ).strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return None

    def _build_response(
        self,
        text: str,
        model: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        raw: Optional[dict] = None,
        latency_ms: int = 0,
    ) -> AIResponse:
        """构造统一响应 (自动尝试 JSON 解析)"""
        return AIResponse(
            content=text,
            json_content=self.parse_json(text),
            provider=self.config.name,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            raw=raw,
        )

    def _resolve_model(self, model: Optional[str]) -> str:
        return model or self.config.model

    def _resolve_temperature(self, temperature: Optional[float]) -> float:
        return temperature if temperature is not None else self.config.temperature

    def _resolve_max_tokens(self, max_tokens: Optional[int]) -> int:
        return max_tokens or self.config.max_tokens


class ProviderError(Exception):
    """Provider 调用异常"""

    def __init__(self, provider: str, message: str, status_code: int = 0):
        self.provider = provider
        self.status_code = status_code
        super().__init__(f"[{provider}] {message}")
