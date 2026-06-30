"""pattern_agent.py — 内容模式识别 Agent

职责: 对爬取的视频数据进行内容模式识别
输入: ctx.crawled_videos + ctx.account_info
输出: ctx.pattern_result (话题分布/内容格式/发布节奏/互动模式)

分析维度:
1. 话题分布 — 从标题/描述提取高频关键词, 识别内容主题
2. 内容格式 — 视频时长分布, 短/中/长视频占比
3. 发布节奏 — 发布时间规律 (时段/星期分布)
4. 互动模式 — 点赞/评论/转发分布, 识别高互动内容特征
"""
import json
from collections import Counter
from typing import Optional

import httpx

from .base import BaseAgent, AgentContext

# ============================================================
# Pattern Agent 的 AI Prompt
# ============================================================

PATTERN_SYSTEM_PROMPT = (
    "你是一个短视频内容模式分析专家。你的职责是从视频数据中识别可执行的内容模式。"
    "只基于实际数据分析, 禁止推测或编造。"
    "每条结论必须附带 confidence_score (0.0-1.0) 和 evidence_fields (引用的真实字段名)。"
    "以严格 JSON 格式输出, 不要输出任何额外文字或 Markdown 代码块。"
)

PATTERN_SCHEMA = """{
  "topic_clusters": [
    {"topic": "话题名称", "video_count": 0, "avg_engagement": 0.0, "confidence_score": 1.0, "evidence_fields": ["title", "digg_count"]}
  ],
  "content_format_analysis": {
    "duration_distribution": {"short_under_30s": 0, "medium_30_120s": 0, "long_over_120s": 0},
    "avg_duration_sec": 0,
    "confidence_score": 1.0,
    "evidence_fields": ["duration"]
  },
  "posting_cadence": {
    "peak_hours": ["18:00-20:00"],
    "weekday_distribution": {"周一": 0},
    "posting_frequency": "每日X条 | 每周X条",
    "confidence_score": 1.0,
    "evidence_fields": ["create_time"]
  },
  "engagement_patterns": {
    "avg_likes": 0,
    "avg_comments": 0,
    "avg_shares": 0,
    "engagement_distribution": "均匀 | 两极分化 | 长尾",
    "top_engagement_trigger": "引发高互动的内容特征",
    "confidence_score": 1.0,
    "evidence_fields": ["digg_count", "comment_count", "share_count"]
  },
  "content_differentiators": [
    {"pattern": "识别到的差异化内容模式", "frequency": "X/50条视频", "confidence_score": 0.8, "evidence_fields": ["title"]}
  ]
}"""


def _build_pattern_prompt(videos: list[dict], account_fields: dict | None = None, rag_context: str = "") -> str:
    """构造内容模式识别 prompt"""
    # 按互动量排序, 取前 30 条 (减少 prompt 体积)
    sorted_videos = sorted(
        videos,
        key=lambda v: (v.get("digg_count") or 0) + (v.get("comment_count") or 0) + (v.get("share_count") or 0),
        reverse=True,
    )[:30]

    lines = []
    for i, v in enumerate(sorted_videos, 1):
        title = (v.get("title") or v.get("desc") or "")[:80]
        lines.append(
            f"视频{i}: 标题={title} "
            f"点赞={v.get('digg_count', '')} 评论={v.get('comment_count', '')} "
            f"转发={v.get('share_count', '')} 时长={v.get('duration', '')}秒 "
            f"发布时间={v.get('create_time_str') or v.get('create_time', '')}"
        )
    videos_text = "\n".join(lines)

    account_json = json.dumps(account_fields, ensure_ascii=False, indent=2) if account_fields else "无"

    rag_section = ""
    if rag_context:
        rag_section = f"""
【RAG 知识库上下文 (相关历史分析)】
{rag_context}
"""

    return f"""请对以下 {len(sorted_videos)} 条视频进行内容模式识别分析。

【账号信息】
{account_json}
{rag_section}
【视频数据 (按互动量排序, 前30条)】
{videos_text}

请严格按照以下 JSON Schema 输出 (只输出 JSON):
{PATTERN_SCHEMA}

【核心规则】
1. topic_clusters: 从标题/描述提取话题, 按出现频次分组, 每组统计视频数和平均互动量
2. content_format_analysis: 按 duration 字段分析时长分布
3. posting_cadence: 按 create_time 分析发布时间规律
4. engagement_patterns: 统计平均互动指标, 识别互动分布模式
5. content_differentiators: 识别该账号独特的内容模式 (如固定栏目、特殊句式等)
6. evidence_fields 必须使用真实字段名: title, desc, digg_count, comment_count, share_count, duration, create_time
7. 数据不足的字段: confidence_score=null, 对应数值填 null
"""


def _call_ai_for_patterns(videos: list[dict], account_fields: dict | None, rag_context: str = "") -> dict:
    """调用 AI 进行内容模式识别"""
    from ai_service import _get_configs, _parse_json

    configs = _get_configs()
    if not configs:
        return {"error": "无可用 AI 配置", "ai_provider": "无"}

    prompt = _build_pattern_prompt(videos, account_fields, rag_context)

    for cfg in configs:
        provider = cfg["provider"]
        try:
            if provider == "claude":
                from anthropic import Anthropic
                ac = Anthropic(api_key=cfg["api_key"])
                msg = ac.messages.create(
                    model=cfg["model"],
                    max_tokens=3000,
                    system=PATTERN_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = msg.content[0].text
            else:
                base_url = cfg["base_url"]
                url = f"{base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": PATTERN_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                }
                with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                text = data["choices"][0]["message"]["content"]

            result = _parse_json(text)
            result["ai_provider"] = provider
            return result
        except Exception as e:
            print(f"[PatternAgent] {cfg['label']} 失败: {e}")
            continue

    return {"error": "所有 AI 供应商均不可用", "ai_provider": "无"}


class PatternAgent(BaseAgent):
    """内容模式识别 Agent"""

    def __init__(self):
        super().__init__("PatternAgent")

    async def execute(self, ctx: AgentContext) -> dict:
        videos = ctx.crawled_videos or []

        if not videos:
            ctx.log(self.name, "无视频数据, 跳过模式识别", "warn")
            return {"agent": self.name, "patterns": None, "reason": "无视频数据"}

        # 获取 RAG 上下文
        rag_context = ""
        if ctx.params.get("use_rag", True):
            try:
                from rag.knowledge_base import get_kb
                account_name = ctx.account_info.get("account_name", "")
                rag_context = get_kb().build_context(f"内容模式 {account_name}", limit=2)
                if rag_context:
                    ctx.log(self.name, f"RAG 检索到相关上下文 ({len(rag_context)} 字符)")
            except Exception as e:
                ctx.log(self.name, f"RAG 检索失败, 继续无上下文分析: {e}", "warn")

        ctx.log(self.name, f"开始识别 {len(videos)} 条视频的内容模式")

        # 调用 AI
        account_fields = ctx.account_info.get("account_fields") if ctx.account_info else None
        result = _call_ai_for_patterns(videos, account_fields, rag_context)

        # 写入上下文
        ctx.pattern_result = result

        return {
            "agent": self.name,
            "topic_clusters": len(result.get("topic_clusters", [])),
            "differentiators": len(result.get("content_differentiators", [])),
            "ai_provider": result.get("ai_provider", "无"),
        }
