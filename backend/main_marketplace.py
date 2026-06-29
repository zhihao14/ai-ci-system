"""main_marketplace.py — API Marketplace (端口 8011)

允许外部开发者通过 API Key 接入系统, 调用 3 个开放 API:
  POST /v1/analyze_video       视频爆款分析
  POST /v1/competitor_monitor   竞品账号监控
  POST /v1/generate_strategy    运营策略生成

认证方式: Header X-API-Key: mk_xxxxxxxx
限流: 每分钟 + 每天 (按 Key 套餐配置)

管理接口:
  GET  /products               API 产品目录
  GET  /products/{name}        单个产品详情
  POST /keys                   创建 API Key
  GET  /keys                   列出 API Key
  DELETE /keys/{id}            删除 Key
  GET  /keys/{id}/usage        Key 使用统计
  GET  /keys/{id}/logs         Key 调用日志
  GET  /health                 健康检查

运行:
  cd backend
  uvicorn main_marketplace:app --reload --port 8011
"""
import os
import time
import logging
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ============================================================
# 日志
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("marketplace")

# ============================================================
# FastAPI
# ============================================================
app = FastAPI(
    title="AI 竞争情报系统 - API Marketplace",
    description="开放 API 市场, 允许外部开发者通过 API Key 接入系统",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开放 API, 允许所有来源
    allow_methods=["*"],
    allow_headers=["*"],
)

from marketplace_service import (
    create_api_key, validate_api_key, check_rate_limit,
    check_api_permission, update_last_used, log_api_call,
    list_logs, get_usage_stats, list_api_products, get_api_product,
    call_analyze_video, call_competitor_monitor, call_generate_strategy,
)
from models_marketplace import (
    CreateKeyRequest, AnalyzeVideoRequest, CompetitorMonitorRequest,
    GenerateStrategyRequest,
)


# ============================================================
# 认证 + 限流中间件
# ============================================================
def authenticate_and_limit(request: Request, api_name: str) -> dict:
    """统一的认证 + 限流检查

    Args:
        request: FastAPI Request
        api_name: 被调用的 API 名称

    Returns:
        key_info dict

    Raises:
        HTTPException 401/403/429
    """
    # 1. 提取 API Key
    api_key = request.headers.get("X-API-Key", "")
    if not api_key:
        # 也支持 Authorization: Bearer mk_xxx
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            api_key = auth_header[7:].strip()

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "missing_api_key",
                "message": "请在 header 中添加 X-API-Key: mk_xxxxxxxx",
            },
        )

    # 2. 验证 Key
    key_info = validate_api_key(api_key)
    if not key_info:
        raise HTTPException(
            status_code=401,
            detail={"error": "invalid_api_key", "message": "API Key 无效或已过期"},
        )

    # 3. 检查 API 权限
    if not check_api_permission(key_info, api_name):
        raise HTTPException(
            status_code=403,
            detail={
                "error": "api_not_allowed",
                "message": f"此 Key 无权调用 {api_name}, 允许的 API: {key_info.get('allowed_apis')}",
            },
        )

    # 4. 检查限流
    ok, msg = check_rate_limit(
        key_info["id"],
        key_info.get("rate_limit_per_min", 10),
        key_info.get("rate_limit_per_day", 100),
    )
    if not ok:
        raise HTTPException(
            status_code=429,
            detail={"error": "rate_limit_exceeded", "message": msg},
        )

    # 5. 更新最后使用时间
    update_last_used(key_info["id"])

    return key_info


