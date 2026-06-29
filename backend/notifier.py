"""notifier.py — 通知系统

支持 3 种通知渠道:
  1. webhook   — 发送 HTTP POST 到用户配置的 URL (飞书/钉钉/Slack 等)
  2. in_app    — 写入 notifications 表 (前端轮询展示)
  3. email     — 通过 SMTP 发送邮件 (可选)

通知触发流程:
  detector 检测到异常 → create_alert() 写入 alerts 表
  → notifier 查询未通知的 active 告警 → 发送通知 → 记录到 notifications 表
"""
import os
import json
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timezone, timedelta
from typing import Optional
import httpx

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from db import get_supabase

_CST = timezone(timedelta(hours=8))

# ============================================================
# 通知配置
# ============================================================
WEBHOOK_URL = os.getenv("NOTIFY_WEBHOOK_URL", "")        # 通用 Webhook URL
WEBHOOK_HEADERS = json.loads(os.getenv("NOTIFY_WEBHOOK_HEADERS", '{"Content-Type": "application/json"}'))

# SMTP 邮件配置 (可选)
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "")
EMAIL_TO = os.getenv("NOTIFY_EMAIL_TO", "")             # 逗号分隔多个收件人

# 严重度过滤: 只通知 medium 及以上
MIN_SEVERITY = os.getenv("NOTIFY_MIN_SEVERITY", "medium")
_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _severity_rank(s: str) -> int:
    return _SEVERITY_ORDER.get(s, 0)


def _min_severity_rank() -> int:
    return _severity_order.get(MIN_SEVERITY, 1)


# ============================================================
# 主入口: 处理未通知的告警
# ============================================================
def process_pending_alerts():
    """查询所有 active 且未发过通知的告警, 逐条发送

    Returns: {"processed": N, "sent": M, "failed": K}
    """
    sb = get_supabase()
    now = datetime.now(_CST)

    # 查询 active 告警
    alerts = sb.table("alerts").select("*").eq("status", "active").execute()
    processed = sent = failed = 0

    for alert in (alerts.data or []):
        # 严重度过滤
        if _severity_rank(alert.get("severity", "low")) < _min_severity_rank():
            continue

        # 检查是否已发过通知 (避免重复)
        existing = sb.table("notifications").select("id").eq("alert_id", alert["id"]).execute()
        if existing.data:
            continue  # 已通知过

        processed += 1

        # 构造通知内容
        payload = _build_notification_payload(alert)

        # 发送通知 (按优先级: webhook > email > in_app)
        success = False

        if WEBHOOK_URL:
            success = _send_webhook(alert, payload)

        if not success and SMTP_HOST and EMAIL_TO:
            success = _send_email(alert, payload)

        # 无论是否发外部通知, 都写入 in_app 记录
        _create_in_app_notification(alert, payload, "sent" if success else "pending")

        if success:
            sent += 1
        else:
            failed += 1

    return {"processed": processed, "sent": sent, "failed": failed, "time": now.isoformat()}


# ============================================================
# 通知内容构造
# ============================================================
def _build_notification_payload(alert: dict) -> dict:
    """构造通知内容 (飞书/钉钉兼容格式)"""
    severity_emoji = {
        "critical": "🚨", "high": "🔥", "medium": "🔺", "low": "⚠️"
    }.get(alert.get("severity", ""), "⚠️")

    metric_cn = {
        "likes": "点赞", "comments": "评论", "followers": "粉丝"
    }.get(alert.get("metric_name", ""), alert.get("metric_name", ""))

    # 获取关联的视频/账号信息
    title = ""
    if alert.get("video_id"):
        sb = get_supabase()
        v = sb.table("videos").select("title").eq("id", alert["video_id"]).execute()
        if v.data:
            title = v.data[0].get("title", "")

    text = (
        f"{severity_emoji} 异常增长告警\n"
        f"类型: {metric_cn}增长异常\n"
        f"指标: {alert.get('metric_name', '')}\n"
        f"当前值: {alert.get('current_value', 0)}\n"
        f"2h增长: +{alert.get('growth_value', 0)}\n"
        f"增长倍数: {alert.get('growth_rate', 0)}x\n"
        f"Z-score: {alert.get('z_score', 0)}\n"
        f"严重度: {alert.get('severity', '')}\n"
        f"{'🔥 已标记为爆款!' if alert.get('is_viral') else ''}\n"
        f"详情: {alert.get('message', '')}"
    )
    if title:
        text = f"视频: {title}\n" + text

    return {
        "text": text,
        "alert_id": alert.get("id"),
        "severity": alert.get("severity"),
        "is_viral": alert.get("is_viral", False),
    }


# ============================================================
# 渠道: Webhook
# ============================================================
def _send_webhook(alert: dict, payload: dict) -> bool:
    """发送 Webhook 通知 (飞书/钉钉/Slack 兼容)"""
    if not WEBHOOK_URL:
        return False

    # 飞书/钉钉格式: {"msg_type": "text", "content": {"text": "..."}}
    body = {
        "msg_type": "text",
        "content": {"text": payload["text"]},
    }
    # Slack 格式兜底: {"text": "..."}
    if "hooks.slack.com" in WEBHOOK_URL:
        body = {"text": payload["text"]}

    try:
        with httpx.Client(timeout=10) as client:
            resp = client.post(WEBHOOK_URL, headers=WEBHOOK_HEADERS, json=body)
        return resp.status_code in (200, 204)
    except Exception as e:
        print(f"[notifier] Webhook 发送失败: {e}")
        return False


# ============================================================
# 渠道: Email
# ============================================================
def _send_email(alert: dict, payload: dict) -> bool:
    """通过 SMTP 发送邮件通知"""
    if not SMTP_HOST or not EMAIL_TO:
        return False

    subject = f"[CI告警] {alert.get('severity', '').upper()} - {alert.get('metric_name', '')}异常增长"
    msg = MIMEText(payload["text"], "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = EMAIL_TO

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM or SMTP_USER, EMAIL_TO.split(","), msg.as_string())
        return True
    except Exception as e:
        print(f"[notifier] 邮件发送失败: {e}")
        return False


# ============================================================
# 渠道: in_app (写入数据库)
# ============================================================
def _create_in_app_notification(alert: dict, payload: dict, status: str):
    """写入 notifications 表, 供前端轮询展示"""
    sb = get_supabase()
    now = datetime.now(_CST).isoformat()
    sb.table("notifications").insert({
        "alert_id": alert["id"],
        "channel": "in_app",
        "recipient": "all",
        "payload": payload,
        "status": status,
        "sent_at": now if status == "sent" else None,
    }).execute()


# ============================================================
# 工具: 获取未读通知 (供前端调用)
# ============================================================
def get_unread_notifications(limit: int = 20) -> list:
    """获取未读通知列表"""
    sb = get_supabase()
    res = (
        sb.table("notifications")
        .select("id, alert_id, channel, payload, status, created_at, sent_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def mark_notification_read(notification_id: str) -> bool:
    """标记通知为已读"""
    sb = get_supabase()
    sb.table("notifications").update({"status": "sent"}).eq("id", notification_id).execute()
    return True
