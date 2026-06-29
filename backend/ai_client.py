"""ai_client.py - 统一 AI 客户端 (DeepSeek / Claude 可切换)

设计目标:
  - 所有 AI 功能复用同一个客户端, 通过 model 参数选择 provider
  - 统一返回 dict (已解析 JSON) + usage 统计
  - 支持显式指定模型; 也支持 fallback (主模型失败自动切备用)

对外暴露:
  call_ai(prompt, system, model="auto", temperature=0.4) -> AIResponse
"""
import os
import json
import re
import httpx
from dataclasses import dataclass
from anthropic import Anthropic

from dotenv import load_dotenv

# 加载项目根 .env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ============================================================
# 配置
# ============================================================
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

# 客户端单例 (复用连接池)
_http = None
_anthropic = None


def _http_client() -> httpx.Client:
    global _http
    if _http is None:
        _http = httpx.Client(timeout=90.0)
    return _http


def _anthropic_client() -> Anthropic:
    global _anthropic
    if _anthropic is None:
        _anthropic = Anthropic(api_key=ANTHROPIC_API_KEY)
    return _anthropic


# ============================================================
# 响应数据类
# ============================================================
@dataclass
class AIResponse:
    """统一 AI 响应封装"""
    content: dict                          # 已解析的结构化结果
    provider: str                          # 'deepseek' | 'claude'
    model: str                             # 实际使用的模型名
    prompt_tokens: int = 0
    completion_tokens: int = 0


# ============================================================
# JSON 容错解析
# ============================================================
def _parse_json(text: str) -> dict:
    """容错解析: 去掉可能的 ```json 包裹, 再 json.loads"""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


# ============================================================
# 各 provider 调用
# ============================================================
def _call_deepseek(prompt: str, system: str, model: str, temperature: float) -> AIResponse:
    """调用 DeepSeek (OpenAI 兼容接口), 强制 JSON 输出"""
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY")

    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},  # 强制 JSON
    }
    resp = _http_client().post(url, headers=headers, json=payload)
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return AIResponse(
        content=_parse_json(text),
        provider="deepseek",
        model=model,
        prompt_tokens=usage.get("prompt_tokens", 0),
        completion_tokens=usage.get("completion_tokens", 0),
    )


def _call_claude(prompt: str, system: str, model: str, temperature: float) -> AIResponse:
    """调用 Anthropic Claude"""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("未配置 ANTHROPIC_API_KEY")

    msg = _anthropic_client().messages.create(
        model=model,
        max_tokens=3000,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text
    usage = msg.usage.model_dump() if hasattr(msg, "usage") else {}
    return AIResponse(
        content=_parse_json(text),
        provider="claude",
        model=model,
        prompt_tokens=usage.get("input_tokens", 0),
        completion_tokens=usage.get("output_tokens", 0),
    )


# ============================================================
# 统一入口
# ============================================================
def call_ai(
    prompt: str,
    system: str,
    model: str = "auto",
    temperature: float = 0.4,
) -> AIResponse:
    """统一 AI 调用入口

    Args:
        prompt:     用户 prompt (要求模型输出 JSON)
        system:     系统提示词
        model:      模型选择:
                    'auto'        -> DeepSeek 优先, 失败 fallback Claude
                    'deepseek'    -> 强制 DeepSeek (用 DEEPSEEK_MODEL)
                    'claude'      -> 强制 Claude (用 CLAUDE_MODEL)
                    其他字符串     -> 当作具体模型名, 按前缀路由到对应 provider
                                    (如 'deepseek-reasoner' / 'claude-3-haiku...')
    Returns:
        AIResponse
    """
    # ---- 解析 model 参数 -> (provider, 实际模型名) ----
    if model == "auto":
        providers = []
        if DEEPSEEK_API_KEY:
            providers.append(("deepseek", DEEPSEEK_MODEL))
        if ANTHROPIC_API_KEY:
            providers.append(("claude", CLAUDE_MODEL))
        if not providers:
            raise RuntimeError("未配置任何 AI API Key")
    elif model == "deepseek":
        providers = [("deepseek", DEEPSEEK_MODEL)]
    elif model == "claude":
        providers = [("claude", CLAUDE_MODEL)]
    else:
        # 具体模型名: 按前缀路由
        if model.startswith("deepseek"):
            providers = [("deepseek", model)]
        elif model.startswith("claude"):
            providers = [("claude", model)]
        else:
            # 未知前缀, 默认走 deepseek
            providers = [("deepseek", model)]

    # ---- 依次尝试 providers (auto 模式下第一个失败切下一个) ----
    last_err = None
    for provider, model_name in providers:
        try:
            if provider == "deepseek":
                return _call_deepseek(prompt, system, model_name, temperature)
            else:
                return _call_claude(prompt, system, model_name, temperature)
        except Exception as e:
            last_err = e
            print(f"[ai_client] {provider} ({model_name}) 失败: {e}")
            if model != "auto":
                # 非自动模式不 fallback, 直接抛出
                raise
            print(f"[ai_client] 切换到下一个 provider...")

    # 所有 provider 都失败
    raise RuntimeError(f"所有 AI 调用均失败, 最后错误: {last_err}")
