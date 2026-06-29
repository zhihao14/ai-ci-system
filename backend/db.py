"""db.py - Supabase 客户端封装"""
import os
from dotenv import load_dotenv
from supabase import create_client, Client

# 加载 .env (默认读取项目根目录的 .env)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# 单例客户端
_supabase: Client | None = None


def get_supabase() -> Client:
    """获取 Supabase 客户端单例"""
    global _supabase
    if _supabase is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise RuntimeError("缺少 SUPABASE_URL / SUPABASE_KEY, 请检查 .env")
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


# ============================================================
# 竞争对手 & 报告
# ============================================================

def upsert_competitor(name: str, url: str) -> str:
    """插入或更新竞争对手, 返回 competitor_id"""
    sb = get_supabase()
    # 先查是否已存在
    existing = sb.table("competitors").select("id").eq("url", url).execute()
    if existing.data:
        return existing.data[0]["id"]
    row = sb.table("competitors").insert({"name": name, "url": url}).execute()
    return row.data[0]["id"]


def insert_report(report: dict) -> dict:
    """插入情报报告, 返回完整记录"""
    sb = get_supabase()
    row = sb.table("intelligence_reports").insert(report).execute()
    return row.data[0]


def list_reports(limit: int = 50) -> list:
    """列出最近的情报报告"""
    sb = get_supabase()
    res = (
        sb.table("intelligence_reports")
        .select("id, url, title, summary, ai_provider, created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


def get_report(report_id: str) -> dict | None:
    """按 id 取单条报告详情"""
    sb = get_supabase()
    res = sb.table("intelligence_reports").select("*").eq("id", report_id).execute()
    return res.data[0] if res.data else None


# ============================================================
# AI 配置 CRUD
# ============================================================

def list_ai_configs() -> list:
    """列出所有 AI 配置, 按 priority 升序"""
    sb = get_supabase()
    res = (
        sb.table("ai_config")
        .select("*")
        .order("priority", desc=False)
        .execute()
    )
    return res.data


def get_active_ai_configs() -> list:
    """获取所有启用的 AI 配置, 按 priority 升序"""
    sb = get_supabase()
    res = (
        sb.table("ai_config")
        .select("*")
        .eq("is_active", True)
        .order("priority", desc=False)
        .execute()
    )
    return res.data


def insert_ai_config(config: dict) -> dict:
    """新增 AI 配置, 返回完整记录"""
    sb = get_supabase()
    row = sb.table("ai_config").insert(config).execute()
    return row.data[0]


def update_ai_config(config_id: str, updates: dict) -> dict | None:
    """更新 AI 配置, 返回更新后的记录"""
    sb = get_supabase()
    res = sb.table("ai_config").update(updates).eq("id", config_id).execute()
    return res.data[0] if res.data else None


def delete_ai_config(config_id: str) -> bool:
    """删除 AI 配置"""
    sb = get_supabase()
    res = sb.table("ai_config").delete().eq("id", config_id).execute()
    return len(res.data) > 0
