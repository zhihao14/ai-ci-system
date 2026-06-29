"""db_auth.py — 用户系统数据库操作 (Supabase CRUD)

所有操作使用 service-role key (绕过 RLS), 适用于后端服务端调用
"""
from typing import Optional
from datetime import datetime, timezone, timedelta

from db import get_supabase

_CST = timezone(timedelta(hours=8))


# ============================================================
# 用户档案
# ============================================================
def get_profile(user_id: str) -> Optional[dict]:
    """获取用户档案"""
    sb = get_supabase()
    res = sb.table("profiles").select("*").eq("id", user_id).execute()
    return res.data[0] if res.data else None


def update_profile(user_id: str, data: dict) -> dict:
    """更新用户档案"""
    sb = get_supabase()
    # 只允许更新安全字段
    safe_fields = {"username", "full_name", "avatar_url", "bio"}
    update_data = {k: v for k, v in data.items() if k in safe_fields}
    if not update_data:
        return get_profile(user_id)
    res = sb.table("profiles").update(update_data).eq("id", user_id).execute()
    return res.data[0] if res.data else {}


def regenerate_api_key(user_id: str) -> str:
    """重新生成 API Key"""
    import secrets
    sb = get_supabase()
    new_key = secrets.token_hex(24)  # 48 字符
    sb.table("profiles").update({"api_key": new_key}).eq("id", user_id).execute()
    return new_key


# ============================================================
# 租户
# ============================================================
def get_tenant(tenant_id: str) -> Optional[dict]:
    """获取租户信息"""
    sb = get_supabase()
    res = sb.table("tenants").select("*").eq("id", tenant_id).execute()
    return res.data[0] if res.data else None


def get_user_tenants(user_id: str) -> list[dict]:
    """获取用户所属的所有租户"""
    sb = get_supabase()
    res = (
        sb.table("tenant_members")
        .select("role, joined_at, tenant:tenants(*)")
        .eq("user_id", user_id)
        .execute()
    )
    # 展平 join 结果
    result = []
    for row in res.data:
        tenant = row.pop("tenant", None)
        if tenant:
            tenant["member_role"] = row.get("role")
            tenant["joined_at"] = row.get("joined_at")
            result.append(tenant)
    return result


def get_current_tenant(user_id: str) -> Optional[dict]:
    """获取用户当前活跃租户"""
    profile = get_profile(user_id)
    if not profile or not profile.get("current_tenant_id"):
        return None
    return get_tenant(profile["current_tenant_id"])


def switch_tenant(user_id: str, tenant_id: str) -> dict:
    """切换当前租户 (需校验用户是否属于该租户)"""
    sb = get_supabase()
    # 校验成员关系
    member = (
        sb.table("tenant_members")
        .select("*")
        .eq("user_id", user_id)
        .eq("tenant_id", tenant_id)
        .execute()
    )
    if not member.data:
        raise PermissionError(f"用户不属于租户 {tenant_id}")

    sb.table("profiles").update({"current_tenant_id": tenant_id}).eq("id", user_id).execute()
    return get_tenant(tenant_id)


def update_tenant(tenant_id: str, data: dict) -> dict:
    """更新租户信息"""
    sb = get_supabase()
    safe_fields = {"name", "plan", "daily_quota", "monthly_quota", "settings"}
    update_data = {k: v for k, v in data.items() if k in safe_fields}
    if not update_data:
        return get_tenant(tenant_id)
    res = sb.table("tenants").update(update_data).eq("id", tenant_id).execute()
    return res.data[0] if res.data else {}


# ============================================================
# 租户成员
# ============================================================
def list_tenant_members(tenant_id: str) -> list[dict]:
    """列出租户所有成员"""
    sb = get_supabase()
    res = (
        sb.table("tenant_members")
        .select("id, role, joined_at, user:profiles(username, full_name, avatar_url)")
        .eq("tenant_id", tenant_id)
        .order("joined_at", desc=False)
        .execute()
    )
    result = []
    for row in res.data:
        user_info = row.pop("user", None) or {}
        row.update(user_info)
        result.append(row)
    return result


def add_tenant_member(tenant_id: str, user_id: str, role: str = "member") -> dict:
    """添加租户成员"""
    sb = get_supabase()
    res = (
        sb.table("tenant_members")
        .insert({"tenant_id": tenant_id, "user_id": user_id, "role": role})
        .execute()
    )
    return res.data[0] if res.data else {}


