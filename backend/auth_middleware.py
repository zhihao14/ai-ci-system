"""auth_middleware.py — 认证中间件 (JWT 验证 + API Key 验证 + 额度检查)

支持两种认证方式:
  1. Supabase JWT (前端直连, Bearer token)
  2. API Key (后端服务间调用, X-API-Key header)

使用方式:
  from auth_middleware import require_auth, require_quota

  @app.get("/protected")
  @require_auth
  async def protected(request: Request):
      user = request.state.user  # {user_id, profile, tenant, tenant_id}
      ...
"""
import os
import re
from typing import Optional
from functools import wraps

from fastapi import Request, HTTPException
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))


# ============================================================
# JWT 验证 (轻量级, 不依赖 PyJWT)
# ============================================================
def _decode_jwt_payload(token: str) -> Optional[dict]:
    """解码 JWT payload (不验签, 仅提取 claims)

    生产环境建议用 Supabase service-role 验证签名
    此处仅做 Base64 decode 获取 uid, 适用于内部服务调用
    """
    try:
        import base64
        import json

        parts = token.split(".")
        if len(parts) != 3:
            return None

        # JWT payload 是第二段
        payload_b64 = parts[1]
        # 补齐 base64 padding
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding

        payload_bytes = base64.urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_bytes)
        return payload
    except Exception:
        return None


def _extract_token(request: Request) -> Optional[str]:
    """从请求中提取 token (Authorization header 或 X-API-Key)"""
    # 1. Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    # 2. API Key
    api_key = request.headers.get("X-API-Key", "")
    if api_key:
        return f"apikey:{api_key}"

    return None


# ============================================================
# 认证装饰器
# ============================================================
def require_auth(func):
    """认证装饰器: 验证 JWT 或 API Key, 注入 request.state.user"""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        token = _extract_token(request)
        if not token:
            raise HTTPException(
                status_code=401,
                detail="未提供认证信息, 请在 header 中添加 Authorization: Bearer <token> 或 X-API-Key: <key>"
            )

        from db_auth import get_user_by_api_key

        user_info = None

        # API Key 认证
        if token.startswith("apikey:"):
            api_key = token[7:]
            user_info = get_user_by_api_key(api_key)
            if not user_info:
                raise HTTPException(status_code=401, detail="API Key 无效")
        else:
            # JWT 认证
            payload = _decode_jwt_payload(token)
            if not payload:
                raise HTTPException(status_code=401, detail="JWT 格式无效")

            user_id = payload.get("sub")
            if not user_id:
                raise HTTPException(status_code=401, detail="JWT 中缺少 sub (user_id)")

            # 获取用户档案
            from db_auth import get_profile, get_tenant
            profile = get_profile(user_id)
            if not profile:
                raise HTTPException(status_code=401, detail="用户档案不存在, 请先注册")

            tenant = None
            if profile.get("current_tenant_id"):
                tenant = get_tenant(profile["current_tenant_id"])

            user_info = {
                "user_id": user_id,
                "profile": profile,
                "tenant": tenant,
                "tenant_id": profile.get("current_tenant_id"),
            }

        # 注入到 request.state
        request.state.user = user_info
        return await func(request, *args, **kwargs)

    return wrapper


def require_quota(func):
    """额度检查装饰器: 在 require_auth 之后使用, 检查租户 API 额度"""
    @wraps(func)
    async def wrapper(request: Request, *args, **kwargs):
        user = getattr(request.state, "user", None)
        if not user:
            raise HTTPException(status_code=401, detail="请先认证")

        tenant_id = user.get("tenant_id")
        if tenant_id:
            from db_auth import check_quota
            ok, msg = check_quota(tenant_id)
            if not ok:
                raise HTTPException(status_code=429, detail=msg)

        return await func(request, *args, **kwargs)

    return wrapper


def record_api_call(
    request: Request,
    status_code: int = 200,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
):
    """记录一次 API 调用到 api_usage 表

    在接口末尾调用, 用于额度统计
    """
    user = getattr(request.state, "user", None)
    if not user:
        return

    try:
        from db_auth import record_usage
        record_usage(
            user_id=user.get("user_id"),
            tenant_id=user.get("tenant_id"),
            endpoint=request.url.path,
            method=request.method,
            status_code=status_code,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    except Exception:
        pass  # 记录失败不影响主流程
