"""main_multi.py - 多平台统一 API 入口

提供统一的爬虫调度接口, 支持 抖音/小红书/YouTube/TikTok 四个平台。
复用现有的 db_accounts.py 数据库操作, 不修改原有架构。

接口:
  POST /crawl              统一爬虫入口 (自动识别平台或手动指定)
  GET  /platforms          列出支持的平台
  POST /add_account        添加账号 (复用)
  GET  /accounts           列出账号 (复用)
  GET  /videos/{id}        获取视频列表 (复用)

运行:
  cd backend
  uvicorn main_multi:app --reload --port 8003
"""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# 复用现有模块
from db_accounts import (
    insert_account,
    get_account,
    list_accounts,
    upsert_video,
    list_videos_by_account,
    count_videos_by_account,
)
from crawler_manager import (
    run_crawler,
    crawl_and_save,
    build_profile_url,
    detect_platform_from_url,
    get_supported_platforms,
)
from models_accounts import AccountOut, VideoOut, AddAccountRequest

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(
    title="AI 竞争情报系统 - 多平台采集模块",
    description="统一接口: 抖音/小红书/YouTube/TikTok 视频采集",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 请求/响应模型 (多平台扩展)
# ============================================================
class CrawlRequest(BaseModel):
    """统一爬虫请求

    用法:
      A) 传 url, 自动检测平台: {url, max_videos}
      B) 传 platform + url: {platform:"xiaohongshu", url:"...", max_videos}
      C) 传 account_id: {account_id, max_videos} (从库中查 platform/uid 拼 URL)
    """
    platform: Optional[str] = Field(
        default=None,
        description="平台: douyin/xiaohongshu/youtube/tiktok (不传则自动检测)",
    )
    url: Optional[str] = Field(default=None, description="目标账号主页 URL")
    account_id: Optional[str] = Field(default=None, description="已有账号 ID")
    max_videos: int = Field(default=30, ge=1, le=100)
    save_to_db: bool = Field(default=True, description="是否写入数据库")


class CrawlResponse(BaseModel):
    """统一爬虫响应"""
    ok: bool
    platform: str
    account_id: Optional[str] = None
    account_name: str = ""
    follower_count: int = 0
    crawled: int = 0
    videos: list[VideoOut] = Field(default_factory=list)


# ============================================================
# 接口 1: POST /crawl — 统一爬虫入口
# ============================================================
@app.post("/crawl", response_model=CrawlResponse)
def crawl(req: CrawlRequest):
    """统一爬虫入口, 支持自动平台检测或手动指定"""

    # ---- 确定平台与 URL ----
    if req.account_id:
        # 用法 C: 从库中查账号
        account = get_account(req.account_id)
        if not account:
            raise HTTPException(status_code=404, detail="账号不存在")
        platform = account["platform"]
        target_url = req.url or build_profile_url(
            platform, account["platform_uid"]
        )
    elif req.url:
        # 用法 A/B: 从 URL 推断或手动指定
        target_url = req.url
        platform = req.platform or detect_platform_from_url(req.url)
        if not platform:
            raise HTTPException(
                status_code=400,
                detail=f"无法从 URL 识别平台, 请手动指定 platform 参数",
            )
    else:
        raise HTTPException(status_code=400, detail="请提供 url 或 account_id")

    # ---- 执行爬虫 ----
    if req.save_to_db:
        # 爬取 + 入库
        try:
            result = crawl_and_save(
                platform=platform,
                url=target_url,
                account_id=req.account_id,
                max_videos=req.max_videos,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
    else:
        # 仅爬取不入库
        try:
            result = run_crawler(platform, target_url, req.max_videos)
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
        result = {
            "account_id": None,
            "platform": result.get("platform", platform),
            "account_name": result.get("account_name", ""),
            "follower_count": result.get("follower_count", 0),
            "crawled": len(result.get("videos", [])),
            "videos": result.get("videos", []),
        }

    return CrawlResponse(
        ok=True,
        platform=result.get("platform", platform),
        account_id=result.get("account_id"),
        account_name=result.get("account_name", ""),
        follower_count=result.get("follower_count", 0),
        crawled=result.get("crawled", 0),
        videos=[VideoOut(**v) if isinstance(v, dict) and "id" in v else VideoOut(
            id="", account_id=result.get("account_id") or "",
            platform_vid=v.get("video_id", ""),
            title=v.get("title"),
            description=v.get("description"),
            cover_url=v.get("cover_url"),
            video_url=v.get("video_url"),
            duration_sec=None,
            view_count=v.get("views", 0),
            like_count=v.get("likes", 0),
            comment_count=v.get("comments", 0),
            share_count=v.get("shares", 0),
            published_at=v.get("publish_time"),
            created_at=None,
            updated_at=None,
        ) for v in result.get("videos", [])],
    )


# ============================================================
# 接口 2: GET /platforms — 支持的平台列表
# ============================================================
@app.get("/platforms")
def platforms():
    """返回支持的平台列表及爬虫状态"""
    platforms_info = get_supported_platforms()
    return {
        "platforms": [
            {
                "platform": p["platform"],
                "script_ready": p["script_exists"],
                "url_template": {
                    "douyin": "https://www.douyin.com/user/{uid}",
                    "xiaohongshu": "https://www.xiaohongshu.com/user/profile/{uid}",
                    "youtube": "https://www.youtube.com/@{handle}/videos",
                    "tiktok": "https://www.tiktok.com/@{username}",
                }.get(p["platform"], ""),
            }
            for p in platforms_info
        ]
    }


# ============================================================
# 接口 3: POST /add_account — 添加账号 (复用)
# ============================================================
@app.post("/add_account", response_model=AccountOut)
def add_account(req: AddAccountRequest):
    """添加竞争对手账号, 支持所有平台"""
    try:
        row = insert_account(
            {
                "platform": req.platform,
                "platform_uid": req.platform_uid,
                "name": req.name,
                "handle": req.handle,
                "avatar_url": req.avatar_url,
                "bio": req.bio,
                "follower_count": req.follower_count,
                "following_count": req.following_count,
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"添加账号失败: {e}")
    return AccountOut(**row)


# ============================================================
# 接口 4: GET /accounts — 列出账号 (复用)
# ============================================================
@app.get("/accounts", response_model=list[AccountOut])
def get_all_accounts(limit: int = Query(100, ge=1, le=500)):
    """列出所有账号, 按创建时间倒序"""
    rows = list_accounts(limit=limit)
    return [AccountOut(**r) for r in rows]


# ============================================================
# 接口 5: GET /videos/{account_id} — 获取视频列表 (复用)
# ============================================================
@app.get("/videos/{account_id}", response_model=list[VideoOut])
def get_videos(account_id: str):
    """返回某账号下所有视频"""
    if not get_account(account_id):
        raise HTTPException(status_code=404, detail="账号不存在")
    rows = list_videos_by_account(account_id)
    return [VideoOut(**r) for r in rows]


# ============================================================
# 接口 6: GET /accounts/{account_id} — 账号详情
# ============================================================
@app.get("/accounts/{account_id}")
def get_account_detail(account_id: str):
    """账号详情 + 视频数"""
    row = get_account(account_id)
    if not row:
        raise HTTPException(status_code=404, detail="账号不存在")
    return {
        "account": AccountOut(**row),
        "video_count": count_videos_by_account(account_id),
    }


# ============================================================
# 健康检查
# ============================================================
@app.get("/health")
def health():
    platforms_info = get_supported_platforms()
    return {
        "status": "ok",
        "platforms": {
            p["platform"]: p["script_exists"] for p in platforms_info
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