def update_member_role(tenant_id: str, user_id: str, role: str) -> dict:
    """更新成员角色"""
    sb = get_supabase()
    res = (
        sb.table("tenant_members")
        .update({"role": role})
        .eq("tenant_id", tenant_id)
        .eq("user_id", user_id)
        .execute()
    )
    return res.data[0] if res.data else {}


def remove_tenant_member(tenant_id: str, user_id: str) -> bool:
    """移除租户成员"""
    sb = get_supabase()
    sb.table("tenant_members").delete().eq("tenant_id", tenant_id).eq("user_id", user_id).execute()
    return True


# ============================================================
# API 额度
# ============================================================
def get_tenant_quota(tenant_id: str) -> dict:
    """获取租户额度使用情况 (今天 + 本月)"""
    sb = get_supabase()
    tenant = get_tenant(tenant_id)
    if not tenant:
        raise ValueError(f"租户不存在: {tenant_id}")

    now = datetime.now(_CST)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    tomorrow = (today_start + timedelta(days=1)).isoformat()

    # 今日调用数
    today_res = (
        sb.table("api_usage")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .gte("called_at", today_start.isoformat())
        .execute()
    )
    today_used = today_res.count or 0

    # 本月调用数
    month_res = (
        sb.table("api_usage")
        .select("id", count="exact")
        .eq("tenant_id", tenant_id)
        .gte("called_at", month_start.isoformat())
        .execute()
    )
    month_used = month_res.count or 0

    daily_quota = tenant.get("daily_quota", 100)
    monthly_quota = tenant.get("monthly_quota", 3000)

    return {
        "tenant_id": tenant_id,
        "plan": tenant.get("plan", "free"),
        "daily_quota": daily_quota,
        "monthly_quota": monthly_quota,
        "today_used": today_used,
        "month_used": month_used,
        "today_remaining": max(0, daily_quota - today_used),
        "month_remaining": max(0, monthly_quota - month_used),
        "today_reset_at": tomorrow,
    }


def check_quota(tenant_id: str) -> tuple[bool, str]:
    """检查额度是否可用, 返回 (是否可用, 消息)"""
    try:
        quota = get_tenant_quota(tenant_id)
        if quota["today_remaining"] <= 0:
            return False, f"今日额度已用完 ({quota['today_used']}/{quota['daily_quota']}), 明日重置"
        if quota["month_remaining"] <= 0:
            return False, f"本月额度已用完 ({quota['month_used']}/{quota['monthly_quota']})"
        return True, "ok"
    except Exception as e:
        return False, f"额度检查失败: {e}"


def record_usage(
    user_id: Optional[str],
    tenant_id: Optional[str],
    endpoint: str,
    method: str = "POST",
    status_code: int = 200,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> dict:
    """记录一次 API 调用"""
    sb = get_supabase()
    row = {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }
    res = sb.table("api_usage").insert(row).execute()
    return res.data[0] if res.data else {}


def list_usage(
    tenant_id: Optional[str] = None,
    user_id: Optional[str] = None,
    endpoint: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """查询调用记录"""
    sb = get_supabase()
    q = sb.table("api_usage").select("*")

    if tenant_id:
        q = q.eq("tenant_id", tenant_id)
    if user_id:
        q = q.eq("user_id", user_id)
    if endpoint:
        q = q.eq("endpoint", endpoint)

    # 总数
    count_res = q.execute()
    total = len(count_res.data)

    # 分页
    items = (
        q.order("called_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )

    return {"total": total, "items": items.data}


# ============================================================
# API Key 认证
# ============================================================
def get_user_by_api_key(api_key: str) -> Optional[dict]:
    """通过 API Key 查找用户 + 当前租户"""
    sb = get_supabase()
    res = (
        sb.table("profiles")
        .select("*")
        .eq("api_key", api_key)
        .execute()
    )
    if not res.data:
        return None

    profile = res.data[0]
    user_id = profile["id"]

    # 获取当前租户
    tenant = None
    if profile.get("current_tenant_id"):
        tenant = get_tenant(profile["current_tenant_id"])

    return {
        "user_id": user_id,
        "profile": profile,
        "tenant": tenant,
        "tenant_id": profile.get("current_tenant_id"),
    }
