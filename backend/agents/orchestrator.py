"""orchestrator.py — Agent 编排器

职责:
  1. 管理所有 Agent 实例
  2. 按流水线顺序执行 Agent
  3. 捕获单个 Agent 失败, 决定是否继续
  4. 支持两种模式:
     - full_pipeline: Crawler → Trend → Analysis → Strategy (完整)
     - partial:       只执行指定 Agent (单步)

流水线数据流:
  params → CrawlerAgent → crawled_videos
                         ↓
                   TrendAgent → anomalies + viral_videos
                              ↓
                  AnalysisAgent → analysis_result
                                 ↓
                  StrategyAgent → strategy_result
"""
import asyncio
from typing import Optional
from dataclasses import asdict
from datetime import datetime, timezone, timedelta

from .base import BaseAgent, AgentContext, AgentStatus

_CST = timezone(timedelta(hours=8))


class Orchestrator:
    """Agent 编排器 (单例)"""

    def __init__(self):
        self.agents: dict[str, BaseAgent] = {}
        self._init_agents()

    def _init_agents(self):
        """初始化所有 Agent"""
        from .crawler_agent import CrawlerAgent
        from .trend_agent import TrendAgent
        from .analysis_agent import AnalysisAgent
        from .strategy_agent import StrategyAgent

        self.agents = {
            "crawler": CrawlerAgent(),
            "trend": TrendAgent(),
            "analysis": AnalysisAgent(),
            "strategy": StrategyAgent(),
        }

    def list_agents(self) -> list[dict]:
        """返回所有 Agent 的状态摘要"""
        return [a.summary() for a in self.agents.values()]

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self.agents.get(name)

    # ============================================================
    # 完整流水线
    # ============================================================
    async def run_pipeline(
        self,
        platform: Optional[str] = None,
        url: Optional[str] = None,
        account_id: Optional[str] = None,
        max_videos: int = 20,
        analysis_model: str = "auto",
        strategy_model: str = "auto",
        skip_crawl: bool = False,
        skip_trend: bool = False,
    ) -> dict:
        """执行完整流水线: 采集 → 检测 → 分析 → 策略

        Args:
            platform:  目标平台 (skip_crawl=False 时必填)
            url:       目标 URL
            account_id: 已有账号 ID
            max_videos: 爬取视频数
            analysis_model: 分析用 AI 模型
            strategy_model: 策略生成用 AI 模型
            skip_crawl: 跳过采集 (用已有数据)
            skip_trend: 跳过趋势检测 (直接分析)

        Returns:
            dict: 完整流水线结果
        """
        ctx = AgentContext()
        ctx.params = {
            "platform": platform,
            "url": url,
            "account_id": account_id,
            "max_videos": max_videos,
            "analysis_model": analysis_model,
            "strategy_model": strategy_model,
            "save_to_db": True,
        }

        pipeline_steps = []

        # ---- Step 1: 采集 ----
        if not skip_crawl:
            crawler = self.agents["crawler"]
            try:
                result = await crawler.run(ctx)
                pipeline_steps.append(result)
            except Exception as e:
                # 采集失败, 流水线无法继续
                return self._build_result(ctx, pipeline_steps, failed_at="crawler", error=str(e))

        # ---- Step 2: 趋势检测 ----
        if not skip_trend:
            trend = self.agents["trend"]
            try:
                result = await trend.run(ctx)
                pipeline_steps.append(result)
            except Exception as e:
                # 趋势检测失败, 但可以继续分析
                ctx.log("orchestrator", f"趋势检测失败, 继续分析: {e}", "warn")
                pipeline_steps.append({"agent": "TrendAgent", "error": str(e)})

        # ---- Step 3: 爆款分析 ----
        analysis = self.agents["analysis"]
        try:
            result = await analysis.run(ctx)
            pipeline_steps.append(result)
        except Exception as e:
            return self._build_result(ctx, pipeline_steps, failed_at="analysis", error=str(e))

        # ---- Step 4: 策略生成 ----
        strategy = self.agents["strategy"]
        try:
            result = await strategy.run(ctx)
            pipeline_steps.append(result)
        except Exception as e:
            ctx.log("orchestrator", f"策略生成失败: {e}", "warn")
            pipeline_steps.append({"agent": "StrategyAgent", "error": str(e)})

        return self._build_result(ctx, pipeline_steps, failed_at=None)

    # ============================================================
    # 单 Agent 执行
    # ============================================================
    async def run_single(
        self,
        agent_name: str,
        params: dict,
    ) -> dict:
        """只执行单个 Agent

        Args:
            agent_name: "crawler" | "trend" | "analysis" | "strategy"
            params:     Agent 参数
        """
        agent = self.agents.get(agent_name)
        if not agent:
            raise ValueError(f"未知 Agent: {agent_name}, 可选: {list(self.agents.keys())}")

        ctx = AgentContext()
        ctx.params = params

        # 预填充上下文 (如果 params 中直接提供了上游数据)
        if "crawled_videos" in params:
            ctx.crawled_videos = params["crawled_videos"]
        if "viral_videos" in params:
            ctx.viral_videos = params["viral_videos"]
        if "analysis_result" in params:
            ctx.analysis_result = params["analysis_result"]
        if "account_info" in params:
            ctx.account_info = params["account_info"]

        result = await agent.run(ctx)

        return {
            "pipeline_id": ctx.pipeline_id,
            "agent": agent_name,
            "status": agent.status.value,
            "result": result,
            "context": self._context_to_dict(ctx),
            "logs": ctx.logs,
        }

    # ============================================================
    # 结果构造
    # ============================================================
    def _build_result(
        self,
        ctx: AgentContext,
        steps: list[dict],
        failed_at: Optional[str] = None,
        error: Optional[str] = None,
    ) -> dict:
        """构造流水线最终结果"""
        return {
            "pipeline_id": ctx.pipeline_id,
            "started_at": ctx.started_at,
            "finished_at": datetime.now(_CST).isoformat(),
            "status": "failed" if failed_at else "success",
            "failed_at": failed_at,
            "error": error,
            "steps": steps,
            "agents_status": [a.summary() for a in self.agents.values()],
            "results": {
                "account": ctx.account_info,
                "crawled_count": len(ctx.crawled_videos),
                "anomalies": ctx.anomalies,
                "viral_videos": ctx.viral_videos,
                "analysis": ctx.analysis_result,
                "strategy": ctx.strategy_result,
            },
            "logs": ctx.logs,
        }

    def _context_to_dict(self, ctx: AgentContext) -> dict:
        """把上下文转为可序列化的 dict"""
        return {
            "pipeline_id": ctx.pipeline_id,
            "crawled_count": len(ctx.crawled_videos),
            "anomalies_count": len(ctx.anomalies),
            "viral_count": len(ctx.viral_videos),
            "has_analysis": bool(ctx.analysis_result),
            "has_strategy": bool(ctx.strategy_result),
            "account": ctx.account_info,
        }


# ============================================================
# 单例
# ============================================================
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
