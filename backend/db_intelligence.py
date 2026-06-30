"""db_intelligence.py — 智能分析模块的数据库操作"""
from typing import Optional
from db import get_supabase


# ============================================================
# video_analyses CRUD
# ============================================================

def insert_video_analysis(data: dict) -> dict:
    """插入视频分析记录, 返回完整记录"""
    sb = get_supabase()
    row = sb.table("video_analyses").insert(data).execute()
    return row.data[0] if row.data else {}


def update_video_analysis(analysis_id: str, updates: dict) -> dict | None:
    """更新视频分析记录"""
    sb = get_supabase()
    res = sb.table("video_analyses").update(updates).eq("id", analysis_id).execute()
    return res.data[0] if res.data else None


def get_video_analysis(analysis_id: str) -> dict | None:
    """按 id 获取视频分析记录"""
    sb = get_supabase()
    res = sb.table("video_analyses").select("*").eq("id", analysis_id).execute()
    return res.data[0] if res.data else None


def list_video_analyses(limit: int = 20) -> list[dict]:
    """列出最近的视频分析记录"""
    sb = get_supabase()
    res = (
        sb.table("video_analyses")
        .select("id, competitor_id, url, account_name, video_count, ai_provider, created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


# ============================================================
# content_patterns CRUD
# ============================================================

def insert_content_pattern(data: dict) -> dict:
    sb = get_supabase()
    row = sb.table("content_patterns").insert(data).execute()
    return row.data[0] if row.data else {}


def get_content_pattern(analysis_id: str) -> dict | None:
    """按 video_analysis_id 获取内容模式"""
    sb = get_supabase()
    res = sb.table("content_patterns").select("*").eq("video_analysis_id", analysis_id).execute()
    return res.data[0] if res.data else None


# ============================================================
# trend_predictions CRUD
# ============================================================

def insert_trend_prediction(data: dict) -> dict:
    sb = get_supabase()
    row = sb.table("trend_predictions").insert(data).execute()
    return row.data[0] if row.data else {}


def get_trend_prediction(analysis_id: str) -> dict | None:
    sb = get_supabase()
    res = sb.table("trend_predictions").select("*").eq("video_analysis_id", analysis_id).execute()
    return res.data[0] if res.data else None


# ============================================================
# growth_strategies CRUD
# ============================================================

def insert_growth_strategy(data: dict) -> dict:
    sb = get_supabase()
    row = sb.table("growth_strategies").insert(data).execute()
    return row.data[0] if row.data else {}


def get_growth_strategy(analysis_id: str) -> dict | None:
    sb = get_supabase()
    res = sb.table("growth_strategies").select("*").eq("video_analysis_id", analysis_id).execute()
    return res.data[0] if res.data else None


# ============================================================
# competitor_comparisons CRUD
# ============================================================

def insert_comparison(data: dict) -> dict:
    sb = get_supabase()
    row = sb.table("competitor_comparisons").insert(data).execute()
    return row.data[0] if row.data else {}


def list_comparisons(limit: int = 10) -> list[dict]:
    sb = get_supabase()
    res = (
        sb.table("competitor_comparisons")
        .select("id, analysis_ids, ai_provider, created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


# ============================================================
# Dashboard 统计
# ============================================================

def dashboard_stats() -> dict:
    """仪表盘统计数据"""
    sb = get_supabase()

    # 视频分析总数
    va_res = sb.table("video_analyses").select("id", count="exact").execute()
    total_analyses = va_res.count or 0

    # 竞争对手总数
    comp_res = sb.table("competitors").select("id", count="exact").execute()
    total_competitors = comp_res.count or 0

    # 对比总数
    cmp_res = sb.table("competitor_comparisons").select("id", count="exact").execute()
    total_comparisons = cmp_res.count or 0

    # 最近分析
    recent = list_video_analyses(limit=5)

    return {
        "total_analyses": total_analyses,
        "total_competitors": total_competitors,
        "total_comparisons": total_comparisons,
        "recent_analyses": recent,
    }