# ============================================================
# 开放 API 1: POST /v1/analyze_video
# ============================================================
@app.post("/v1/analyze_video")
def api_analyze_video(req: AnalyzeVideoRequest, request: Request):
    """视频爆款分析

    输入视频数据数组, AI 提炼爆款规律, 返回:
    - overview: 总体概述
    - viral_reasons: 爆款原因
    - title_patterns: 标题结构
    - content_tactics: 内容套路
    - topic_suggestions: 选题建议

    认证: X-API-Key header
    """
    request_id = str(uuid.uuid4())[:8]
    key_info = authenticate_and_limit(request, "analyze_video")

    start = time.time()
    status_code = 200
    error_msg = None

    try:
        videos_data = [v.model_dump() for v in req.videos]
        result = call_analyze_video(videos=videos_data, model=req.model)

        response_time_ms = int((time.time() - start) * 1000)
        tokens = result.get("tokens", {})

        # 记录日志
        log_api_call(
            api_key_id=key_info["id"],
            api_key_name=key_info["name"],
            api_name="analyze_video",
            endpoint="/v1/analyze_video",
            status_code=200,
            response_time_ms=response_time_ms,
            prompt_tokens=tokens.get("prompt_tokens", 0),
            completion_tokens=tokens.get("completion_tokens", 0),
            request_summary={"video_count": len(req.videos), "model": req.model},
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        logger.info(f"[{request_id}] analyze_video: {len(req.videos)} videos, {response_time_ms}ms")

        return {
            "success": True,
            "request_id": request_id,
            "analysis": result["analysis"],
            "tokens": tokens,
        }

    except Exception as e:
        status_code = 500
        error_msg = str(e)
        response_time_ms = int((time.time() - start) * 1000)

        log_api_call(
            api_key_id=key_info["id"],
            api_key_name=key_info["name"],
            api_name="analyze_video",
            endpoint="/v1/analyze_video",
            status_code=500,
            response_time_ms=response_time_ms,
            error=error_msg,
            client_ip=request.client.host if request.client else None,
        )

        logger.error(f"[{request_id}] analyze_video failed: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": error_msg})


# ============================================================
# 开放 API 2: POST /v1/competitor_monitor
# ============================================================
@app.post("/v1/competitor_monitor")
def api_competitor_monitor(req: CompetitorMonitorRequest, request: Request):
    """竞品账号监控

    输入竞品账号 URL, 自动:
    1. 采集最新视频
    2. (可选) AI 分析新视频

    支持平台: douyin / xiaohongshu / youtube / tiktok

    认证: X-API-Key header
    """
    request_id = str(uuid.uuid4())[:8]
    key_info = authenticate_and_limit(request, "competitor_monitor")

    start = time.time()
    error_msg = None

    try:
        result = call_competitor_monitor(
            platform=req.platform,
            url=req.url,
            max_videos=req.max_videos,
            auto_analyze=req.auto_analyze,
            analysis_model=req.analysis_model,
        )

        response_time_ms = int((time.time() - start) * 1000)
        tokens = result.get("tokens", {})

        log_api_call(
            api_key_id=key_info["id"],
            api_key_name=key_info["name"],
            api_name="competitor_monitor",
            endpoint="/v1/competitor_monitor",
            status_code=200,
            response_time_ms=response_time_ms,
            prompt_tokens=tokens.get("prompt_tokens", 0),
            completion_tokens=tokens.get("completion_tokens", 0),
            request_summary={
                "platform": req.platform,
                "url": req.url[:50],
                "max_videos": req.max_videos,
                "auto_analyze": req.auto_analyze,
            },
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        logger.info(
            f"[{request_id}] competitor_monitor: {req.platform}, "
            f"crawled={result.get('crawled')}, {response_time_ms}ms"
        )

        return {
            "success": True,
            "request_id": request_id,
            **result,
        }

    except Exception as e:
        error_msg = str(e)
        response_time_ms = int((time.time() - start) * 1000)

        log_api_call(
            api_key_id=key_info["id"],
            api_key_name=key_info["name"],
            api_name="competitor_monitor",
            endpoint="/v1/competitor_monitor",
            status_code=500,
            response_time_ms=response_time_ms,
            error=error_msg,
            client_ip=request.client.host if request.client else None,
        )

        logger.error(f"[{request_id}] competitor_monitor failed: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": error_msg})


