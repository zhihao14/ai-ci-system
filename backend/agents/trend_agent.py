"""trend_agent.py — 趋势 Agent

职责: 拍快照 + 检测异常增长 + 标记爆款
输入: ctx.params 中可选 account_id (限定检测范围)
输出: ctx.anomalies + ctx.viral_videos + ctx.snapshot_result
"""
from .base import BaseAgent, AgentContext


class TrendAgent(BaseAgent):
    def __init__(self):
        super().__init__("TrendAgent")

    async def execute(self, ctx: AgentContext) -> dict:
        from detector import capture_snapshot, detect_anomalies
        from db import get_supabase

        # 1. 拍快照
        ctx.log(self.name, "开始采集指标快照")
        snap = capture_snapshot()
        ctx.snapshot_result = snap

        # 2. 异常检测
        ctx.log(self.name, "开始异常增长检测")
        detect = detect_anomalies()

        ctx.anomalies = detect.get("details", [])

        # 3. 查询已标记的爆款视频
        sb = get_supabase()
        viral_res = sb.table("videos").select(
            "id, title, like_count, comment_count, view_count, published_at, account_id"
        ).eq("is_viral", True).order("like_count", desc=True).limit(20).execute()

        ctx.viral_videos = viral_res.data or []

        return {
            "agent": self.name,
            "snapshots": snap,
            "alerts": detect.get("alerts", 0),
            "viral_marked": detect.get("viral_marked", 0),
            "viral_total": len(ctx.viral_videos),
        }
