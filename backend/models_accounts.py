"""models_accounts.py - 账号/视频模块的 Pydantic 数据模型

与 schema_accounts.sql 中的 accounts / videos 表字段对齐
"""
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# 请求模型
# ============================================================
class AddAccountRequest(BaseModel):
    """POST /add_account 入参: 添加一个竞争对手账号"""
    platform: str                          # 'douyin' | 'tiktok' | 'youtube'
    platform_uid: str                      # 平台内账号唯一 ID (抖音为 sec_user_id)
    name: str                              # 昵称/展示名
    handle: Optional[str] = None           # @账号 (可空)
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0


class CrawlAccountRequest(BaseModel):
    """POST /crawl_account 入参: 触发某账号的爬虫

    两种用法:
      1. 传 account_id  -> 从库中查 platform/uid, 自动拼接 URL 爬取
      2. 传 url         -> 直接爬该 URL (若提供 account_id 则结果归到该账号)
    """
    account_id: Optional[str] = None
    url: Optional[str] = None
    max_videos: int = Field(default=30, ge=1, le=100)


# ============================================================
# 响应模型
# ============================================================
class AccountOut(BaseModel):
    """账号信息"""
    id: str
    platform: str
    platform_uid: str
    name: str
    handle: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    follower_count: int = 0
    following_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class VideoOut(BaseModel):
    """视频信息"""
    id: str
    account_id: str
    platform_vid: str
    title: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    video_url: Optional[str] = None
    duration_sec: Optional[int] = None
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    published_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CrawlResult(BaseModel):
    """爬取结果"""
    account_id: str
    account_name: Optional[str] = None
    crawled: int                            # 本次新爬取/更新的视频数
    videos: list[VideoOut] = Field(default_factory=list)
