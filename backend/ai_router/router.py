"""router.py — 统一 AI 路由器

核心功能:
  1. call()        — 按 model 参数路由到对应 provider
  2. call_auto()   — 自动按 priority 遍历可用 provider, 失败自动切换
  3. call_with_retry() — 带指数退避重试
  4. list_models() — 列出所有可用模型
"""
import time
from typing import Optional
from dataclasses import asdict

from .base import BaseProvider, AIResponse, AIMessage, ProviderError
from .config import get_all_providers, get_provider, ProviderConfig
from .providers import create_provider


class AIRouter:
    """统一 AI 路由器 (单例)"""

    def __init__(self):
        self._provider_cache: dict[str, BaseProvider] = {}

    def _get_provider_instance(self, config: ProviderConfig) -> BaseProvider:
        """获取或创建 provider 实例 (缓存)"""
        if config.name not in self._provider_cache:
            self._provider_cache[config.name] = create_provider(config)
        return self._provider_cache[config.name]

    def list_models(self) -> list[dict]:
        """列出所有可用模型"""
        models = []
        for cfg in get_all_providers():
            if not cfg.enabled:
                continue
            models.append({
                "id": cfg.name,
                "label": f"{cfg.name} ({cfg.model})",
                "provider": cfg.name,
                "model": cfg.model,
                "base_url": cfg.base_url,
                "priority": cfg.priority,
            })
        return models

    def list_providers(self) -> list[dict]:
        """列出所有 provider (含状态)"""
        from .config import list_provider_summaries
        return list_provider_summaries()

    # ============================================================
    # 核心: 指定 provider 调用
    # ============================================================
    def call(
        self,
        messages: list[AIMessage],
        model: str = "auto",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> AIResponse:
        """指定 provider 调用

        Args:
            model: provider 名 (如 "deepseek") 或 "auto"
                   也可传具体模型名 (如 "gpt-4o"), 会自动匹配
        """
        if model == "auto":
            return self.call_auto(
                messages, temperature, max_tokens, json_mode
            )

        # 按 name 匹配 provider
        cfg = get_provider(model)
        if cfg:
            if not cfg.enabled:
                raise ProviderError(model, "provider 已禁用")
            return self._call_single(cfg, messages, None, temperature, max_tokens, json_mode)

        # 按 model 名模糊匹配 (用户传了具体模型名)
        for cfg in get_all_providers():
            if cfg.model == model or cfg.name == model:
                return self._call_single(cfg, messages, model, temperature, max_tokens, json_mode)

        raise ProviderError(model, f"找不到 provider 或模型: {model}")

    # ============================================================
    # 自动切换: 按 priority 遍历, 失败切下一个
    # ============================================================
    def call_auto(
        self,
        messages: list[AIMessage],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> AIResponse:
        """自动选择 provider, 失败按 priority 切换"""
        providers = [p for p in get_all_providers() if p.enabled]
        if not providers:
            raise ProviderError("auto", "没有可用的 provider")

        last_error = None
        for cfg in providers:
            try:
                return self._call_single(
                    cfg, messages, None, temperature, max_tokens, json_mode
                )
            except ProviderError as e:
                last_error = e
                print(f"[router] provider {cfg.name} 失败: {e}, 切换下一个...")
                continue

        raise ProviderError(
            "auto",
            f"所有 provider 均失败, 最后错误: {last_error}",
        )

    # ============================================================
    # 带重试的调用 (指数退避)
    # ============================================================
    def call_with_retry(
        self,
        messages: list[AIMessage],
        model: str = "auto",
        max_retries: int = 3,
        retry_delay: float = 1.0,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        json_mode: bool = False,
    ) -> AIResponse:
        """带指数退避重试

        策略:
          - 重试时自动切换 provider (若 model=auto)
          - 指数退避: delay * 2^attempt
          - 最后一次失败抛出异常
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                if model == "auto":
                    # auto 模式: 每次重试都可能切到不同 provider
                    return self.call_auto(messages, temperature, max_tokens, json_mode)
                else:
                    return self.call(messages, model, temperature, max_tokens, json_mode)
            except ProviderError as e:
                last_error = e
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    print(
                        f"[router] 第 {attempt + 1} 次失败 ({e}), "
                        f"{delay:.1f}s 后重试..."
                    )
                    time.sleep(delay)

        raise last_error

    # ============================================================
    # 内部: 调用单个 provider
    # ============================================================
    def _call_single(
        self,
        cfg: ProviderConfig,
        messages: list[AIMessage],
        model_override: Optional[str],
        temperature: Optional[float],
        max_tokens: Optional[int],
        json_mode: bool,
    ) -> AIResponse:
        """调用单个 provider, 记录耗时"""
        provider = self._get_provider_instance(cfg)
        start = time.time()

        resp = provider.call(
            messages=messages,
            model=model_override,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
        )

        resp.latency_ms = int((time.time() - start) * 1000)
        return resp


# ============================================================
# 单例
# ============================================================
_router: Optional[AIRouter] = None


def get_router() -> AIRouter:
    """获取路由器单例"""
    global _router
    if _router is None:
        _router = AIRouter()
    return _router
