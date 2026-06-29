"""ai_service.py - DeepSeek / Claude 情报分析

调用流程:
1. build_prompt()  把爬到的正文组装成结构化提取 prompt
2. analyze()       优先 DeepSeek, 失败自动 fallback 到 Claude
返回结构化 dict, 字段与 intelligence_reports 表对齐
"""
import os
import json
import re
import httpx
from anthropic import Anthropic

# DeepSeek 配置 (OpenAI 兼容接口)
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# Claude 配置 (备用)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")

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


def _deepseek_analyze(title: str, content: str) -> dict:
    """调用 DeepSeek (OpenAI 兼容 /chat/completions)"""
    url = f"{DEEPSEEK_BASE_URL}/chat/completions"
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(title, content)},
        ],
        "temperature": 0.3,
        # response_format 强制 JSON 输出 (DeepSeek 支持)
        "response_format": {"type": "json_object"},
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    text = data["choices"][0]["message"]["content"]
    return _parse_json(text)


def _claude_analyze(title: str, content: str) -> dict:
    """调用 Anthropic Claude (备用)"""
    ac = Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = ac.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_user_prompt(title, content)}],
    )
    text = msg.content[0].text
    return _parse_json(text)


def analyze(title: str, content: str) -> dict:
    """主入口: DeepSeek 优先, 失败自动 fallback 到 Claude

    返回值会补上 ai_provider 字段
    """
    # 1) 优先 DeepSeek
    if DEEPSEEK_API_KEY:
        try:
            result = _deepseek_analyze(title, content)
            result["ai_provider"] = "deepseek"
            return result
        except Exception as e:
            print(f"[ai_service] DeepSeek 失败, 切换 Claude: {e}")

    # 2) 备用 Claude
    if ANTHROPIC_API_KEY:
        try:
            result = _claude_analyze(title, content)
            result["ai_provider"] = "claude"
            return result
        except Exception as e:
            print(f"[ai_service] Claude 也失败: {e}")

    # 3) 全部失败: 返回空壳, 保证流程不中断
    return {
        "summary": "AI 分析失败, 请检查 API Key 与额度",
        "products": [], "pricing": [], "positioning": {},
        "strengths": [], "weaknesses": [], "recent_changes": "",
        "ai_provider": "none",
    }
