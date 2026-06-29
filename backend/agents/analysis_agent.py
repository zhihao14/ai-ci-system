"""analysis_agent.py — 分析 Agent

职责: 对爆款视频做 AI 分析, 提炼爆款规律
输入: ctx.viral_videos (Trend Agent 产出) 或 ctx.crawled_videos (Crawler Agent 产出)
输出: ctx.analysis_result (爆款原因/标题结构/内容套路/选题建议)
"""
from typing import Optional

from .base import BaseAgent, AgentContext


class AnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__("AnalysisAgent")

    async def execute(self, ctx: AgentContext) -> dict:
        from viral_service import analyze_viral
        from models_viral import VideoInput

        # 选择分析对象: 优先爆款, 其次爬取的视频
        videos_raw = ctx.viral_videos or ctx.crawled_videos or []
        if not videos_raw:
            ctx.log(self.name, "无视频数据可分析, 跳过", "warn")
            return {"agent": self.name, "analyzed": 0, "reason": "无视频数据"}

        model = ctx.params.get("analysis_model", "auto")
        max_videos = min(len(videos_raw), 20)  # AI 上下文限制

        # 转为 VideoInput 格式
        videos = []
        for v in videos_raw[:max_videos]:
            videos.append(VideoInput(
                video_id=v.get("id") or v.get("video_id"),
                title=v.get("title", ""),
                like_count=v.get("like_count", v.get("likes", 0)),
                comment_count=v.get("comment_count", v.get("comments", 0)),
                share_count=v.get("share_count", v.get("shares", 0)),
                view_count=v.get("view_count", v.get("views", 0)),
                published_at=v.get("published_at") or v.get("publish_time"),
                video_url=v.get("video_url"),
                cover_url=v.get("cover_url"),
            ))

        ctx.log(self.name, f"开始分析 {len(videos)} 条视频")

        result = analyze_viral(videos=videos, model=model)

        # 写入上下文 (转为 dict 传递)
        ctx.analysis_result = {
            "overview": result.overview,
            "viral_reasons": [r.model_dump() for r in result.viral_reasons],
            "title_patterns": [p.model_dump() for p in result.title_patterns],
            "content_tactics": [t.model_dump() for t in result.content_tactics],
            "topic_suggestions": [t.model_dump() for t in result.topic_suggestions],
            "model_used": result.model_used,
            "provider": result.provider,
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
        }

        return {
            "agent": self.name,
            "analyzed": len(videos),
            "model_used": result.model_used,
            "provider": result.provider,
            "viral_reasons_count": len(result.viral_reasons),
            "topics_count": len(result.topic_suggestions),
        }
