"""main_ws.py — 实时通知 WebSocket 服务 (端口 8010)

职责:
  1. 提供 WebSocket 端点, 前端连接后接收实时监控事件
  2. 支持 REST 触发监控 (monitor_service 发送 WS 事件)
  3. 支持 HTTP 推送事件 (跨服务调用)

事件类型 (前端接收):
  - monitor_start      监控开始
  - account_crawling   正在采集某账号
  - crawl_done         采集完成
  - analysis_crawling  正在 AI 分析
  - analysis_done      分析完成
  - monitor_done       监控结束
  - error              错误

运行:
  cd backend
  uvicorn main_ws:app --reload --port 8010

  或直接运行:
  python main_ws.py

前端连接:
  ws://localhost:8010/ws                   — 全局监听
  ws://localhost:8010/ws?run_id={run_id}   — 只接收特定轮次
"""
import os
import uuid
import logging
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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
logger = logging.getLogger("main_ws")

# ============================================================
# FastAPI
# ============================================================
app = FastAPI(
    title="AI 竞争情报系统 - 实时通知 WebSocket",
    description="监控事件实时推送到前端",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from ws_manager import get_ws_manager


# ============================================================
# WebSocket 端点
# ============================================================
@app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    run_id: Optional[str] = Query(None, description="订阅特定监控轮次"),
):
    """WebSocket 连接端点

    连接后自动接收监控事件:
      ws://localhost:8010/ws                   — 全局监听
      ws://localhost:8010/ws?run_id=xxx        — 只接收指定轮次

    前端也可发送消息:
      {"action": "ping"}                       — 心跳
      {"action": "subscribe", "run_id": "xxx"} — 切换订阅
    """
    client_id = str(uuid.uuid4())[:8]
    ws_manager = get_ws_manager()

    await ws_manager.connect(websocket, client_id, run_id)

    try:
        while True:
            # 接收前端消息 (心跳/订阅切换)
            data = await websocket.receive_text()
            import json
            try:
                msg = json.loads(data)
                action = msg.get("action")

                if action == "ping":
                    await ws_manager._send(websocket, {
                        "type": "pong",
                        "timestamp": str(uuid.uuid4())[:8],
                    })

                elif action == "subscribe":
                    new_run_id = msg.get("run_id")
                    async with ws_manager._lock:
                        ws_manager._connections[client_id]["run_id"] = new_run_id
                    await ws_manager._send(websocket, {
                        "type": "subscribed",
                        "run_id": new_run_id,
                        "message": f"已订阅轮次 {new_run_id}" if new_run_id else "已切换为全局监听",
                    })

            except json.JSONDecodeError:
                await ws_manager._send(websocket, {
                    "type": "error",
                    "message": "消息格式错误, 请发送 JSON",
                })

    except WebSocketDisconnect:
        await ws_manager.disconnect(client_id)
    except Exception as e:
        logger.error(f"WebSocket 异常: {e}")
        await ws_manager.disconnect(client_id)


# ============================================================
# HTTP 接口 (管理 + 触发)
# ============================================================
@app.get("/connections")
def list_connections():
    """当前 WebSocket 连接列表"""
    ws = get_ws_manager()
    return {
        "count": ws.get_connection_count(),
        "connections": ws.get_connections_info(),
    }


class BroadcastRequest(BaseModel):
    """HTTP 推送事件 (跨服务调用)"""
    event: dict
    run_id: Optional[str] = None


@app.post("/broadcast")
async def broadcast_event(req: BroadcastRequest):
    """HTTP 推送事件到 WebSocket 客户端 (跨服务调用)

    其他后端服务 (如 monitor :8009) 可通过 HTTP POST 推送事件:
      POST http://localhost:8010/broadcast
      {"event": {"type": "account_crawling", ...}, "run_id": "xxx"}
    """
    ws = get_ws_manager()
    await ws.broadcast(req.event, run_id=req.run_id)
    return {"ok": True, "pushed_to": ws.get_connection_count()}


@app.post("/trigger")
async def trigger_monitor():
    """HTTP 触发一轮监控 (内部调用 monitor_service)

    监控服务 (8009) 可直接调, 也可通过此接口触发
    """
    try:
        from monitor_service import run_monitor_cycle
        # 异步执行监控 (不阻塞 HTTP 响应)
        import asyncio
        loop = asyncio.get_event_loop()
        loop.create_task(_async_monitor())
        return {"ok": True, "message": "监控已触发, 事件将通过 WebSocket 推送"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def _async_monitor():
    """异步执行监控"""
    from monitor_service import run_monitor_cycle
    run_monitor_cycle(
        max_accounts=int(os.getenv("MONITOR_MAX_ACCOUNTS", "100")),
        max_videos=int(os.getenv("MONITOR_MAX_VIDEOS", "20")),
        analyze=os.getenv("MONITOR_ANALYZE", "true").lower() == "true",
        analysis_model=os.getenv("MONITOR_ANALYSIS_MODEL", "auto"),
        run_type="manual",
    )


# ============================================================
# 事件类型说明
# ============================================================
@app.get("/events")
def event_types():
    """事件类型说明"""
    return {
        "events": [
            {
                "type": "monitor_start",
                "description": "监控开始",
                "fields": ["run_id", "run_type", "total_accounts"],
            },
            {
                "type": "account_crawling",
                "description": "正在采集某账号",
                "fields": ["run_id", "account_name", "platform", "index", "total"],
            },
            {
                "type": "crawl_done",
                "description": "采集完成",
                "fields": ["run_id", "account_name", "crawled", "new_count", "duration_ms"],
            },
            {
                "type": "analysis_crawling",
                "description": "正在 AI 分析",
                "fields": ["run_id", "account_name", "video_count"],
            },
            {
                "type": "analysis_done",
                "description": "分析完成",
                "fields": ["run_id", "account_name", "analyzed", "tokens", "duration_ms"],
            },
            {
                "type": "monitor_done",
                "description": "监控结束",
                "fields": ["run_id", "status", "stats"],
            },
            {
                "type": "error",
                "description": "错误",
                "fields": ["run_id", "account_name", "stage", "error"],
            },
        ]
    }


# ============================================================
# 健康检查
# ============================================================
@app.get("/health")
def health():
    ws = get_ws_manager()
    return {
        "status": "ok",
        "service": "realtime-notification-ws",
        "port": 8010,
        "connections": ws.get_connection_count(),
        "endpoint": "ws://localhost:8010/ws",
    }


# ============================================================
# 启动
# ============================================================
if __name__ == "__main__":
    import uvicorn
    logger.info("启动实时通知 WebSocket 服务...")
    uvicorn.run(app, host="0.0.0.0", port=8010)
