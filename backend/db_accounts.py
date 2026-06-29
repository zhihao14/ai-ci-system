"""db_accounts.py - accounts / videos 表的数据库操作

复用 db.py 的 Supabase 单例客户端
"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from db import get_supabase

# 东八区, 用于把爬虫返回的 "YYYY-MM-DD HH:mm:ss" 转成带时区的 ISO 时间
_CST = timezone(timedelta(hours=8))


# ============================================================
# accounts 表操作
# ============================================================
def insert_account(data: dict) -> dict:
    """插入账号; 若 (platform, platform_uid) 已存在则返回已有记录

    Returns: 完整的 account 行
    """
    sb = get_supabase()
    # 先查是否已存在 (业务唯一键 platform + platform_uid)
    existing = (
        sb.table("accounts")
        .select("*")
        .eq("platform", data["platform"])
        .eq("platform_uid", data["platform_uid"])
        .execute()
    )
    if existing.data:
        # 已存在则更新可变字段 (粉丝数等快照)
        row = existing.data[0]
        updates = {
            k: v for k, v in data.items()
            if k in ("name", "handle", "avatar_url", "bio",
                     "follower_count", "following_count")
        }
        if updates:
            sb.table("accounts").update(updates).eq("id", row["id"]).execute()
            # 重新查一次拿到 updated_at
            refreshed = sb.table("accounts").select("*").eq("id", row["id"]).execute()
            return refreshed.data[0]
        return row

    # 不存在则插入
    row = sb.table("accounts").insert(data).execute()
    return row.data[0]


def get_account(account_id: str) -> Optional[dict]:
    """按 id 查单个账号"""
    sb = get_supabase()
    res = sb.table("accounts").select("*").eq("id", account_id).execute()
    return res.data[0] if res.data else None


def list_accounts(limit: int = 100) -> list:
    """列出所有账号"""
    sb = get_supabase()
    res = (
        sb.table("accounts")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


# ============================================================
# videos 表操作
# ============================================================
def upsert_video(account_id: str, video: dict) -> dict:
    """插入或更新单条视频 (按 account_id + platform_vid 去重)

    video 字段来自爬虫: video_id, title, likes, comments, shares,
                       publish_time, video_url, cover_url
    """
    sb = get_supabase()
    platform_vid = video["video_id"]

    # 映射爬虫字段 -> 数据库字段
    published_at = _parse_publish_time(video.get("publish_time"))
    row = {
        "account_id": account_id,
        "platform_vid": platform_vid,
        "title": video.get("title"),
        "cover_url": video.get("cover_url"),
        "video_url": video.get("video_url"),
        "like_count": video.get("likes", 0),
        "comment_count": video.get("comments", 0),
        "share_count": video.get("shares", 0),
        "view_count": video.get("views", 0),
        "published_at": published_at,
    }

    # 先查是否已存在
    existing = (
        sb.table("videos")
        .select("id")
        .eq("account_id", account_id)
        .eq("platform_vid", platform_vid)
        .execute()
    )
    if existing.data:
        # 已存在 -> 更新统计快照
        vid = existing.data[0]["id"]
        res = sb.table("videos").update(row).eq("id", vid).execute()
        return res.data[0]
    # 不存在 -> 插入
    res = sb.table("videos").insert(row).execute()
    return res.data[0]


def list_videos_by_account(account_id: str) -> list:
    """列出某账号下所有视频, 按发布时间倒序"""
    sb = get_supabase()
    res = (
        sb.table("videos")
        .select("*")
        .eq("account_id", account_id)
        .order("published_at", desc=True, nulls_first=False)
        .execute()
    )
    return res.data


def count_videos_by_account(account_id: str) -> int:
    """统计某账号下视频数量"""
    sb = get_supabase()
    res = (
        sb.table("videos")
        .select("id", count="exact")
        .eq("account_id", account_id)
        .execute()
    )
    return res.count or 0


# ============================================================
# 工具函数
# ============================================================
def _parse_publish_time(s: Optional[str]) -> Optional[str]:
    """把爬虫返回的 'YYYY-MM-DD HH:mm:ss' 转成 ISO 8601 带时区字符串

    Supabase 的 timestamptz 列接受 ISO 格式。返回 None 表示无发布时间。
    """
    if not s:
        return None
    try:
        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_CST)
        return dt.isoformat()
    except (ValueError, TypeError):
        # 可能已经是 ISO 格式, 原样返回
        return s
