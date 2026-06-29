"""ws_manager.py — WebSocket 连接管理器

职责:
  1. 管理所有 WebSocket 客户端连接
  2. 提供广播接口, 向所有连接推送实时事件
  3. 支持按 run_id 订阅 (只接收特定监控轮次的事件)

事件类型 (event.type):
  - monitor_start      监控开始
  - account_crawling   开始采集某账号
  - crawl_done         采集完成
  - analysis_crawling  开始 AI 分析
  - analysis_done      分析完成
  - monitor_done       监控结束
  - error              错误
"""
import json
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import WebSocket

logger = logging.getLogger("ws_manager")

_CST = timezone(timedelta(hours=8))


class WSManager:
    """WebSocket 连接管理器 (单例)

    每个连接可订阅特定 run_id, 也可全局监听
    """

    def __init__(self):
        # active_connections: {client_id: {"ws": WebSocket, "run_id": Optional[str]}}
        self._connections: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, client_id: str, run_id: Optional[str] = None):
        """接受 WebSocket 连接"""
        await websocket.accept()
        async with self._lock:
            self._connections[client_id] = {
                "ws": websocket,
                "run_id": run_id,
            }
        logger.info(f"WebSocket 连接: client={client_id}, run_id={run_id}, 当前连接数={len(self._connections)}")

        # 发送连接成功消息
        await self._send(websocket, {
            "type": "connected",
            "client_id": client_id,
            "message": "WebSocket 连接成功, 等待监控事件...",
            "timestamp": datetime.now(_CST).isoformat(),
        })

    async def disconnect(self, client_id: str):
        """断开连接"""
        async with self._lock:
            self._connections.pop(client_id, None)
        logger.info(f"WebSocket 断开: client={client_id}, 当前连接数={len(self._connections)}")

    async def broadcast(self, event: dict, run_id: Optional[str] = None):
        """广播事件到所有 (或指定 run_id 的) 连接

        Args:
            event:   事件数据, 必须包含 type 字段
            run_id:   如果提供, 只推送给订阅了该 run_id 的连接 + 全局连接
        """
        # 补充时间戳
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(_CST).isoformat()

        message = json.dumps(event, ensure_ascii=False, default=str)

        # 收集需要推送的连接
        targets = []
        async with self._lock:
            for client_id, conn in self._connections.items():
                conn_run_id = conn.get("run_id")
                # 全局连接 (无订阅) 或匹配 run_id 的连接
                if run_id is None or conn_run_id is None or conn_run_id == run_id:
                    targets.append((client_id, conn["ws"]))

        # 异步推送
        for client_id, ws in targets:
            await self._send(ws, event)

        if targets:
            logger.debug(f"广播事件 {event.get('type')} → {len(targets)} 个客户端")

    async def _send(self, websocket: WebSocket, event: dict):
        """安全发送消息 (连接已断开时忽略)"""
        try:
            await websocket.send_text(json.dumps(event, ensure_ascii=False, default=str))
        except Exception as e:
            logger.warning(f"发送 WebSocket 消息失败: {e}")

    def get_connection_count(self) -> int:
        """当前连接数"""
        return len(self._connections)

    def get_connections_info(self) -> list[dict]:
        """连接信息列表"""
        return [
            {
                "client_id": cid,
                "run_id": conn.get("run_id"),
            }
            for cid, conn in self._connections.items()
        ]


# ============================================================
# 单例
# ============================================================
_manager: Optional[WSManager] = None


def get_ws_manager() -> WSManager:
    global _manager
    if _manager is None:
        _manager = WSManager()
    return _manager


# ============================================================
# 事件构造辅助函数 (供 monitor_service 调用)
# ============================================================
async def emit_monitor_start(run_id: str, total_accounts: int, run_type: str = "scheduled"):
    """推送: 监控开始"""
    await get_ws_manager().broadcast({
        "type": "monitor_start",
        "run_id": run_id,
        "run_type": run_type,
        "total_accounts": total_accounts,
        "message": f"开始监控 {total_accounts} 个账号",
    }, run_id=run_id)


async def emit_account_crawling(run_id: str, account_name: str, platform: str, index: int, total: int):
    """推送: 开始采集某账号"""
    await get_ws_manager().broadcast({
        "type": "account_crawling",
        "run_id": run_id,
        "account_name": account_name,
        "platform": platform,
        "index": index,
        "total": total,
        "message": f"正在采集 [{index}/{total}] {account_name} ({platform})",
    }, run_id=run_id)


async def emit_crawl_done(run_id: str, account_name: str, crawled: int, new_count: int, duration_ms: int):
    """推送: 采集完成"""
    await get_ws_manager().broadcast({
        "type": "crawl_done",
        "run_id": run_id,
        "account_name": account_name,
        "crawled": crawled,
        "new_count": new_count,
        "duration_ms": duration_ms,
        "message": f"采集完成: {account_name} - {crawled} 条视频, 新增 {new_count} 条",
    }, run_id=run_id)


async def emit_analysis_start(run_id: str, account_name: str, video_count: int):
    """推送: 开始 AI 分析"""
    await get_ws_manager().broadcast({
        "type": "analysis_crawling",
        "run_id": run_id,
        "account_name": account_name,
        "video_count": video_count,
        "message": f"正在 AI 分析 {account_name} 的 {video_count} 条新视频",
    }, run_id=run_id)


async def emit_analysis_done(run_id: str, account_name: str, analyzed: int, tokens: int, duration_ms: int):
    """推送: 分析完成"""
    await get_ws_manager().broadcast({
        "type": "analysis_done",
        "run_id": run_id,
        "account_name": account_name,
        "analyzed": analyzed,
        "tokens": tokens,
        "duration_ms": duration_ms,
        "message": f"分析完成: {account_name} - {analyzed} 条视频, 消耗 {tokens} tokens",
    }, run_id=run_id)


async def emit_error(run_id: str, account_name: str, stage: str, error: str):
    """推送: 错误"""
    await get_ws_manager().broadcast({
        "type": "error",
        "run_id": run_id,
        "account_name": account_name,
        "stage": stage,  # "crawl" | "analysis"
        "error": error,
        "message": f"{stage} 失败: {account_name} - {error}",
    }, run_id=run_id)


async def emit_monitor_done(run_id: str, stats: dict, status: str = "success"):
    """推送: 监控结束"""
    await get_ws_manager().broadcast({
        "type": "monitor_done",
        "run_id": run_id,
        "status": status,
        "stats": stats,
        "message": (
            f"监控完成: 扫描 {stats.get('total', 0)}, "
            f"新增 {stats.get('new_videos', 0)} 条视频, "
            f"分析 {stats.get('analyzed', 0)} 条"
        ),
    }, run_id=run_id)
