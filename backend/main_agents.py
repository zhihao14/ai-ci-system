"""main_agents.py — Multi-Agent 系统 API

接口:
  # ---- 流水线 ----
  POST /pipeline          执行完整流水线 (采集→检测→分析→策略)
  POST /agents/{name}/run 执行单个 Agent

  # ---- 查询 ----
  GET  /agents            所有 Agent 状态
  GET  /agents/{name}     单个 Agent 详情

  # ---- 管理 ----
  POST /pipeline/dry-run  干跑模式 (不写库, 只看流程)

运行:
  cd backend
  uvicorn main_agents:app --reload --port 8007
"""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(
    title="AI 竞争情报系统 - Multi-Agent 编排",
    description="Crawler → Trend → Analysis → Strategy 流水线编排",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 请求模型
# ============================================================
class PipelineRequest(BaseModel):
    """完整流水线请求"""
    platform: Optional[str] = Field(None, description="平台: douyin/xiaohongshu/youtube/tiktok (skip_crawl=False 时必填)")
    url: Optional[str] = Field(None, description="目标账号/频道 URL")
    account_id: Optional[str] = Field(None, description="已有账号 ID (跳过采集时用)")
    max_videos: int = Field(20, ge=1, le=100, description="爬取视频数上限")
    analysis_model: str = Field("auto", description="分析用 AI 模型: auto/deepseek/claude/glm")
    strategy_model: str = Field("auto", description="策略生成用 AI 模型")
    skip_crawl: bool = Field(False, description="跳过采集 (用已有账号数据)")
    skip_trend: bool = Field(False, description="跳过趋势检测")
    save_to_db: bool = Field(True, description="结果写入数据库")


class SingleAgentRequest(BaseModel):
    """单 Agent 执行请求"""
    params: dict = Field(default_factory=dict, description="Agent 参数")
    # 预填充上下文数据 (可选, 用于跳过上游)
    crawled_videos: Optional[list[dict]] = Field(None, description="直接传入视频数据 (跳过采集)")
    viral_videos: Optional[list[dict]] = Field(None, description="直接传入爆款视频")
    analysis_result: Optional[dict] = Field(None, description="直接传入分析结果")
    account_info: Optional[dict] = Field(None, description="直接传入账号信息")


# ============================================================
# 核心接口
# ============================================================
@app.post("/pipeline")
async def run_pipeline(req: PipelineRequest):
    """执行完整流水线: 采集 → 检测 → 分析 → 策略

    流程:
      1. CrawlerAgent  采集视频数据
      2. TrendAgent     检测异常增长 + 标记爆款
      3. AnalysisAgent  AI 分析爆款规律
      4. StrategyAgent  生成运营策略
    """
    from orchestrator import get_orchestrator

    orch = get_orchestrator()

    # 参数校验
    if not req.skip_crawl:
        if not req.platform and not req.url:
            raise HTTPException(status_code=400, detail="skip_crawl=False 时需要 platform 或 url 参数")
        if not req.platform and not req.url:
            raise HTTPException(status_code=400, detail="缺少 platform 或 url")

    try:
        result = await orch.run_pipeline(
            platform=req.platform,
            url=req.url,
            account_id=req.account_id,
            max_videos=req.max_videos,
            analysis_model=req.analysis_model,
            strategy_model=req.strategy_model,
            skip_crawl=req.skip_crawl,
            skip_trend=req.skip_trend,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"流水线执行失败: {e}")


@app.post("/agents/{agent_name}/run")
async def run_single_agent(agent_name: str, req: SingleAgentRequest):
    """执行单个 Agent

    支持的 Agent:
      - crawler:   采集视频 (需要 platform/url 或 account_id)
      - trend:     异常检测
      - analysis:  爆款分析 (需要 crawled_videos 或 viral_videos)
      - strategy:  策略生成 (需要 analysis_result)
    """
    from orchestrator import get_orchestrator

    orch = get_orchestrator()
    agent = orch.get_agent(agent_name)
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"未知 Agent: {agent_name}, 可选: {list(orch.agents.keys())}"
        )

    # 合并参数
    params = dict(req.params)
    if req.crawled_videos is not None:
        params["crawled_videos"] = req.crawled_videos
    if req.viral_videos is not None:
        params["viral_videos"] = req.viral_videos
    if req.analysis_result is not None:
        params["analysis_result"] = req.analysis_result
    if req.account_info is not None:
        params["account_info"] = req.account_info

    try:
        result = await orch.run_single(agent_name, params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {e}")


# ============================================================
# 查询接口
# ============================================================
@app.get("/agents")
def list_agents():
    """所有 Agent 状态"""
    from orchestrator import get_orchestrator
    return get_orchestrator().list_agents()


@app.get("/agents/{agent_name}")
def get_agent_status(agent_name: str):
    """单个 Agent 状态"""
    from orchestrator import get_orchestrator
    orch = get_orchestrator()
    agent = orch.get_agent(agent_name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"未知 Agent: {agent_name}")
    return agent.summary()


# ============================================================
# 流水线说明
# ============================================================
@app.get("/pipeline/info")
def pipeline_info():
    """流水线信息与说明"""
    return {
        "pipeline": ["crawler", "trend", "analysis", "strategy"],
        "description": {
            "crawler": "采集视频数据 (多平台爬虫)",
            "trend": "检测异常增长 + 标记爆款 (Z-score)",
            "analysis": "AI 分析爆款规律 (标题/内容/选题)",
            "strategy": "生成运营策略 (标题改写+脚本+选题+综合策略)",
        },
        "models": {
            "analysis": "auto / deepseek / claude / glm / 具体模型名",
            "strategy": "auto / deepseek / claude / glm / 具体模型名",
        },
        "ports": {
            "agents": 8007,
            "accounts": 8001,
            "viral": 8002,
            "multi": 8003,
            "router": 8004,
            "anomaly": 8005,
            "content": 8006,
        },
        "error_handling": {
            "crawler_failed": "流水线终止 (无数据无法继续)",
            "trend_failed": "继续分析 (趋势非必需)",
            "analysis_failed": "流水线终止 (策略依赖分析)",
            "strategy_failed": "返回部分结果 (策略非必需)",
        },
    }


# ============================================================
# 健康检查
# ============================================================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "multi-agent-orchestrator",
        "port": 8007,
        "agents": ["crawler", "trend", "analysis", "strategy"],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
