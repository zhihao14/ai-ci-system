"""models_auth.py — 用户系统 Pydantic 数据模型"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


# ============================================================
# 注册 / 登录
# ============================================================
class RegisterRequest(BaseModel):
    """注册请求 (前端调 Supabase Auth, 此模型仅做后端校验参考)"""
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)
    username: Optional[str] = Field(None, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)


class LoginRequest(BaseModel):
    """登录请求"""
    email: EmailStr
    password: str


# ============================================================
# 用户档案
# ============================================================
class ProfileResponse(BaseModel):
    """用户档案响应"""
    id: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    current_tenant_id: Optional[str] = None
    api_key: Optional[str] = None
    created_at: Optional[str] = None


class ProfileUpdate(BaseModel):
    """更新用户档案"""
    username: Optional[str] = Field(None, max_length=50)
    full_name: Optional[str] = Field(None, max_length=100)
    avatar_url: Optional[str] = None
    bio: Optional[str] = Field(None, max_length=500)


# ============================================================
# 租户
# ============================================================
class TenantResponse(BaseModel):
    """租户信息"""
    id: str
    name: str
    slug: str
    plan: str = "free"
    daily_quota: int = 100
    monthly_quota: int = 3000
    is_active: bool = True
    settings: dict = {}
    created_at: Optional[str] = None


class TenantUpdate(BaseModel):
    """更新租户"""
    name: Optional[str] = Field(None, max_length=100)
    plan: Optional[str] = Field(None, pattern="^(free|pro|enterprise)$")
    daily_quota: Optional[int] = Field(None, ge=1, le=100000)
    monthly_quota: Optional[int] = Field(None, ge=1, le=1000000)
    settings: Optional[dict] = None


class TenantMemberResponse(BaseModel):
    """租户成员"""
    id: str
    tenant_id: str
    user_id: str
    role: str
    joined_at: Optional[str] = None
    # 关联用户信息 (join 查询)
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class InviteMemberRequest(BaseModel):
    """邀请成员"""
    email: EmailStr
    role: str = Field("member", pattern="^(admin|member)$")


# ============================================================
# 额度
# ============================================================
class QuotaResponse(BaseModel):
    """额度信息"""
    tenant_id: str
    plan: str = "free"
    daily_quota: int = 100
    monthly_quota: int = 3000
    today_used: int = 0
    month_used: int = 0
    today_remaining: int = 100
    month_remaining: int = 3000
    today_reset_at: Optional[str] = None  # 额度重置时间 (次日0点)


class UsageRecord(BaseModel):
    """单条 API 调用记录"""
    id: str
    endpoint: str
    method: str = "POST"
    status_code: int = 200
    prompt_tokens: int = 0
    completion_tokens: int = 0
    called_at: Optional[str] = None


class UsageListResponse(BaseModel):
    """额度使用列表"""
    total: int
    items: list[UsageRecord]
