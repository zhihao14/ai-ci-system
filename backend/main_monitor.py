"""main_monitor.py — 自动监控调度系统 API (端口 8009)

职责: 每 30 分钟自动扫描所有账号 → 抓新视频 → AI 分析 → 存数据库

接口:
  # ---- 手动触发 ----
  POST /run              立即执行一轮完整监控
  POST /run/{account_id} 仅监控指定账号

  # ---- 查询 ----
  GET  /runs             监控轮次历史
  GET  /runs/{id}        单轮监控详情 (含各账号任务)
  GET  /runs/last        最近一轮监控摘要
  GET  /accounts/{id}/history  某账号的监控历史

  # ---- 调度器管理 ----
  GET  /scheduler/status 调度器运行状态
  POST /scheduler/start  启动定时调度 (每 30 分钟)
  POST /scheduler/stop   停止定时调度
  POST /scheduler/trigger 手动触发一次定时任务

  # ---- 健康检查 ----
  GET  /health           健康检查

运行:
  cd backend
  uvicorn main_monitor:app --reload --port 8009

  或直接运行 (启动 API + 自动启动调度器):
  python main_monitor.py
"""
import os
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ============================================================
# 日志
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("main_monitor")

# ============================================================
# FastAPI
# ============================================================
app = FastAPI(
    title="AI 竞争情报系统 - 自动监控调度",
    description="每 30 分钟自动扫描账号 → 采集新视频 → AI 分析 → 入库",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from monitor_service import (
    run_monitor_cycle,
    monitor_account,
    list_monitor_runs,
    get_monitor_run,
    get_last_run_summary,
    get_account_monitor_history,
)
from db_accounts import get_account

# ============================================================
# 请求模型
# ============================================================
class RunRequest(BaseModel):
    """手动触发监控"""
    max_accounts: int = Field(100, ge=1, le=500, description="最大扫描账号数")
    max_videos: int = Field(20, ge=1, le=100, description="每账号爬取上限")
    analyze: bool = Field(True, description="是否做 AI 分析")
    analysis_model: str = Field("auto", description="AI 模型: auto/deepseek/claude")


class RunSingleRequest(BaseModel):
    """单账号监控"""
    max_videos: int = Field(20, ge=1, le=100)
    analyze: bool = Field(True)
    analysis_model: str = Field("auto")


# ============================================================
# 手动触发接口
# ============================================================
@app.post("/run")
def api_run(req: RunRequest):
    """立即执行一轮完整监控 (扫描所有账号)

    流程:
      1. 从数据库扫描所有账号
      2. 逐个账号: 调爬虫抓新视频 → upsert 入库
      3. 对新增视频: 调 AI 做爆款分析 → 存 ai_analysis 表
      4. 记录到 monitor_runs / monitor_tasks
    """
    logger.info(f"手动触发监控: max_accounts={req.max_accounts}, analyze={req.analyze}")
    try:
        result = run_monitor_cycle(
            max_accounts=req.max_accounts,
            max_videos=req.max_videos,
            analyze=req.analyze,
            analysis_model=req.analysis_model,
            run_type="manual",
        )
        return {"ok": True, **result}
    except Exception as e:
        logger.error(f"监控失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run/{account_id}")
def api_run_single(account_id: str, req: RunSingleRequest):
    """仅监控指定账号"""
    account = get_account(account_id)
    if not account:
        raise HTTPException(status_code=404, detail=f"账号不存在: {account_id}")

    logger.info(f"手动监控单账号: {account.get('name')} ({account_id})")

    # 创建一个临时 run
    from monitor_service import create_monitor_run, finish_monitor_run
    run_id = create_monitor_run("manual")

    try:
        result = monitor_account(
            run_id=run_id,
            account=account,
            max_videos=req.max_videos,
            analyze=req.analyze,
            analysis_model=req.analysis_model,
        )

        # 更新 run 统计
        stats = {
            "total": 1,
            "crawled": 1 if result["status"] == "success" and result["new_count"] > 0 else 0,
            "failed": 1 if result["status"] == "failed" else 0,
            "skipped": 1 if result["status"] == "success" and result["new_count"] == 0 else 0,
            "new_videos": result["new_count"],
            "analyzed": result["analyzed"],
            "total_tokens": result["tokens"],
        }
        finish_monitor_run(run_id, status=result["status"], stats=stats)

        return {"ok": True, "run_id": run_id, "result": result}
    except Exception as e:
        finish_monitor_run(run_id, status="failed", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 查询接口
# ============================================================
@app.get("/runs")
def api_list_runs(limit: int = Query(20, ge=1, le=100)):
    """监控轮次历史"""
    return list_monitor_runs(limit=limit)


@app.get("/runs/last")
def api_last_run():
    """最近一轮监控摘要"""
    summary = get_last_run_summary()
    if not summary:
        return {"message": "暂无监控记录"}
    return summary


@app.get("/runs/{run_id}")
def api_get_run(run_id: str):
    """单轮监控详情 (含各账号任务)"""
    run = get_monitor_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="监控轮次不存在")
    return run


@app.get("/accounts/{account_id}/history")
def api_account_history(account_id: str, limit: int = Query(20, ge=1, le=100)):
    """某账号的监控历史"""
    return get_account_monitor_history(account_id, limit=limit)


# ============================================================
# 调度器管理
# ============================================================
_scheduler_instance = None

@app.get("/scheduler/status")
def scheduler_status():
    """调度器运行状态"""
    global _scheduler_instance
    if _scheduler_instance is None:
        return {"running": False, "jobs": [], "interval_minutes": 30}

    # APScheduler
    if hasattr(_scheduler_instance, "get_jobs"):
        jobs = []
        for job in _scheduler_instance.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
        return {
            "running": _scheduler_instance.running,
            "jobs": jobs,
            "interval_minutes": 30,
        }

    # 简单循环线程
    return {
        "running": _scheduler_instance.is_alive() if hasattr(_scheduler_instance, "is_alive") else True,
        "jobs": [],
        "interval_minutes": 30,
    }


@app.post("/scheduler/start")
def scheduler_start():
    """启动定时调度 (每 30 分钟自动监控)"""
    global _scheduler_instance
    if _scheduler_instance is not None:
        return {"ok": False, "message": "调度器已在运行"}

    _scheduler_instance = _start_scheduler()
    return {"ok": True, "message": "调度器已启动, 每 30 分钟执行一次自动监控"}


@app.post("/scheduler/stop")
def scheduler_stop():
    """停止定时调度"""
    global _scheduler_instance
    if _scheduler_instance is None:
        return {"ok": False, "message": "调度器未运行"}

    if hasattr(_scheduler_instance, "shutdown"):
        _scheduler_instance.shutdown(wait=False)
    _scheduler_instance = None
    return {"ok": True, "message": "调度器已停止"}


@app.post("/scheduler/trigger")
def scheduler_trigger():
    """手动触发一次调度任务 (不等待 30 分钟)"""
    try:
        result = run_monitor_cycle(
            max_accounts=int(os.getenv("MONITOR_MAX_ACCOUNTS", "100")),
            max_videos=int(os.getenv("MONITOR_MAX_VIDEOS", "20")),
            analyze=os.getenv("MONITOR_ANALYZE", "true").lower() == "true",
            analysis_model=os.getenv("MONITOR_ANALYSIS_MODEL", "auto"),
            run_type="scheduled",
        )
        return {"ok": True, "result": {
            "run_id": result["run_id"],
            "status": result["status"],
            "stats": result["stats"],
        }}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 调度器实现
# ============================================================
def _start_scheduler():
    """启动 APScheduler 定时调度"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from datetime import datetime, timezone, timedelta
    except ImportError:
        logger.error("未安装 apscheduler, 回退到简单循环模式")
        return _start_simple_loop()

    _CST = timezone(timedelta(hours=8))
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # 主任务: 每 30 分钟自动监控
    scheduler.add_job(
        _scheduled_monitor,
        trigger=IntervalTrigger(minutes=30),
        id="monitor",
        name="自动监控 (扫描→采集→分析)",
        max_instances=1,
        coalesce=True,
    )

    scheduler.start()
    logger.info("✓ 监控调度器已启动, 每 30 分钟执行一次")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.id}: {job.name} → 下次执行 {job.next_run_time}")

    return scheduler


def _start_simple_loop():
    """无 APScheduler 时的回退方案"""
    import threading
    import time

    def loop():
        interval = 30 * 60  # 30 分钟
        logger.info("启动简单循环调度器 (无 APScheduler), 每 30 分钟执行")
        while True:
            try:
                _scheduled_monitor()
            except Exception as e:
                logger.error(f"定时监控异常: {e}")
            time.sleep(interval)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread


def _scheduled_monitor():
    """定时任务: 执行一轮自动监控"""
    logger.info("⏰ 定时监控触发")
    try:
        run_monitor_cycle(
            max_accounts=int(os.getenv("MONITOR_MAX_ACCOUNTS", "100")),
            max_videos=int(os.getenv("MONITOR_MAX_VIDEOS", "20")),
            analyze=os.getenv("MONITOR_ANALYZE", "true").lower() == "true",
            analysis_model=os.getenv("MONITOR_ANALYSIS_MODEL", "auto"),
            run_type="scheduled",
        )
    except Exception as e:
        logger.error(f"定时监控失败: {e}", exc_info=True)


# ============================================================
# 健康检查
# ============================================================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "auto-monitor-scheduler",
        "port": 8009,
        "interval_minutes": 30,
        "scheduler_running": _scheduler_instance is not None,
        "features": [
            "每 30 分钟自动扫描所有账号",
            "自动抓取新视频并入库",
            "自动 AI 爆款分析",
            "分析结果存入 ai_analysis 表",
            "监控历史记录 (monitor_runs / monitor_tasks)",
        ],
    }


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    import uvicorn

    # 启动时自动启动调度器
    logger.info("启动自动监控调度系统...")
    _scheduler_instance = _start_scheduler()

    uvicorn.run(app, host="0.0.0.0", port=8009)
