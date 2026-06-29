"""config.py — Provider 配置管理

支持两种配置方式:
  1. 环境变量 (启动时自动加载, 向后兼容)
  2. 运行时动态配置 (通过 API 添加/删除 provider)

配置文件路径: ai_router/providers.json (运行时动态配置持久化)
"""
import os
import json
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

# 动态配置持久化文件
_CONFIG_FILE = Path(__file__).parent / "providers.json"


@dataclass
class ProviderConfig:
    """单个 provider 的配置"""
    name: str                                   # 唯一标识, 如 "deepseek"
    provider_type: str                          # "openai" | "anthropic" | "custom"
    base_url: str                               # API Base URL
    api_key: str                                # API Key
    model: str                                  # 默认模型名
    priority: int = 100                         # 路由优先级 (越小越优先)
    enabled: bool = True                        # 是否启用
    max_tokens: int = 4096                      # 默认最大输出 token
    temperature: float = 0.4                    # 默认温度
    timeout: int = 90                           # 请求超时秒数
    extra_headers: dict = field(default_factory=dict)  # 额外请求头


def _load_env_providers() -> list[ProviderConfig]:
    """从环境变量加载内置 provider 配置"""
    providers = []

    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        providers.append(ProviderConfig(
            name="openai",
            provider_type="openai",
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            priority=10,
        ))

    # DeepSeek (OpenAI 兼容)
    if os.getenv("DEEPSEEK_API_KEY"):
        providers.append(ProviderConfig(
            name="deepseek",
            provider_type="openai",
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            priority=20,
        ))

    # GLM / 智谱 (OpenAI 兼容)
    if os.getenv("GLM_API_KEY"):
        providers.append(ProviderConfig(
            name="glm",
            provider_type="openai",
            base_url=os.getenv("GLM_BASE_URL", "https://open.bigmodel.cn/api/paas/v4"),
            api_key=os.getenv("GLM_API_KEY"),
            model=os.getenv("GLM_MODEL", "glm-4"),
            priority=30,
        ))

    # Claude / Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        providers.append(ProviderConfig(
            name="claude",
            provider_type="anthropic",
            base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            api_key=os.getenv("ANTHROPIC_API_KEY"),
            model=os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
            priority=40,
        ))

    # 自定义第三方 (通过环境变量 CUSTOM_AI_* 配置)
    if os.getenv("CUSTOM_AI_API_KEY"):
        providers.append(ProviderConfig(
            name=os.getenv("CUSTOM_AI_NAME", "custom"),
            provider_type=os.getenv("CUSTOM_AI_TYPE", "openai"),
            base_url=os.getenv("CUSTOM_AI_BASE_URL", ""),
            api_key=os.getenv("CUSTOM_AI_API_KEY"),
            model=os.getenv("CUSTOM_AI_MODEL", ""),
            priority=50,
        ))

    return providers


def _load_dynamic_providers() -> list[ProviderConfig]:
    """从 providers.json 加载运行时添加的 provider"""
    if not _CONFIG_FILE.exists():
        return []
    try:
        data = json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        return [ProviderConfig(**item) for item in data]
    except Exception as e:
        print(f"[config] 加载 providers.json 失败: {e}")
        return []


def _save_dynamic_providers(providers: list[ProviderConfig]):
    """持久化动态 provider 到 providers.json"""
    data = [asdict(p) for p in providers]
    _CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_all_providers() -> list[ProviderConfig]:
    """获取所有 provider (环境变量 + 动态配置)

    同名 provider 以动态配置优先 (覆盖环境变量)
    """
    env_providers = _load_env_providers()
    dyn_providers = _load_dynamic_providers()

    # 动态配置覆盖同名环境变量配置
    dyn_names = {p.name for p in dyn_providers}
    merged = [p for p in env_providers if p.name not in dyn_names] + dyn_providers

    # 按 priority 排序
    return sorted(merged, key=lambda p: p.priority)


def get_provider(name: str) -> Optional[ProviderConfig]:
    """按 name 查单个 provider"""
    for p in get_all_providers():
        if p.name == name:
            return p
    return None


def add_provider(config: ProviderConfig) -> ProviderConfig:
    """添加或更新一个 provider (动态配置)

    若 name 已存在则更新, 否则添加
    """
    dyn_providers = _load_dynamic_providers()
    # 移除同名旧配置
    dyn_providers = [p for p in dyn_providers if p.name != config.name]
    dyn_providers.append(config)
    _save_dynamic_providers(dyn_providers)
    return config


def remove_provider(name: str) -> bool:
    """删除一个动态 provider (环境变量配置的不可删)

    Returns: True 删除成功, False 不存在
    """
    dyn_providers = _load_dynamic_providers()
    before = len(dyn_providers)
    dyn_providers = [p for p in dyn_providers if p.name != name]
    if len(dyn_providers) < before:
        _save_dynamic_providers(dyn_providers)
        return True
    return False


def list_provider_summaries() -> list[dict]:
    """返回 provider 列表摘要 (隐藏 api_key)"""
    result = []
    for p in get_all_providers():
        d = asdict(p)
        d["api_key"] = "***" + d["api_key"][-4:] if len(d["api_key"]) > 4 else "***"
        d["source"] = "env" if p.name in [e.name for e in _load_env_providers()] else "dynamic"
        result.append(d)
    return result
