"""ai_service.py - AI 情报分析 (从数据库读取配置)

调用流程:
1. 从 ai_config 表读取启用的 AI 供应商配置(按 priority 升序)
2. build_prompt()  把爬到的正文组装成结构化提取 prompt
3. analyze()       按优先级依次尝试, 失败自动 fallback 到下一个
返回结构化 dict, 字段与 intelligence_reports 表对齐
"""
import os
import json
import re
import httpx
from anthropic import Anthropic

# 环境变量作为 fallback (数据库无配置时使用)
ENV_DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
ENV_DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
ENV_DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
ENV_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ENV_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

# 各供应商默认 base_url
DEFAULT_BASE_URLS = {
    "deepseek": "https://api.deepseek.com/v1",
    "openai": "https://api.openai.com/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "claude": None,  # Claude 用 SDK, 不需要 base_url
}

# 要求模型严格输出的 JSON Schema
SYSTEM_PROMPT = (
    "你是一名资深竞争情报分析师。请根据给定的网页正文, 提炼竞争对手情报, "
    "并以严格 JSON 格式输出, 不要输出任何额外文字或 Markdown 代码块。"
)


def build_user_prompt(title: str, content: str) -> str:
    """构造用户 prompt, 明确要求字段与输出格式"""
    return f"""请分析以下竞争对手网页内容, 输出 JSON, 字段如下:
- summary: 一段话概述该公司的核心业务(<=200字)
- products: 字符串数组, 列出主要产品/服务
- pricing: 字符串数组, 列出能识别到的定价信息; 无则空数组
- positioning: 对象 {{market: 目标市场, audience: 目标客群, region: 主要区域}}
- strengths: 字符串数组, 3 条核心优势
- weaknesses: 字符串数组, 3 条潜在劣势或短板
- recent_changes: 字符串, 推断的近期动向/新品/战略调整; 无则填 "无明显变化"

网页标题: {title}
网页正文:
{content}
"""


def _parse_json(text: str) -> dict:
    """容错解析: 去掉可能的 ```json 包裹, 再 json.loads"""
    cleaned = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    return json.loads(cleaned)


def _get_configs() -> list[dict]:
    """获取 AI 配置列表: 先查数据库, 无配置则用环境变量 fallback"""
    configs: list[dict] = []

    # 1) 尝试从数据库读取
    try:
        from db import get_active_ai_configs
        db_configs = get_active_ai_configs()
        for c in db_configs:
            configs.append({
                "provider": c["provider"],
                "label": c.get("label", c["provider"]),
                "api_key": c["api_key"],
                "base_url": c.get("base_url") or DEFAULT_BASE_URLS.get(c["provider"]),
                "model": c["model"],
            })
    except Exception as e:
        print(f"[ai_service] 读取数据库 AI 配置失败, 使用环境变量: {e}")

    # 2) 数据库无配置时, 使用环境变量 fallback
    if not configs:
        if ENV_DEEPSEEK_API_KEY:
            configs.append({
                "provider": "deepseek",
                "label": "DeepSeek (env)",
                "api_key": ENV_DEEPSEEK_API_KEY,
                "base_url": ENV_DEEPSEEK_BASE_URL,
                "model": ENV_DEEPSEEK_MODEL,
            })
        if ENV_ANTHROPIC_API_KEY:
            configs.append({
                "provider": "claude",
                "label": "Claude (env)",
                "api_key": ENV_ANTHROPIC_API_KEY,
                "base_url": None,
                "model": ENV_CLAUDE_MODEL,
            })

    return configs


def _openai_compatible_analyze(cfg: dict, title: str, content: str) -> dict:
    """调用 OpenAI 兼容接口 (DeepSeek / OpenAI / GLM)"""
    base_url = cfg["base_url"]
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(title, content)},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    text = data["choices"][0]["message"]["content"]
    return _parse_json(text)


def _claude_analyze(cfg: dict, title: str, content: str) -> dict:
    """调用 Anthropic Claude (官方 SDK)"""
    ac = Anthropic(api_key=cfg["api_key"])
    msg = ac.messages.create(
        model=cfg["model"],
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(title, content)}],
    )
    text = msg.content[0].text
    return _parse_json(text)


def analyze(title: str, content: str) -> dict:
    """主入口: 按优先级依次尝试配置的 AI 供应商

    返回值会补上 ai_provider 字段
    """
    configs = _get_configs()

    if not configs:
        print("[ai_service] 无可用 AI 配置, 请在前台设置页面配置 AI 供应商")
        return {
            "summary": "AI 分析失败: 未配置任何 AI 供应商, 请前往设置页面配置",
            "products": [], "pricing": [], "positioning": {},
            "strengths": [], "weaknesses": [], "recent_changes": "",
            "ai_provider": "none",
        }

    for cfg in configs:
        provider = cfg["provider"]
        try:
            if provider == "claude":
                result = _claude_analyze(cfg, title, content)
            else:
                # deepseek / openai / glm 都走 OpenAI 兼容接口
                result = _openai_compatible_analyze(cfg, title, content)
            result["ai_provider"] = provider
            print(f"[ai_service] 分析成功, 使用: {cfg['label']}")
            return result
        except Exception as e:
            print(f"[ai_service] {cfg['label']} 失败, 尝试下一个: {e}")
            continue

    # 全部失败
    return {
        "summary": "AI 分析失败, 所有 AI 供应商均不可用, 请检查配置",
        "products": [], "pricing": [], "positioning": {},
        "strengths": [], "weaknesses": [], "recent_changes": "",
        "ai_provider": "none",
    }
