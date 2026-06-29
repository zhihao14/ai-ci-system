"""crawler_manager.py - 多平台爬虫统一调度器

职责:
1. 根据 platform 字段路由到对应的 Node.js 爬虫脚本
2. 以子进程方式调用, 解析 stdout JSON
3. 返回统一的 CrawlResult 结构

支持的 4 个平台:
  - douyin        → crawler/douyin/crawl_douyin.js
  - xiaohongshu   → crawler/xiaohongshu/crawl_xiaohongshu.js
  - youtube       → crawler/youtube/crawl_youtube.js
  - tiktok        → crawler/tiktok/crawl_tiktok.js

不修改原有架构: 复用现有 db_accounts.py 的 upsert_video 等函数
"""
import os
import json
import subprocess
from typing import Optional
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ============================================================
# 平台 → 爬虫脚本 路由表
# ============================================================
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)

CRAWLER_SCRIPTS = {
    "douyin": os.path.join(_PROJECT_ROOT, "crawler", "douyin", "crawl_douyin.js"),
    "xiaohongshu": os.path.join(_PROJECT_ROOT, "crawler", "xiaohongshu", "crawl_xiaohongshu.js"),
    "youtube": os.path.join(_PROJECT_ROOT, "crawler", "youtube", "crawl_youtube.js"),
    "tiktok": os.path.join(_PROJECT_ROOT, "crawler", "tiktok", "crawl_tiktok.js"),
}

# ============================================================
# 平台 → 主页 URL 模板
# ============================================================
PROFILE_URL_TEMPLATES = {
    "douyin": "https://www.douyin.com/user/{uid}",
    "xiaohongshu": "https://www.xiaohongshu.com/user/profile/{uid}",
    "youtube": "https://www.youtube.com/@{uid}/videos",
    "tiktok": "https://www.tiktok.com/@{uid}",
}


def get_supported_platforms() -> list:
    """返回支持的平台列表 (含脚本是否存在状态)"""
    return [
        {
            "platform": p,
            "script_exists": os.path.exists(script),
            "script_path": script,
        }
        for p, script in CRAWLER_SCRIPTS.items()
    ]


def build_profile_url(platform: str, platform_uid: str) -> str:
    """根据平台 + UID 拼接主页 URL"""
    p = platform.lower()
    template = PROFILE_URL_TEMPLATES.get(p)
    if template:
        return template.format(uid=platform_uid)
    # 未知平台: 若 uid 本身是 URL 则直接用
    if platform_uid.startswith("http"):
        return platform_uid
    raise ValueError(f"不支持的平台 '{platform}'")


def detect_platform_from_url(url: str) -> Optional[str]:
    """从 URL 自动推断平台"""
    host = urlparse(url).netloc.lower()
    if "douyin.com" in host:
        return "douyin"
    if "xiaohongshu.com" in host or "xhslink.com" in host:
        return "xiaohongshu"
    if "youtube.com" in host or "youtu.be" in host:
        return "youtube"
    if "tiktok.com" in host:
        return "tiktok"
    return None


def run_crawler(
    platform: str,
    url: str,
    max_videos: int = 30,
    timeout: int = 180,
) -> dict:
    """统一爬虫调用入口

    Args:
        platform: 平台名 (douyin/xiaohongshu/youtube/tiktok)
        url:     目标账号主页 URL
        max_videos: 最大爬取数
        timeout: 子进程超时秒数

    Returns:
        dict: 爬虫输出的统一 JSON
            { ok, platform, account_url, account_name, account_id,
              follower_count, count, videos: [...] }

    Raises:
        RuntimeError: 爬虫脚本不存在 / 执行失败 / 输出解析失败
    """
    p = platform.lower()
    script = CRAWLER_SCRIPTS.get(p)
    if not script:
        raise RuntimeError(f"不支持的平台: {platform}")

    if not os.path.exists(script):
        raise RuntimeError(f"爬虫脚本不存在: {script}")

    try:
        proc = subprocess.run(
            ["node", script, url, f"--max={max_videos}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"爬虫执行超时 ({timeout}s)")
    except FileNotFoundError:
        raise RuntimeError("未找到 node 命令, 请确认 Node.js 已安装")

    stdout = proc.stdout.strip()
    if not stdout:
        stderr = proc.stderr[:500] if proc.stderr else ""
        raise RuntimeError(f"爬虫无输出, stderr: {stderr}")

    try:
        result = json.loads(stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"爬虫输出解析失败: {stdout[:500]}")

    if not result.get("ok"):
        raise RuntimeError(
            f"爬虫返回错误: {result.get('error', '未知错误')}"
        )

    return result


def crawl_and_save(
    platform: str,
    url: str,
    account_id: Optional[str] = None,
    max_videos: int = 30,
) -> dict:
    """爬取视频并写入数据库 (复用 db_accounts.py)

    若提供 account_id, 视频归到该账号; 否则自动创建/更新账号。

    Returns:
        dict: { account_id, platform, account_name, follower_count,
                crawled, videos }
    """
    from db_accounts import upsert_video, insert_account, get_account

    # 1. 调用爬虫
    result = run_crawler(platform, url, max_videos)

    # 2. 确定 account_id
    if not account_id:
        # 自动创建账号
        account_data = {
            "platform": platform,
            "platform_uid": result.get("account_id") or url,
            "name": result.get("account_name") or "未命名账号",
            "follower_count": result.get("follower_count", 0),
        }
        row = insert_account(account_data)
        account_id = row["id"]
    else:
        # 更新已有账号的粉丝数
        existing = get_account(account_id)
        if not existing:
            raise RuntimeError(f"账号不存在: {account_id}")
        # 更新粉丝数快照
        from db import get_supabase
        get_supabase().table("accounts").update({
            "follower_count": result.get("follower_count", 0),
            "name": result.get("account_name") or existing.get("name"),
        }).eq("id", account_id).execute()

    # 3. 逐条 upsert 视频
    videos_raw = result.get("videos", [])
    saved = []
    for v in videos_raw:
        try:
            row = upsert_video(account_id, v)
            saved.append(row)
        except Exception as e:
            print(f"[crawler_manager] 视频 {v.get('video_id')} 入库失败: {e}")

    return {
        "account_id": account_id,
        "platform": platform,
        "account_name": result.get("account_name", ""),
        "follower_count": result.get("follower_count", 0),
        "crawled": len(saved),
        "videos": saved,
    }
