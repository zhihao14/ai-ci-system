"""marketplace_service.py — API Marketplace 核心逻辑

职责:
  1. API Key 认证 + 限流 (每分钟/每天)
  2. 封装 3 个开放 API:
     - analyze_video      → 调用 viral_service.analyze_viral()
     - competitor_monitor → 调用 crawler_manager + viral_service
     - generate_strategy  → 调用 content_service.generate_content()
  3. 记录调用日志到 marketplace_logs 表
"""
import time
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import get_supabase

logger = logging.getLogger("marketplace")

_CST = timezone(timedelta(hours=8))


# ============================================================
# API Key 管理
# ============================================================
def create_api_key(
    name: str,
    description: Optional[str] = None,
    plan: str = "free",
    rate_limit_per_min: int = 10,
    rate_limit_per_day: int = 100,
    allowed_apis: list[str] = None,
    user_id: Optional[str] = None,
    tenant_id: Optional[str] = None,
) -> dict:
    """创建 API Key"""
    sb = get_supabase()
    key = "mk_" + secrets.token_hex(24)  # 48 字符, mk_ 前缀

    row = {
        "key": key,
        "name": name,
        "description": description,
        "plan": plan,
        "rate_limit_per_min": rate_limit_per_min,
        "rate_limit_per_day": rate_limit_per_day,
        "allowed_apis": allowed_apis or ["analyze_video", "competitor_monitor", "generate_strategy"],
        "user_id": user_id,
        "tenant_id": tenant_id,
    }
    res = sb.table("api_keys").insert(row).execute()
    return res.data[0] if res.data else {}


