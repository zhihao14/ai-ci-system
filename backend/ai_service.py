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


# ============================================================
# 短视频增长策略分析 (evidence-based 聚合分析)
# ============================================================

GROWTH_SYSTEM_PROMPT = (
    "你是一个严格基于数据的短视频内容分析师。"
    "你的唯一职责是对提供的账号信息和视频数据进行聚合统计与事实性分析。"
    "\n\n【绝对禁止】以下行为:\n"
    "1. 禁止推测用户心理、情绪、动机\n"
    "2. 禁止编造传播模型或抽象理论框架\n"
    "3. 禁止虚构未提供的视频标题、数据或内容\n"
    "4. 禁止基于账号简介推测视频内容特征\n"
    "5. 禁止编造不存在的字段名: evidence_fields 只能使用 prompt 中列出的真实字段名\n"
    "6. 如果某项分析所需的数据字段不存在或为空, 必须输出 '数据不足，无法判断'\n"
    "\n每一条结论必须附带:\n"
    "- confidence_score: 0.0-1.0 (1.0=直接从数据计算, 0.5=部分数据支撑, 无法计算时该字段为null)\n"
    "- evidence_fields: 支撑该结论的具体数据字段名数组, 必须是 prompt 中提供的真实字段名 (如 ['follower_count','aweme_count'])\n"
    "请以严格 JSON 格式输出，不要输出任何额外文字或 Markdown 代码块。"
)

GROWTH_JSON_SCHEMA = """{
  "data_completeness": "full | partial | insufficient",
  "raw_data_summary": {
    "has_account_info": true,
    "has_video_data": true,
    "video_count": 0,
    "available_video_fields": ["实际存在的字段名, 如 title/desc/digg_count/create_time 等"],
    "missing_video_fields": ["缺失的字段名"]
  },
  "aggregate_analysis": {
    "high_frequency_keywords": [
      {
        "keyword": "从视频标题/描述中提取的实际高频词",
        "occurrence_count": 0,
        "confidence_score": 1.0,
        "evidence_fields": ["title", "desc"]
      }
    ],
    "engagement_ranking": [
      {
        "rank": 1,
        "video_title": "实际视频标题",
        "total_engagement": 0,
        "digg_count": 0,
        "comment_count": 0,
        "share_count": 0,
        "confidence_score": 1.0,
        "evidence_fields": ["digg_count", "comment_count", "share_count"]
      }
    ],
    "posting_time_pattern": {
      "peak_hours": ["实际统计出的高频发布时段, 如 18:00-20:00"],
      "weekday_distribution": {"周一": 0, "周二": 0},
      "confidence_score": 1.0,
      "evidence_fields": ["create_time"],
      "status": "数据充足已计算 | 数据不足，无法判断"
    },
    "like_comment_ratio": {
      "average_ratio": 0.0,
      "min_ratio": 0.0,
      "max_ratio": 0.0,
      "confidence_score": 1.0,
      "evidence_fields": ["digg_count", "comment_count"],
      "status": "数据充足已计算 | 数据不足，无法判断"
    },
    "top_content_types": [
      {
        "content_type": "基于标题关键词的实际分类",
        "video_count": 0,
        "avg_engagement": 0.0,
        "confidence_score": 0.8,
        "evidence_fields": ["title", "digg_count"]
      }
    ]
  },
  "actionable_insights": [
    {
      "insight": "仅基于已验证数据的结论",
      "confidence_score": 0.9,
      "evidence_fields": ["具体字段"],
      "supporting_data": "引用的具体数值或事实"
    }
  ]
}"""


