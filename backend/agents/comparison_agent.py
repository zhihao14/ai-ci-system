"""comparison_agent.py — 多竞争对手对比 Agent

职责: 对比多个竞争对手的分析结果, 生成竞争格局矩阵
输入: 多个 video_analysis 记录 (含 account_info + videos + analysis)
输出: 对比矩阵 (内容策略对比 / 互动表现对比 / 增长潜力对比 / SWOT)

对比维度:
1. 内容策略对比 — 话题覆盖/内容格式/发布频率
2. 互动表现对比 — 平均点赞/评论/转发/互动率
3. 增长潜力对比 — 粉丝规模/内容产出/爆款比例
4. SWOT 矩阵 — 每个竞争对手的优势/劣势/机会/威胁
"""
import json
from typing import Optional

import httpx

from .base import BaseAgent, AgentContext

COMPARISON_SYSTEM_PROMPT = (
    "你是一个竞争情报分析专家。你的职责是对比多个短视频账号的竞争格局。"
    "只基于提供的实际数据分析, 禁止推测或编造。"
    "每条结论必须附带 confidence_score (0.0-1.0) 和 evidence_fields。"
    "以严格 JSON 格式输出, 不要输出任何额外文字或 Markdown 代码块。"
)

COMPARISON_SCHEMA = """{
  "comparison_matrix": [
    {
      "competitor": "账号名称",
      "follower_count": 0,
      "video_count": 0,
      "avg_likes": 0,
      "avg_comments": 0,
      "avg_shares": 0,
      "top_topic": "主要话题",
      "posting_frequency": "发布频率",
      "engagement_rate": 0.0,
      "confidence_score": 1.0,
      "evidence_fields": ["follower_count", "digg_count"]
    }
  ],
  "competitive_landscape": {
    "market_leader": "粉丝/互动最高的账号",
    "content_leader": "内容产出最多的账号",
    "engagement_leader": "互动率最高的账号",
    "growth_potential": "增长潜力最大的账号",
    "confidence_score": 0.8,
    "evidence_fields": ["follower_count", "digg_count", "aweme_count"]
  },
  "swot_analysis": [
    {
      "competitor": "账号名称",
      "strengths": ["优势1", "优势2"],
      "weaknesses": ["劣势1"],
      "opportunities": ["机会1"],
      "threats": ["威胁1"],
      "confidence_score": 0.8,
      "evidence_fields": ["follower_count", "digg_count"]
    }
  ],
  "strategic_recommendations": [
    {"recommendation": "基于对比的差异化策略建议", "priority": "high|medium|low", "confidence_score": 0.7, "evidence_fields": ["follower_count"]}
  ]
}"""


def _build_comparison_prompt(analyses: list[dict], rag_context: str = "") -> str:
    """构造多竞争对手对比 prompt"""
    competitors = []
    for a in analyses:
        account_fields = a.get("account_fields") or {}
        videos = a.get("videos") or []

        # 计算统计数据
        total_likes = sum(v.get("digg_count") or 0 for v in videos)
        total_comments = sum(v.get("comment_count") or 0 for v in videos)
        total_shares = sum(v.get("share_count") or 0 for v in videos)
        avg_likes = total_likes // len(videos) if videos else 0
        avg_comments = total_comments // len(videos) if videos else 0
        avg_shares = total_shares // len(videos) if videos else 0

        # 提取高频关键词
        all_titles = " ".join(v.get("title") or v.get("desc") or "" for v in videos)
        competitors.append({
            "name": account_fields.get("nickname") or a.get("account_name") or "未知",
            "follower_count": account_fields.get("follower_count"),
            "total_favorited": account_fields.get("total_favorited"),
            "aweme_count": account_fields.get("aweme_count"),
            "video_count": len(videos),
            "avg_likes": avg_likes,
            "avg_comments": avg_comments,
            "avg_shares": avg_shares,
            "total_engagement": total_likes + total_comments + total_shares,
            "top_videos": [
                {"title": (v.get("title") or "")[:50], "digg": v.get("digg_count"), "comment": v.get("comment_count")}
                for v in sorted(videos, key=lambda x: (x.get("digg_count") or 0), reverse=True)[:3]
            ],
        })

    competitors_json = json.dumps(competitors, ensure_ascii=False, indent=2)

    rag_section = ""
    if rag_context:
        rag_section = f"""
【RAG 知识库上下文】
{rag_context}
"""

    return f"""请对比以下 {len(competitors)} 个短视频账号的竞争格局。

【竞争对手数据 (统计摘要)】
{competitors_json}
{rag_section}
请严格按照以下 JSON Schema 输出 (只输出 JSON):
{COMPARISON_SCHEMA}

【核心规则】
1. comparison_matrix: 每个账号一行, 包含关键指标
2. competitive_landscape: 识别各类领先者
3. swot_analysis: 每个账号的 SWOT
4. strategic_recommendations: 基于对比的策略建议
5. evidence_fields 必须使用真实字段名: follower_count, digg_count, comment_count, share_count, aweme_count, total_favorited
"""


def _call_ai_for_comparison(analyses: list[dict], rag_context: str = "") -> dict:
    """调用 AI 进行多竞争对手对比"""
    from ai_service import _get_configs, _parse_json

    configs = _get_configs()
    if not configs:
        return {"error": "无可用 AI 配置", "ai_provider": "none"}

    prompt = _build_comparison_prompt(analyses, rag_context)

    for cfg in configs:
        provider = cfg["provider"]
        try:
            if provider == "claude":
                from anthropic import Anthropic
                ac = Anthropic(api_key=cfg["api_key"])
                msg = ac.messages.create(
                    model=cfg["model"],
                    max_tokens=4000,
                    system=COMPARISON_SYSTEM_PROMPT,
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
                        {"role": "system", "content": COMPARISON_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
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
            print(f"[ComparisonAgent] {cfg['label']} 失败: {e}")
            continue

    return {"error": "所有 AI 供应商均不可用", "ai_provider": "none"}


class ComparisonAgent(BaseAgent):
    """多竞争对手对比 Agent"""

    def __init__(self):
        super().__init__("ComparisonAgent")

    async def execute(self, ctx: AgentContext) -> dict:
        analyses = ctx.params.get("analyses", [])
        if len(analyses) < 2:
            ctx.log(self.name, "至少需要 2 个竞争对手才能对比", "warn")
            return {"agent": self.name, "comparison": None, "reason": "竞争对手不足"}

        # 获取 RAG 上下文
        rag_context = ""
        try:
            from rag.knowledge_base import get_kb
            names = [a.get("account_name", "") for a in analyses]
            rag_context = get_kb().build_context(" ".join(names), limit=3)
            if rag_context:
                ctx.log(self.name, f"RAG 检索到相关上下文 ({len(rag_context)} 字符)")
        except Exception as e:
            ctx.log(self.name, f"RAG 检索失败: {e}", "warn")

        ctx.log(self.name, f"开始对比 {len(analyses)} 个竞争对手")

        result = _call_ai_for_comparison(analyses, rag_context)

        ctx.comparison_result = result

        return {
            "agent": self.name,
            "competitors_compared": len(analyses),
            "matrix_rows": len(result.get("comparison_matrix", [])),
            "recommendations": len(result.get("strategic_recommendations", [])),
            "ai_provider": result.get("ai_provider", "none"),
        }