def validate_api_key(api_key: str) -> Optional[dict]:
    """验证 API Key, 返回 Key 信息 (含限流配置)

    Returns:
        dict or None: Key 不存在/已禁用/已过期返回 None
    """
    sb = get_supabase()
    res = sb.table("api_keys").select("*").eq("key", api_key).eq("is_active", True).execute()
    if not res.data:
        return None

    key_info = res.data[0]

    # 检查过期
    if key_info.get("expires_at"):
        expires = datetime.fromisoformat(key_info["expires_at"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > expires:
            return None

    return key_info


def check_rate_limit(api_key_id: str, per_min: int, per_day: int) -> tuple[bool, str]:
    """检查限流: 每分钟 + 每天调用次数

    Returns:
        (是否允许, 消息)
    """
    sb = get_supabase()
    now = datetime.now(_CST)
    one_min_ago = (now - timedelta(minutes=1)).isoformat()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()

    # 每分钟调用数
    min_res = (
        sb.table("marketplace_logs")
        .select("id", count="exact")
        .eq("api_key_id", api_key_id)
        .gte("called_at", one_min_ago)
        .execute()
    )
    min_count = min_res.count or 0
    if min_count >= per_min:
        return False, f"频率超限: 每分钟 {min_count}/{per_min} 次, 请稍后重试"

    # 每天调用数
    day_res = (
        sb.table("marketplace_logs")
        .select("id", count="exact")
        .eq("api_key_id", api_key_id)
        .gte("called_at", today_start)
        .execute()
    )
    day_count = day_res.count or 0
    if day_count >= per_day:
        return False, f"额度超限: 今日 {day_count}/{per_day} 次, 明日重置"

    return True, "ok"


def check_api_permission(key_info: dict, api_name: str) -> bool:
    """检查 Key 是否有权限调用指定 API"""
    allowed = key_info.get("allowed_apis", [])
    if isinstance(allowed, str):
        import json
        allowed = json.loads(allowed)
    return api_name in allowed


def update_last_used(api_key_id: str):
    """更新最后使用时间"""
    sb = get_supabase()
    sb.table("api_keys").update({
        "last_used_at": datetime.now(_CST).isoformat(),
    }).eq("id", api_key_id).execute()


# ============================================================
# 调用日志
# ============================================================
def log_api_call(
    api_key_id: Optional[str],
    api_key_name: Optional[str],
    api_name: str,
    endpoint: str,
    method: str = "POST",
    status_code: int = 200,
    response_time_ms: Optional[int] = None,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    request_summary: Optional[dict] = None,
    error: Optional[str] = None,
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> str:
    """记录一次 API 调用到 marketplace_logs, 返回 log_id"""
    sb = get_supabase()
    row = {
        "api_key_id": api_key_id,
        "api_key_name": api_key_name,
        "api_name": api_name,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "response_time_ms": response_time_ms,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "request_summary": request_summary,
        "error": error,
        "client_ip": client_ip,
        "user_agent": user_agent,
    }
    res = sb.table("marketplace_logs").insert(row).execute()
    return res.data[0]["id"] if res.data else ""


def list_logs(api_key_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    """查询调用日志"""
    sb = get_supabase()
    q = sb.table("marketplace_logs").select("*")
    if api_key_id:
        q = q.eq("api_key_id", api_key_id)
    res = q.order("called_at", desc=True).limit(limit).execute()
    return res.data


def get_usage_stats(api_key_id: str) -> dict:
    """获取 Key 的使用统计"""
    sb = get_supabase()
    now = datetime.now(_CST)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    # 今日
    today_res = (
        sb.table("marketplace_logs")
        .select("id, status_code, prompt_tokens, completion_tokens, api_name")
        .eq("api_key_id", api_key_id)
        .gte("called_at", today_start)
        .execute()
    )
    today_data = today_res.data or []
    today_total = len(today_data)
    today_errors = sum(1 for r in today_data if r.get("status_code", 200) >= 400)
    today_tokens = sum(
        (r.get("prompt_tokens", 0) or 0) + (r.get("completion_tokens", 0) or 0)
        for r in today_data
    )

    # 本月
    month_res = (
        sb.table("marketplace_logs")
        .select("id", count="exact")
        .eq("api_key_id", api_key_id)
        .gte("called_at", month_start)
        .execute()
    )
    month_total = month_res.count or 0

    # 按 API 分组
    api_breakdown = {}
    for r in today_data:
        name = r.get("api_name", "unknown")
        if name not in api_breakdown:
            api_breakdown[name] = {"calls": 0, "tokens": 0}
        api_breakdown[name]["calls"] += 1
        api_breakdown[name]["tokens"] += (r.get("prompt_tokens", 0) or 0) + (r.get("completion_tokens", 0) or 0)

    return {
        "today_calls": today_total,
        "today_errors": today_errors,
        "today_tokens": today_tokens,
        "month_calls": month_total,
        "api_breakdown": api_breakdown,
    }


# ============================================================
# 核心 API: analyze_video
# ============================================================
def call_analyze_video(videos: list[dict], model: str = "auto") -> dict:
    """封装: 视频爆款分析

    调用: viral_service.analyze_viral()
    """
    from viral_service import analyze_viral
    from models_viral import VideoInput

    # 转换格式
    video_inputs = [
        VideoInput(
            title=v.get("title", ""),
            like_count=v.get("like_count", 0),
            comment_count=v.get("comment_count", 0),
            share_count=v.get("share_count", 0),
            view_count=v.get("view_count", 0),
            published_at=v.get("published_at"),
            video_url=v.get("video_url"),
        )
        for v in videos
    ]

    result = analyze_viral(videos=video_inputs, model=model)

    return {
        "analysis": {
            "overview": result.overview,
            "viral_reasons": [r.model_dump() for r in result.viral_reasons],
            "title_patterns": [p.model_dump() for p in result.title_patterns],
            "content_tactics": [t.model_dump() for t in result.content_tactics],
            "topic_suggestions": [t.model_dump() for t in result.topic_suggestions],
        },
        "tokens": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "provider": result.provider,
            "model": result.model_used,
        },
    }


# ============================================================
# 核心 API: competitor_monitor
# ============================================================
def call_competitor_monitor(
    platform: str,
    url: str,
    max_videos: int = 20,
    auto_analyze: bool = True,
    analysis_model: str = "auto",
) -> dict:
    """封装: 竞品账号监控

    调用: crawler_manager.crawl_and_save() + viral_service.analyze_viral()
    """
    from crawler_manager import crawl_and_save

    # 1. 采集
    crawl_result = crawl_and_save(
        platform=platform,
        url=url,
        account_id=None,  # 外部调用不直接写库 (或可选写入)
        max_videos=max_videos,
    )

    videos = crawl_result.get("videos", [])
    account_info = crawl_result.get("account_info", {})
    account_id = crawl_result.get("account_id")

    result = {
        "account_id": account_id,
        "account_name": account_info.get("account_name"),
        "platform": platform,
        "crawled": len(videos),
        "new_videos": len(videos),  # 外部调用无已有数据, 全是新视频
        "analyzed": 0,
        "analysis_id": None,
        "analysis_summary": None,
    }

    # 2. AI 分析 (可选)
    if auto_analyze and videos:
        try:
            analysis = call_analyze_video(videos, model=analysis_model)
            result["analyzed"] = len(videos)
            result["analysis_summary"] = analysis["analysis"].get("overview", "")
            result["analysis_detail"] = analysis["analysis"]
            result["tokens"] = analysis["tokens"]
        except Exception as e:
            result["analysis_error"] = str(e)

    return result


# ============================================================
# 核心 API: generate_strategy
# ============================================================
def call_generate_strategy(
    video: dict,
    model: str = "auto",
    topic_count: int = 20,
) -> dict:
    """封装: 运营策略生成

    调用: content_service.generate_content()
    """
    from content_service import generate_content
    from models_content import VideoRef

    video_ref = VideoRef(
        title=video.get("title", ""),
        like_count=video.get("like_count", 0),
        comment_count=video.get("comment_count", 0),
        share_count=video.get("share_count", 0),
        view_count=video.get("view_count", 0),
    )

    result = generate_content(video=video_ref, model=model, count=topic_count)

    return {
        "titles": [t.model_dump() for t in result.titles],
        "scripts": [s.model_dump() for s in result.scripts],
        "topics": [t.model_dump() for t in result.topics],
        "tokens": {
            "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens,
            "provider": result.provider,
            "model": result.model_used,
        },
    }


# ============================================================
# API 产品目录
# ============================================================
def list_api_products() -> list[dict]:
    """列出所有 API 产品"""
    sb = get_supabase()
    res = (
        sb.table("api_products")
        .select("*")
        .eq("is_active", True)
        .order("is_featured", desc=True)
        .execute()
    )
    return res.data


def get_api_product(name: str) -> Optional[dict]:
    """获取单个 API 产品详情"""
    sb = get_supabase()
    res = sb.table("api_products").select("*").eq("name", name).execute()
    return res.data[0] if res.data else None