def build_growth_prompt(account_info: str, videos: list[dict] | None = None, account_fields: dict | None = None) -> str:
    """构造 evidence-based 聚合分析 prompt"""
    # 明确列出可用数据, 让 AI 知道边界
    has_videos = bool(videos and len(videos) > 0)
    video_count = len(videos) if videos else 0
    has_account_fields = bool(account_fields)

    if has_videos:
        available_fields = set()
        for v in videos:
            available_fields.update(v.keys())
        video_fields_str = ", ".join(sorted(available_fields)) or "无"
        missing_str = ""
    else:
        video_fields_str = "无视频数据"
        missing_str = "title, desc, digg_count, comment_count, share_count, play_count, create_time"

    # 账号结构化字段
    if has_account_fields:
        account_field_names = list(account_fields.keys())
        account_fields_json = json.dumps(account_fields, ensure_ascii=False, indent=2)
    else:
        account_field_names = []
        account_fields_json = "无结构化字段 (仅纯文本)"

    # 构造视频数据文本 — 截断过长内容, 只保留分析必需字段, 限制 20 条
    videos_text = "无视频数据"
    if has_videos:
        # 按互动量降序取前 20 条, 减少 prompt 体积
        sorted_videos = sorted(
            videos,
            key=lambda v: (v.get("digg_count") or 0) + (v.get("comment_count") or 0) + (v.get("share_count") or 0),
            reverse=True,
        )[:20]
        lines = []
        for i, v in enumerate(sorted_videos, 1):
            # 标题/描述截断到 80 字, 避免 prompt 过大导致超时
            title = (v.get("title") or v.get("desc") or "")[:80]
            desc = (v.get("desc") or "")[:80]
            lines.append(
                f"视频{i}: 标题={title} "
                f"点赞={v.get('digg_count','')} 评论={v.get('comment_count','')} "
                f"转发={v.get('share_count','')} 播放={v.get('play_count','')} "
                f"发布时间={v.get('create_time_str') or v.get('create_time','')}"
            )
        videos_text = "\n".join(lines)

    return f"""请对以下短视频账号进行 evidence-based 聚合分析。

【账号信息 (纯文本)】
{account_info}

【账号结构化字段 (JSON)】
以下是可以直接引用为 evidence_fields 的真实字段名及其值:
{account_fields_json}

【视频数据】
{videos_text}

【数据可用性】
- 账号信息(纯文本): {'有' if account_info.strip() else '无'}
- 账号结构化字段: {'有, 字段名: ' + ', '.join(account_field_names) if has_account_fields else '无'}
- 视频数据: {'有, 共' + str(video_count) + '条' if has_videos else '无'}
- 视频可用字段: {video_fields_str}
- 视频缺失字段: {missing_str or '无'}

请严格按照以下JSON Schema输出(只输出JSON,不要任何额外文字):
{GROWTH_JSON_SCHEMA}

【核心规则】
1. data_completeness: 有视频数据=full/partial, 无视频数据=insufficient
2. evidence_fields 必须使用上方【账号结构化字段】或【视频可用字段】中列出的真实字段名
   - 账号级字段: {', '.join(account_field_names) if account_field_names else '无'}
   - 视频级字段: {video_fields_str if has_videos else '无'}
   - 禁止编造不存在的字段名
3. 所有视频级指标(high_frequency_keywords/engagement_ranking/posting_time_pattern/like_comment_ratio/top_content_types):
   - 有视频数据时: 从实际数据计算, confidence_score=1.0
   - 无视频数据时: 对应字段填 status="数据不足，无法判断", confidence_score=null, 其余数值字段填null
4. actionable_insights: 只输出有数据支撑的结论, 每条必须引用具体数值
5. 禁止输出任何心理分析、传播模型、情绪推测
6. high_frequency_keywords: 从视频标题/描述中提取出现>=2次的词, 无视频数据时返回空数组
7. engagement_ranking: 按总互动量(点赞+评论+转发)降序排列, 无视频数据时返回空数组
8. 如果只有账号信息没有视频数据, actionable_insights 只能基于账号结构化字段的数值输出, evidence_fields 引用真实字段名
"""


def _openai_compatible_growth(cfg: dict, account_info: str, videos: list[dict] | None, account_fields: dict | None = None) -> dict:
    """调用 OpenAI 兼容接口进行增长策略分析"""
    base_url = cfg["base_url"]
    url = f"{base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
    payload = {
        "model": cfg["model"],
        "messages": [
            {"role": "system", "content": GROWTH_SYSTEM_PROMPT},
            {"role": "user", "content": build_growth_prompt(account_info, videos, account_fields)},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    # 超时 120s: connect 10s + read 110s, 应对大 prompt 的慢响应
    with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
        resp = client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    text = data["choices"][0]["message"]["content"]
    return _parse_json(text)


def _claude_growth(cfg: dict, account_info: str, videos: list[dict] | None, account_fields: dict | None = None) -> dict:
    """调用 Claude 进行增长策略分析"""
    ac = Anthropic(api_key=cfg["api_key"])
    msg = ac.messages.create(
        model=cfg["model"],
        max_tokens=4000,
        system=GROWTH_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": build_growth_prompt(account_info, videos, account_fields)}],
    )
    text = msg.content[0].text
    return _parse_json(text)


def growth_analyze(account_info: str, videos: list[dict] | None = None, account_fields: dict | None = None) -> dict:
    """增长策略分析主入口: evidence-based 聚合分析

    参数:
        account_info: 账号信息文本(爬虫抓取的content)
        videos: 可选的视频数据列表(含title/desc/digg_count等)
        account_fields: 可选的账号结构化字段(含follower_count/aweme_count等真实字段名)

    返回: 结构化分析结果 + ai_provider 字段
    """
    configs = _get_configs()

    if not configs:
        return {
            "error": "未配置任何 AI 供应商, 请前往设置页面配置",
            "ai_provider": "none",
        }

    errors = []
    for cfg in configs:
        provider = cfg["provider"]
        try:
            if provider == "claude":
                result = _claude_growth(cfg, account_info, videos, account_fields)
            else:
                result = _openai_compatible_growth(cfg, account_info, videos, account_fields)
            result["ai_provider"] = provider
            print(f"[ai_service] 增长策略分析成功, 使用: {cfg['label']}")
            return result
        except Exception as e:
            error_msg = f"{cfg['label']}: {type(e).__name__}: {str(e)}"
            errors.append(error_msg)
            print(f"[ai_service] {cfg['label']} 增长分析失败, 尝试下一个: {error_msg}")
            continue

    error_detail = "; ".join(errors) if errors else "未知错误"
    return {
        "error": f"所有 AI 供应商均不可用, 请检查配置。详细错误: {error_detail}",
        "ai_provider": "none",
    }
