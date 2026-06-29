"""main_anomaly.py — 异常检测系统 API

接口:
  # ---- 手动触发 ----
  POST /snapshot          手动拍快照
  POST /detect            手动触发异常检测
  POST /run-cycle         执行完整一轮 (快照+检测+通知)

  # ---- 查询 ----
  GET  /alerts            告警列表 (支持按 severity/status 筛选)
  GET  /alerts/{id}       告警详情
  GET  /notifications     通知列表
  GET  /viral             爆款视频列表
  GET  /snapshots/{id}    某对象的快照历史 (用于画趋势图)

  # ---- 管理 ----
  PUT  /alerts/{id}/ack   确认告警
  PUT  /alerts/{id}/resolve  解决告警
  POST /notifications/{id}/read  标记通知已读
  POST /cleanup           清理旧快照

  # ---- 调度器状态 ----
  GET  /scheduler/status  调度器运行状态
  POST /scheduler/start    启动调度器
  POST /scheduler/stop     停止调度器

运行:
  cd backend
  uvicorn main_anomaly:app --reload --port 8005
"""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(
    title="AI 竞争情报系统 - 异常增长检测",
    description="2h 点赞/评论/粉丝增长异常检测 + 自动标记爆款 + 通知",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from db import get_supabase
from detector import capture_snapshot, detect_anomalies, cleanup_old_snapshots
from notifier import process_pending_alerts, get_unread_notifications

# 调度器实例 (延迟初始化)
_scheduler_instance = None


# ============================================================
# 手动触发接口
# ============================================================
@app.post("/snapshot")
def api_snapshot():
    """手动拍一次快照"""
    try:
        return {"ok": True, "result": capture_snapshot()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/detect")
def api_detect():
    """手动触发异常检测"""
    try:
        result = detect_anomalies()
        # 检测后自动发送通知
        if result["alerts"] > 0:
            notif = process_pending_alerts()
            result["notifications"] = notif
        return {"ok": True, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run-cycle")
def api_run_cycle():
    """执行完整一轮: 快照 → 检测 → 通知"""
    try:
        snap = capture_snapshot()
        detect = detect_anomalies()
        notif = process_pending_alerts() if detect["alerts"] > 0 else {"processed": 0}
        return {
            "ok": True,
            "snapshot": snap,
            "detection": detect,
            "notifications": notif,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 查询接口
# ============================================================
@app.get("/alerts")
def list_alerts(
    severity: Optional[str] = Query(None, description="low|medium|high|critical"),
    status: str = Query("active", description="active|acknowledged|resolved|all"),
    limit: int = Query(50, ge=1, le=200),
):
    """告警列表 (支持筛选)"""
    sb = get_supabase()
    q = sb.table("alerts").select("*")

    if status != "all":
        q = q.eq("status", status)
    if severity:
        q = q.eq("severity", severity)

    res = q.order("created_at", desc=True).limit(limit).execute()
    return res.data


@app.get("/alerts/{alert_id}")
def get_alert(alert_id: str):
    """告警详情"""
    sb = get_supabase()
    res = sb.table("alerts").select("*").eq("id", alert_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="告警不存在")
    return res.data[0]


@app.get("/notifications")
def list_notifications(limit: int = Query(20, ge=1, le=100)):
    """通知列表"""
    return get_unread_notifications(limit=limit)


@app.get("/viral")
def list_viral(limit: int = Query(50, ge=1, le=200)):
    """爆款视频列表 (is_viral=true)"""
    sb = get_supabase()
    res = (
        sb.table("videos")
        .select("id, title, like_count, comment_count, share_count, view_count, published_at, is_viral, account_id")
        .eq("is_viral", True)
        .order("like_count", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


@app.get("/snapshots/video/{video_id}")
def get_video_snapshots(video_id: str, limit: int = Query(100, ge=1, le=500)):
    """某视频的快照历史 (用于趋势图)"""
    sb = get_supabase()
    res = (
        sb.table("metrics_snapshots")
        .select("like_count, comment_count, share_count, view_count, captured_at")
        .eq("video_id", video_id)
        .order("captured_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


@app.get("/snapshots/account/{account_id}")
def get_account_snapshots(account_id: str, limit: int = Query(100, ge=1, le=500)):
    """某账号的粉丝快照历史"""
    sb = get_supabase()
    res = (
        sb.table("metrics_snapshots")
        .select("follower_count, captured_at")
        .eq("account_id", account_id)
        .order("captured_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


# ============================================================
# 管理接口
# ============================================================
@app.put("/alerts/{alert_id}/ack")
def ack_alert(alert_id: str):
    """确认告警 (status → acknowledged)"""
    sb = get_supabase()
    sb.table("alerts").update({"status": "acknowledged"}).eq("id", alert_id).execute()
    return {"ok": True, "message": "告警已确认"}


@app.put("/alerts/{alert_id}/resolve")
def resolve_alert(alert_id: str):
    """解决告警 (status → resolved)"""
    sb = get_supabase()
    sb.table("alerts").update({"status": "resolved"}).eq("id", alert_id).execute()
    return {"ok": True, "message": "告警已解决"}


@app.post("/notifications/{notification_id}/read")
def mark_notification_read_api(notification_id: str):
    """标记通知已读"""
    sb = get_supabase()
    sb.table("notifications").update({"status": "sent"}).eq("id", notification_id).execute()
    return {"ok": True}


@app.post("/cleanup")
def api_cleanup():
    """手动清理旧快照"""
    return cleanup_old_snapshots()


# ============================================================
# 调度器管理
# ============================================================
@app.get("/scheduler/status")
def scheduler_status():
    """调度器运行状态"""
    global _scheduler_instance
    if _scheduler_instance is None:
        return {"running": False, "jobs": []}

    # APScheduler
    if hasattr(_scheduler_instance, "get_jobs"):
        jobs = []
        for job in _scheduler_instance.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            })
        return {"running": _scheduler_instance.running, "jobs": jobs}

    # 简单循环线程
    return {"running": _scheduler_instance.is_alive() if hasattr(_scheduler_instance, "is_alive") else True, "jobs": []}


@app.post("/scheduler/start")
def scheduler_start():
    """启动调度器"""
    global _scheduler_instance
    if _scheduler_instance is not None:
        return {"ok": False, "message": "调度器已在运行"}

    from scheduler import start_scheduler
    _scheduler_instance = start_scheduler()
    return {"ok": True, "message": "调度器已启动"}


@app.post("/scheduler/stop")
def scheduler_stop():
    """停止调度器"""
    global _scheduler_instance
    if _scheduler_instance is None:
        return {"ok": False, "message": "调度器未运行"}

    if hasattr(_scheduler_instance, "shutdown"):
        _scheduler_instance.shutdown(wait=False)
    _scheduler_instance = None
    return {"ok": True, "message": "调度器已停止"}


# ============================================================
# 健康检查
# ============================================================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "window_hours": int(os.getenv("ANOMALY_WINDOW_HOURS", "2")),
        "baseline_days": int(os.getenv("ANOMALY_BASELINE_DAYS", "7")),
        "scheduler_running": _scheduler_instance is not None,
    }


if __name__ == "__main__":
    import uvicorn
    # 启动时自动启动调度器
    from scheduler import start_scheduler
    _scheduler_instance = start_scheduler()
    uvicorn.run(app, host="0.0.0.0", port=8005)
