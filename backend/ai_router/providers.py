"""providers.py — 各 provider 的具体实现

按 provider_type 路由:
  - "openai"    → OpenAICompatibleProvider (OpenAI/DeepSeek/GLM/自定义OpenAI兼容)
  - "anthropic" → AnthropicProvider (Claude)
  - "custom"    → 按 OpenAI 兼容处理 (大多数第三方都是)
"""
import httpx
from typing import Optional

from .base import BaseProvider, AIResponse, AIMessage, ProviderError
from .config import ProviderConfig


# ============================================================
# OpenAI 兼容 Provider
# 适用于: OpenAI / DeepSeek / GLM / 其他 OpenAI 兼容 API
# ============================================================
class OpenAICompatibleProvider(BaseProvider):
    """OpenAI /v1/chat/completions 兼容接口"""

    def call(
        self,
        messages: list[AIMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> AIResponse:
        m = self._resolve_model(model)
        temp = self._resolve_temperature(temperature)
        max_tok = self._resolve_max_tokens(max_tokens)

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        # 合并额外请求头
        headers.update(self.config.extra_headers)

        payload = {
            "model": m,
            "messages": [{"role": msg.role, "content": msg.content} for msg in messages],
            "temperature": temp,
            "max_tokens": max_tok,
        }
        # JSON 模式: OpenAI 兼容接口用 response_format
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=self.config.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise ProviderError(self.config.name, f"请求超时 ({self.config.timeout}s)")
        except httpx.ConnectError as e:
            raise ProviderError(self.config.name, f"连接失败: {e}")

        if resp.status_code != 200:
            raise ProviderError(
                self.config.name,
                f"HTTP {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )

        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})

        return self._build_response(
            text=text,
            model=m,
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            raw=data,
        )


# ============================================================
# Anthropic Provider (Claude)
# ============================================================
class AnthropicProvider(BaseProvider):
    """Anthropic Messages API"""

    # Anthropic 要求的 header 版本
    _ANTHROPIC_VERSION = "2023-06-01"

    def call(
        self,
        messages: list[AIMessage],
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> AIResponse:
        m = self._resolve_model(model)
        temp = self._resolve_temperature(temperature)
        max_tok = self._resolve_max_tokens(max_tokens)

        url = f"{self.config.base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": self._ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        headers.update(self.config.extra_headers)

        # Anthropic 要求 system 消息分离
        system_text = ""
        chat_messages = []
        for msg in messages:
            if msg.role == "system":
                system_text += msg.content + "\n"
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})

        # JSON 模式: 在 system prompt 追加约束
        if json_mode and system_text:
            system_text += "\n请仅输出 JSON, 不要 Markdown 代码块。"
        elif json_mode and not system_text:
            system_text = "请仅输出 JSON, 不要 Markdown 代码块。"

        payload = {
            "model": m,
            "max_tokens": max_tok,
            "temperature": temp,
            "messages": chat_messages,
        }
        if system_text.strip():
            payload["system"] = system_text.strip()

        try:
            with httpx.Client(timeout=self.config.timeout) as client:
                resp = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise ProviderError(self.config.name, f"请求超时 ({self.config.timeout}s)")
        except httpx.ConnectError as e:
            raise ProviderError(self.config.name, f"连接失败: {e}")

        if resp.status_code != 200:
            raise ProviderError(
                self.config.name,
                f"HTTP {resp.status_code}: {resp.text[:300]}",
                status_code=resp.status_code,
            )

        data = resp.json()
        # Anthropic 响应: content[0].text
        text = data["content"][0]["text"]
        usage = data.get("usage", {})

        return self._build_response(
            text=text,
            model=m,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            raw=data,
        )


# ============================================================
# Provider 工厂
# ============================================================
def create_provider(config: ProviderConfig) -> BaseProvider:
    """根据 config.provider_type 创建对应的 provider 实例"""
    ptype = config.provider_type.lower()
    if ptype == "anthropic":
        return AnthropicProvider(config)
    elif ptype in ("openai", "custom"):
        return OpenAICompatibleProvider(config)
    else:
        # 默认按 OpenAI 兼容处理
        return OpenAICompatibleProvider(config)
