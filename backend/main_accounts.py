"""main_accounts.py - 账号/视频模块 FastAPI 应用

提供三个接口:
  POST /add_account      添加竞争对手账号
  POST /crawl_account    触发爬虫抓取视频并入库
  GET  /videos/{account_id}  获取某账号下的视频列表

运行:
  cd backend
  uvicorn main_accounts:app --reload --port 8001

环境变量(读取项目根 .env):
  SUPABASE_URL / SUPABASE_KEY
  CRAWLER_DOUYIN_SCRIPT  抖音爬虫脚本路径, 默认 ../crawler/douyin/crawl_douyin.js
"""
import os
import json
import subprocess

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models_accounts import (
    AddAccountRequest,
    CrawlAccountRequest,
    AccountOut,
    VideoOut,
    CrawlResult,
)
from db_accounts import (
    insert_account,
    get_account,
    list_accounts,
    upsert_video,
    list_videos_by_account,
    count_videos_by_account,
)

# 加载项目根 .env
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(
    title="AI 竞争情报系统 - 账号/视频模块",
    description="添加账号 / 触发爬虫 / 获取视频列表",
)

# 跨域: 允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 抖音爬虫脚本绝对路径
_DOUYIN_SCRIPT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        os.getenv("CRAWLER_DOUYIN_SCRIPT", "../crawler/douyin/crawl_douyin.js"),
    )
)


# ============================================================
# 平台 URL 拼接: 根据 platform + platform_uid 生成主页 URL
# ============================================================
def _build_profile_url(platform: str, platform_uid: str) -> str:
    """根据平台把账号 UID 拼成可访问的主页 URL"""
    p = platform.lower()
    if p == "douyin":
        return f"https://www.douyin.com/user/{platform_uid}"
    if p == "tiktok":
        return f"https://www.tiktok.com/@{platform_uid}"
    if p == "youtube":
        return f"https://www.youtube.com/{platform_uid}"
    if p == "bilibili":
        return f"https://space.bilibili.com/{platform_uid}"
    # 未知平台: 若 uid 本身像 URL 则直接用, 否则报错
    if platform_uid.startswith("http"):
        return platform_uid
    raise ValueError(f"不支持的平台 '{platform}', 请直接传 url 参数")


# ============================================================
# 调用 Node 爬虫 (子进程, 解析 stdout JSON)
# ============================================================
def _run_douyin_crawler(url: str, max_videos: int) -> dict:
    """调用 node crawl_douyin.js <url> --max=N, 返回解析后的 dict"""
    if not os.path.exists(_DOUYIN_SCRIPT):
        raise RuntimeError(f"爬虫脚本不存在: {_DOUYIN_SCRIPT}")

    try:
        proc = subprocess.run(
            ["node", _DOUYIN_SCRIPT, url, f"--max={max_videos}"],
            capture_output=True,
            text=True,
            timeout=180,  # 爬虫滚动加载可能较久, 给 3 分钟
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("爬虫执行超时 (180s)")
    except FileNotFoundError:
        raise RuntimeError("未找到 node 命令, 请确认 Node.js 已安装")

    # 爬虫把结果以一行 JSON 输出到 stdout
    stdout = proc.stdout.strip()
    if not stdout:
        raise RuntimeError(f"爬虫无输出, stderr: {proc.stderr[:500]}")

    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"爬虫输出解析失败: {stdout[:500]}")


# ============================================================
# 接口 1: POST /add_account —— 添加竞争对手账号
# ============================================================
@app.post("/add_account", response_model=AccountOut)
def add_account(req: AddAccountRequest):
    """添加一个账号; 若 (platform, platform_uid) 已存在则更新快照并返回"""
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
# 接口 2: POST /crawl_account —— 触发爬虫
# ============================================================
@app.post("/crawl_account", response_model=CrawlResult)
def crawl_account(req: CrawlAccountRequest):
    """触发爬虫抓取某账号视频, 结果写入 videos 表

    用法:
      A) 传 account_id: 自动从库中查 platform/uid 拼 URL 爬取
      B) 传 url (+ 可选 account_id): 直接爬该 URL
    """
    # ---- 确定 account_id 与爬取 URL ----
    account_row = None
    if req.account_id:
        account_row = get_account(req.account_id)
        if not account_row:
            raise HTTPException(status_code=404, detail="账号不存在")
        target_url = req.url or _build_profile_url(
            account_row["platform"], account_row["platform_uid"]
        )
        account_id = req.account_id
    elif req.url:
        # 只传 url: 先创建一个占位账号, 爬完拿到 account_name 再更新
        # 这里简单处理: 用 url 作为 platform_uid, platform=douyin (默认)
        target_url = req.url
        row = insert_account(
            {
                "platform": "douyin",
                "platform_uid": req.url,  # 临时用 url, 后续可修正
                "name": "待识别",
            }
        )
        account_id = row["id"]
        account_row = row
    else:
        raise HTTPException(status_code=400, detail="请提供 account_id 或 url")

    # ---- 调用爬虫 ----
    try:
        result = _run_douyin_crawler(target_url, req.max_videos)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if not result.get("ok"):
        raise HTTPException(
            status_code=502,
            detail=f"爬虫失败: {result.get('error', '未知错误')}",
        )

    # ---- 若爬虫返回了账号名且库中名字是占位, 更新之 ----
    crawled_name = result.get("account_name", "")
    if crawled_name and account_row and account_row.get("name") == "待识别":
        sb_row = get_account(account_id)
        if sb_row and sb_row.get("name") == "待识别":
            from db import get_supabase
            get_supabase().table("accounts").update(
                {"name": crawled_name}
            ).eq("id", account_id).execute()

    # ---- 视频入库 (upsert) ----
    videos_raw = result.get("videos", [])
    saved = []
    for v in videos_raw:
        try:
            row = upsert_video(account_id, v)
            saved.append(VideoOut(**row))
        except Exception as e:
            # 单条失败不中断整体流程, 记录到 stderr
            print(f"[crawl_account] 视频 {v.get('video_id')} 入库失败: {e}")

    return CrawlResult(
        account_id=account_id,
        account_name=crawled_name or None,
        crawled=len(saved),
        videos=saved,
    )


# ============================================================
# 接口 3: GET /videos/{account_id} —— 获取视频列表
# ============================================================
@app.get("/videos/{account_id}", response_model=list[VideoOut])
def get_videos(account_id: str):
    """返回某账号下所有视频, 按发布时间倒序"""
    # 先校验账号存在
    if not get_account(account_id):
        raise HTTPException(status_code=404, detail="账号不存在")

    rows = list_videos_by_account(account_id)
    return [VideoOut(**r) for r in rows]


# ============================================================
# 辅助接口: 列出所有账号 (便于前端选择要爬取的账号)
# ============================================================
@app.get("/accounts", response_model=list[AccountOut])
def get_all_accounts():
    """列出所有已添加的账号"""
    rows = list_accounts(limit=100)
    return [AccountOut(**r) for r in rows]


# ============================================================
# 辅助接口: 账号详情 (含视频数统计)
# ============================================================
@app.get("/accounts/{account_id}")
def get_account_detail(account_id: str):
    """账号详情 + 视频总数"""
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
    return {
        "status": "ok",
        "crawler_script": os.path.exists(_DOUYIN_SCRIPT),
        "crawler_path": _DOUYIN_SCRIPT,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
