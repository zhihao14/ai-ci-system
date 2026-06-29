"""strategy_agent.py — 策略 Agent

职责: 基于分析结果生成运营策略 (标题改写 + 新脚本 + 选题建议 + 综合策略)
输入: ctx.analysis_result (Analysis Agent 产出)
      ctx.account_info (Crawler Agent 产出)
输出: ctx.strategy_result
"""
from typing import Optional

from .base import BaseAgent, AgentContext


class StrategyAgent(BaseAgent):
    def __init__(self):
        super().__init__("StrategyAgent")

    async def execute(self, ctx: AgentContext) -> dict:
        from content_service import generate_content
        from models_content import VideoRef
        from ai_router.base import AIMessage
        from ai_router.router import get_router

        # ---- 1. 基于爆款分析生成内容 (复用 content_service) ----
        # 取分析结果中建议的选题或原始爆款标题
        analysis = ctx.analysis_result
        topics = analysis.get("topic_suggestions", [])
        viral_reasons = analysis.get("viral_reasons", [])

        # 取第一条建议选题或原始视频作为参考
        ref_title = ""
        if topics:
            ref_title = topics[0].get("title", "")
        if not ref_title and ctx.viral_videos:
            ref_title = ctx.viral_videos[0].get("title", "")
        if not ref_title and ctx.crawled_videos:
            ref_title = ctx.crawled_videos[0].get("title", "")

        if not ref_title:
            ctx.log(self.name, "无参考视频数据, 仅生成策略建议", "warn")
            ref_title = "通用短视频内容"

        model = ctx.params.get("strategy_model", "auto")
        topic_count = ctx.params.get("topic_count", 20)

        ctx.log(self.name, f"基于「{ref_title[:20]}...」生成内容策略")

        # 调用内容生成
        video_ref = VideoRef(
            title=ref_title,
            like_count=ctx.viral_videos[0].get("like_count", 0) if ctx.viral_videos else 0,
            view_count=ctx.viral_videos[0].get("view_count", 0) if ctx.viral_videos else 0,
            platform=ctx.account_info.get("platform", "douyin"),
        )

        content_result = generate_content(
            video=video_ref,
            model=model,
            count=topic_count,
        )

        # ---- 2. 生成综合运营策略 (AI 综合判断) ----
        ctx.log(self.name, "生成综合运营策略")
        strategy = await self._generate_strategy_summary(ctx, model)

        # ---- 3. 汇总写入上下文 ----
        ctx.strategy_result = {
            "content": {
                "rewritten_titles": [t.model_dump() for t in content_result.rewritten_titles],
                "new_scripts": [s.model_dump() for s in content_result.new_scripts],
                "similar_topics": [t.model_dump() for t in content_result.similar_topics],
            },
            "strategy_summary": strategy,
            "account": ctx.account_info,
            "analysis_ref": {
                "overview": analysis.get("overview", ""),
                "viral_reasons": viral_reasons,
                "title_patterns": analysis.get("title_patterns", []),
            },
            "model_used": content_result.model_used,
            "provider": content_result.provider,
            "tokens": {
                "prompt": content_result.prompt_tokens,
                "completion": content_result.completion_tokens,
            },
        }

        return {
            "agent": self.name,
            "titles_generated": len(content_result.rewritten_titles),
            "scripts_generated": len(content_result.new_scripts),
            "topics_generated": len(content_result.similar_topics),
            "strategy_summary": strategy.get("summary", "")[:100],
        }

    async def _generate_strategy_summary(self, ctx: AgentContext, model: str) -> dict:
        """调用 AI 生成综合运营策略建议"""
        router = get_router()

        # 构造策略 prompt
        account = ctx.account_info
        analysis = ctx.analysis_result

        viral_reasons_text = "\n".join(
            f"- {r.get('factor', '')}: {r.get('detail', '')}"
            for r in analysis.get("viral_reasons", [])[:5]
        )

        tactics_text = "\n".join(
            f"- {t.get('name', '')}: {t.get('description', '')}"
            for t in analysis.get("content_tactics", [])[:5]
        )

        prompt = f"""基于以下竞品分析和账号信息, 生成一份运营策略建议。

【账号信息】
平台: {account.get('platform', '')}
账号名: {account.get('account_name', '')}
粉丝数: {account.get('follower_count', 0)}

【爆款原因分析】
{viral_reasons_text or '暂无'}

【内容套路】
{tactics_text or '暂无'}

【分析概述】
{analysis.get('overview', '暂无')}

请输出 JSON:
{{
  "summary": "总体策略概述(一段话)",
  "short_term": ["短期策略1", "短期策略2", "短期策略3"],
  "mid_term": ["中期策略1", "中期策略2"],
  "content_calendar": [
    {{"day": "周一", "content_type": "视频", "topic": "建议选题", "reason": "原因"}},
    {{"day": "周三", "content_type": "图文", "topic": "建议选题", "reason": "原因"}},
    {{"day": "周五", "content_type": "视频", "topic": "建议选题", "reason": "原因"}}
  ],
  "kpi_targets": [
    {{"metric": "粉丝增长", "target": "+1000/周", "strategy": "通过XX实现"}},
    {{"metric": "互动率", "target": ">5%", "strategy": "通过XX实现"}}
  ],
  "risks": ["风险1", "风险2"]
}}
"""

        messages = [
            AIMessage(
                role="system",
                content="你是短视频运营策略专家, 擅长基于竞品分析制定可执行的运营策略。只输出 JSON。",
            ),
            AIMessage(role="user", content=prompt),
        ]

        resp = router.call_with_retry(
            messages=messages,
            model=model,
            max_retries=3,
            temperature=0.5,
            json_mode=True,
        )

        return resp.json_content or {"summary": resp.content[:500]}
