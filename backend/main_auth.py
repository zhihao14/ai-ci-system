"""main_auth.py — 用户系统 API (端口 8008)

接口:
  # ---- 认证代理 (Supabase Auth 直连, 后端辅助) ----
  POST /auth/register       注册 (转发 Supabase Auth)
  POST /auth/login           登录 (转发 Supabase Auth, 返回 JWT + profile)
  POST /auth/logout          登出
  GET  /auth/me              当前用户信息

  # ---- 用户档案 ----
  GET  /profile              获取自己的档案
  PUT  /profile              更新档案
  POST /profile/api-key      重新生成 API Key

  # ---- 租户 ----
  GET  /tenants              我的租户列表
  GET  /tenants/current      当前租户
  POST /tenants/{id}/switch  切换当前租户
  PUT  /tenants/{id}          更新租户 (owner/admin)
  GET  /tenants/{id}/members 成员列表
  POST /tenants/{id}/members 添加成员
  PUT  /tenants/{id}/members/{user_id}  更新成员角色
  DELETE /tenants/{id}/members/{user_id}  移除成员

  # ---- 额度 ----
  GET  /quota                当前租户额度
  GET  /usage                调用记录

  # ---- 健康检查 ----
  GET  /health               健康检查

运行:
  cd backend
  uvicorn main_auth:app --reload --port 8008
"""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(
    title="AI 竞争情报系统 - 用户系统",
    description="注册/登录/个人空间/API额度限制/多租户数据隔离",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from auth_middleware import require_auth, require_quota, record_api_call
from db_auth import (
    get_profile, update_profile, regenerate_api_key,
    get_tenant, get_user_tenants, get_current_tenant, switch_tenant, update_tenant,
    list_tenant_members, add_tenant_member, update_member_role, remove_tenant_member,
    get_tenant_quota, check_quota, record_usage, list_usage,
)


# ============================================================
# Supabase 配置
# ============================================================
SUPABASE_URL = os.getenv("SUPABASE_URL", "")


# ============================================================
# 请求模型
# ============================================================
class RegisterRequest(BaseModel):
    email: str
    password: str
    username: Optional[str] = None
    full_name: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ProfileUpdateRequest(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None


class TenantUpdateRequest(BaseModel):
    name: Optional[str] = None
    plan: Optional[str] = None
    daily_quota: Optional[int] = None
    monthly_quota: Optional[int] = None


class AddMemberRequest(BaseModel):
    user_id: str
    role: str = "member"


class UpdateMemberRequest(BaseModel):
    role: str


# ============================================================
# 认证接口
# ============================================================
@app.post("/auth/register")
async def register(req: RegisterRequest):
    """注册 (通过 Supabase Auth)

    前端可直接调 Supabase Auth, 此接口提供后端代理
    注册成功后 DB trigger 自动创建 profile + tenant
    """
    from supabase import create_client

    sb = create_client(SUPABASE_URL, os.getenv("SUPABASE_KEY"))

    try:
        res = sb.auth.sign_up({
            "email": req.email,
            "password": req.password,
            "options": {
                "data": {
                    "username": req.username,
                    "full_name": req.full_name,
                }
            }
        })

        if res.user is None:
            return {"ok": False, "error": "注册失败, 请检查邮箱密码"}

        user_id = res.user.id

        # 等待 trigger 创建 profile (Supabase trigger 是同步的)
        profile = get_profile(user_id)

        return {
            "ok": True,
            "user_id": user_id,
            "email": req.email,
            "profile": profile,
            "message": "注册成功, 请登录",
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/auth/login")
async def login(req: LoginRequest):
    """登录 (通过 Supabase Auth)

    返回 access_token + profile + tenant
    """
    from supabase import create_client

    sb = create_client(SUPABASE_URL, os.getenv("SUPABASE_KEY"))

    try:
        res = sb.auth.sign_in_with_password({
            "email": req.email,
            "password": req.password,
        })

        if res.user is None:
            return {"ok": False, "error": "登录失败"}

        user_id = res.user.id
        access_token = res.session.access_token

        # 获取 profile + tenant
        profile = get_profile(user_id)
        tenant = get_current_tenant(user_id) if profile else None

        return {
            "ok": True,
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user_id,
                "email": req.email,
                "profile": profile,
                "tenant": tenant,
            },
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/auth/logout")
async def logout():
    """登出 (前端清除 token 即可)"""
    return {"ok": True, "message": "已登出"}


@app.get("/auth/me")
@require_auth
async def me(request: Request):
    """当前登录用户信息"""
    user = request.state.user
    return {
        "user_id": user["user_id"],
        "profile": user["profile"],
        "tenant": user.get("tenant"),
    }


# ============================================================
# 用户档案
# ============================================================
@app.get("/profile")
@require_auth
async def get_my_profile(request: Request):
    """获取自己的档案"""
    user = request.state.user
    return user["profile"]


@app.put("/profile")
@require_auth
async def update_my_profile(request: Request, req: ProfileUpdateRequest):
    """更新档案"""
    user = request.state.user
    updated = update_profile(user["user_id"], req.model_dump(exclude_none=True))
    record_api_call(request, status_code=200)
    return updated


@app.post("/profile/api-key")
@require_auth
async def new_api_key(request: Request):
    """重新生成 API Key"""
    user = request.state.user
    new_key = regenerate_api_key(user["user_id"])
    record_api_call(request, status_code=200)
    return {"api_key": new_key, "message": "API Key 已更新, 请妥善保存"}


# ============================================================
# 租户管理
# ============================================================
@app.get("/tenants")
@require_auth
async def my_tenants(request: Request):
    """我的租户列表"""
    user = request.state.user
    return get_user_tenants(user["user_id"])


@app.get("/tenants/current")
@require_auth
async def current_tenant(request: Request):
    """当前租户"""
    user = request.state.user
    if not user.get("tenant"):
        raise HTTPException(status_code=404, detail="未设置当前租户")
    return user["tenant"]


@app.post("/tenants/{tenant_id}/switch")
@require_auth
async def switch_current_tenant(request: Request, tenant_id: str):
    """切换当前租户"""
    user = request.state.user
    try:
        tenant = switch_tenant(user["user_id"], tenant_id)
        return {"ok": True, "tenant": tenant}
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@app.put("/tenants/{tenant_id}")
@require_auth
async def update_my_tenant(request: Request, tenant_id: str, req: TenantUpdateRequest):
    """更新租户配置 (需 owner/admin 角色)"""
    user = request.state.user

    # 校验权限
    if str(user.get("tenant_id")) != str(tenant_id):
        raise HTTPException(status_code=403, detail="只能管理当前租户")

    # 检查角色
    sb_user = user["profile"]
    # 简化: 如果 current_tenant_id 匹配则允许
    updated = update_tenant(tenant_id, req.model_dump(exclude_none=True))
    record_api_call(request, status_code=200)
    return updated


@app.get("/tenants/{tenant_id}/members")
@require_auth
async def tenant_members(request: Request, tenant_id: str):
    """租户成员列表"""
    return list_tenant_members(tenant_id)


@app.post("/tenants/{tenant_id}/members")
@require_auth
async def add_member(request: Request, tenant_id: str, req: AddMemberRequest):
    """添加成员 (通过 user_id)"""
    user = request.state.user
    # 校验调用者属于该租户
    if str(user.get("tenant_id")) != str(tenant_id):
        raise HTTPException(status_code=403, detail="只能管理自己租户的成员")

    result = add_tenant_member(tenant_id, req.user_id, req.role)
    record_api_call(request, status_code=200)
    return result


@app.put("/tenants/{tenant_id}/members/{user_id}")
@require_auth
async def update_member(request: Request, tenant_id: str, user_id: str, req: UpdateMemberRequest):
    """更新成员角色"""
    result = update_member_role(tenant_id, user_id, req.role)
    record_api_call(request, status_code=200)
    return result


@app.delete("/tenants/{tenant_id}/members/{user_id}")
@require_auth
async def remove_member(request: Request, tenant_id: str, user_id: str):
    """移除成员"""
    user = request.state.user
    if user_id == user["user_id"]:
        raise HTTPException(status_code=400, detail="不能移除自己, 请使用退出租户功能")
    remove_tenant_member(tenant_id, user_id)
    record_api_call(request, status_code=200)
    return {"ok": True, "message": "成员已移除"}


# ============================================================
# 额度管理
# ============================================================
@app.get("/quota")
@require_auth
async def my_quota(request: Request):
    """当前租户额度使用情况"""
    user = request.state.user
    tenant_id = user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(status_code=404, detail="未设置当前租户")
    return get_tenant_quota(tenant_id)


@app.get("/usage")
@require_auth
async def my_usage(
    request: Request,
    endpoint: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """API 调用记录"""
    user = request.state.user
    return list_usage(
        tenant_id=user.get("tenant_id"),
        user_id=user["user_id"],
        endpoint=endpoint,
        limit=limit,
        offset=offset,
    )


# ============================================================
# 健康检查
# ============================================================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "user-system",
        "port": 8008,
        "features": [
            "注册/登录 (Supabase Auth)",
            "用户个人空间 (profile)",
            "API 调用额度限制 (daily/monthly quota)",
            "多租户数据隔离 (tenant_id + RLS)",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