# ============================================================
# 开放 API 3: POST /v1/generate_strategy
# ============================================================
@app.post("/v1/generate_strategy")
def api_generate_strategy(req: GenerateStrategyRequest, request: Request):
    """运营策略生成

    输入竞品视频数据, AI 生成:
    - titles: 5 条改写标题
    - scripts: 3 条新脚本 (含分镜+钩子+CTA)
    - topics: N 条相似选题

    认证: X-API-Key header
    """
    request_id = str(uuid.uuid4())[:8]
    key_info = authenticate_and_limit(request, "generate_strategy")

    start = time.time()
    error_msg = None

    try:
        result = call_generate_strategy(
            video=req.video.model_dump(),
            model=req.model,
            topic_count=req.topic_count,
        )

        response_time_ms = int((time.time() - start) * 1000)
        tokens = result.get("tokens", {})

        log_api_call(
            api_key_id=key_info["id"],
            api_key_name=key_info["name"],
            api_name="generate_strategy",
            endpoint="/v1/generate_strategy",
            status_code=200,
            response_time_ms=response_time_ms,
            prompt_tokens=tokens.get("prompt_tokens", 0),
            completion_tokens=tokens.get("completion_tokens", 0),
            request_summary={"title": req.video.title[:50], "model": req.model},
            client_ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )

        logger.info(f"[{request_id}] generate_strategy: {response_time_ms}ms")

        return {
            "success": True,
            "request_id": request_id,
            "titles": result.get("titles", []),
            "scripts": result.get("scripts", []),
            "topics": result.get("topics", []),
            "tokens": tokens,
        }

    except Exception as e:
        error_msg = str(e)
        response_time_ms = int((time.time() - start) * 1000)

        log_api_call(
            api_key_id=key_info["id"],
            api_key_name=key_info["name"],
            api_name="generate_strategy",
            endpoint="/v1/generate_strategy",
            status_code=500,
            response_time_ms=response_time_ms,
            error=error_msg,
            client_ip=request.client.host if request.client else None,
        )

        logger.error(f"[{request_id}] generate_strategy failed: {e}")
        raise HTTPException(status_code=500, detail={"error": "internal_error", "message": error_msg})


# ============================================================
# 管理接口: API 产品目录
# ============================================================
@app.get("/products")
def api_products():
    """API 产品目录 (无需认证)"""
    return list_api_products()


@app.get("/products/{name}")
def api_product_detail(name: str):
    """单个 API 产品详情"""
    product = get_api_product(name)
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product


# ============================================================
# 管理接口: API Key 管理
# ============================================================
@app.post("/keys")
def api_create_key(req: CreateKeyRequest):
    """创建 API Key"""
    key = create_api_key(
        name=req.name,
        description=req.description,
        plan=req.plan,
        rate_limit_per_min=req.rate_limit_per_min,
        rate_limit_per_day=req.rate_limit_per_day,
        allowed_apis=req.allowed_apis,
    )
    logger.info(f"创建 API Key: {req.name} ({key.get('key', '')[:12]}...)")
    return key


@app.get("/keys")
def api_list_keys(
    user_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    """列出 API Key"""
    from db import get_supabase
    sb = get_supabase()
    q = sb.table("api_keys").select("*")
    if user_id:
        q = q.eq("user_id", user_id)
    res = q.order("created_at", desc=True).limit(limit).execute()
    return res.data


@app.delete("/keys/{key_id}")
def api_delete_key(key_id: str):
    """删除 (禁用) API Key"""
    from db import get_supabase
    sb = get_supabase()
    sb.table("api_keys").update({"is_active": False}).eq("id", key_id).execute()
    return {"ok": True, "message": "Key 已禁用"}


@app.get("/keys/{key_id}/usage")
def api_key_usage(key_id: str):
    """Key 使用统计"""
    return get_usage_stats(key_id)


@app.get("/keys/{key_id}/logs")
def api_key_logs(key_id: str, limit: int = Query(50, ge=1, le=200)):
    """Key 调用日志"""
    return list_logs(api_key_id=key_id, limit=limit)


# ============================================================
# 健康检查
# ============================================================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "api-marketplace",
        "port": 8011,
        "apis": [
            {"method": "POST", "path": "/v1/analyze_video", "name": "视频爆款分析"},
            {"method": "POST", "path": "/v1/competitor_monitor", "name": "竞品账号监控"},
            {"method": "POST", "path": "/v1/generate_strategy", "name": "运营策略生成"},
        ],
        "auth": "X-API-Key header",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("启动 API Marketplace...")
    uvicorn.run(app, host="0.0.0.0", port=8011)
