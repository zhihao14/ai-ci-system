"""main_router.py — AI Router 管理 + 调用 API

接口:
  # ---- 模型调用 ----
  POST /chat              统一对话接口 (核心)
  POST /complete          补全接口 (简写)
  GET  /models            可用模型列表

  # ---- Provider 管理 ----
  GET    /providers       列出所有 provider
  POST   /providers       添加/更新 provider
  DELETE /providers/{name} 删除 provider
  PUT    /providers/{name}/toggle  启用/禁用

  # ---- 测试 ----
  POST /providers/{name}/test  测试某 provider 连通性

运行:
  cd backend
  uvicorn main_router:app --reload --port 8004
"""
import os
import time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from ai_router.config import (
    ProviderConfig,
    get_all_providers,
    get_provider,
    add_provider,
    remove_provider,
    list_provider_summaries,
)
from ai_router.base import AIMessage, AIResponse, ProviderError
from ai_router.router import get_router

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(
    title="AI Router — 统一模型调用层",
    description="统一调用 OpenAI/DeepSeek/GLM/Claude/自定义 API, 支持自动切换 + 重试",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 请求/响应模型
# ============================================================
class MessageIn(BaseModel):
    role: str = Field(description="system | user | assistant")
    content: str


class ChatRequest(BaseModel):
    """统一对话请求"""
    messages: list[MessageIn]
    model: str = Field(default="auto", description="auto | provider名 | 具体模型名")
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    json_mode: bool = False
    max_retries: int = Field(default=3, ge=0, le=10, description="最大重试次数")
    retry_delay: float = Field(default=1.0, description="重试初始延迟秒")


class ChatResponse(BaseModel):
    """统一对话响应"""
    ok: bool = True
    content: str
    json_content: Optional[dict] = None
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0


class ProviderIn(BaseModel):
    """添加/更新 Provider 请求"""
    name: str = Field(description="唯一标识, 如 'my-gpt'")
    provider_type: str = Field(
        default="openai",
        description="openai | anthropic | custom",
    )
    base_url: str = Field(description="API Base URL, 如 https://api.openai.com/v1")
    api_key: str = Field(description="API Key")
    model: str = Field(description="默认模型名, 如 gpt-4o")
    priority: int = Field(default=100, description="路由优先级 (越小越优先)")
    enabled: bool = True
    max_tokens: int = 4096
    temperature: float = 0.4
    timeout: int = 90
    extra_headers: dict = Field(default_factory=dict)


class ToggleRequest(BaseModel):
    enabled: bool


# ============================================================
# 接口 1: POST /chat — 统一对话 (核心)
# ============================================================
@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """统一对话接口

    - model="auto" 自动按优先级选择, 失败自动切换
    - model="deepseek" 强制用某 provider
    - 带指数退避重试
    """
    router = get_router()

    messages = [AIMessage(role=m.role, content=m.content) for m in req.messages]

    try:
        resp = router.call_with_retry(
            messages=messages,
            model=req.model,
            max_retries=req.max_retries,
            retry_delay=req.retry_delay,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            json_mode=req.json_mode,
        )
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"调用失败: {e}")

    return ChatResponse(
        content=resp.content,
        json_content=resp.json_content,
        provider=resp.provider,
        model=resp.model,
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
        latency_ms=resp.latency_ms,
    )


# ============================================================
# 接口 2: POST /complete — 补全简写
# ============================================================
class CompleteRequest(BaseModel):
    prompt: str
    system: Optional[str] = None
    model: str = "auto"
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    json_mode: bool = False


@app.post("/complete", response_model=ChatResponse)
def complete(req: CompleteRequest):
    """简写接口: 单条 prompt → 单条响应"""
    messages = []
    if req.system:
        messages.append(AIMessage(role="system", content=req.system))
    messages.append(AIMessage(role="user", content=req.prompt))

    router = get_router()
    try:
        resp = router.call_with_retry(
            messages=messages,
            model=req.model,
            temperature=req.temperature,
            max_tokens=req.max_tokens,
            json_mode=req.json_mode,
        )
    except ProviderError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return ChatResponse(
        content=resp.content,
        json_content=resp.json_content,
        provider=resp.provider,
        model=resp.model,
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
        latency_ms=resp.latency_ms,
    )


# ============================================================
# 接口 3: GET /models — 可用模型
# ============================================================
@app.get("/models")
def models():
    """返回可用模型列表 (供前端下拉选择)"""
    router = get_router()
    return {"models": router.list_models()}


# ============================================================
# 接口 4: GET /providers — 列出所有 provider
# ============================================================
@app.get("/providers")
def providers():
    """列出所有已配置的 provider (隐藏 api_key)"""
    return {"providers": list_provider_summaries()}


# ============================================================
# 接口 5: POST /providers — 添加/更新 provider
# ============================================================
@app.post("/providers")
def add_provider_api(req: ProviderIn):
    """添加或更新一个 provider (持久化到 providers.json)"""
    config = ProviderConfig(
        name=req.name,
        provider_type=req.provider_type,
        base_url=req.base_url,
        api_key=req.api_key,
        model=req.model,
        priority=req.priority,
        enabled=req.enabled,
        max_tokens=req.max_tokens,
        temperature=req.temperature,
        timeout=req.timeout,
        extra_headers=req.extra_headers,
    )
    add_provider(config)
    # 清除 router 缓存, 使新配置生效
    from ai_router.router import get_router
    get_router()._provider_cache.pop(req.name, None)
    return {"ok": True, "message": f"provider '{req.name}' 已添加/更新"}


# ============================================================
# 接口 6: DELETE /providers/{name} — 删除 provider
# ============================================================
@app.delete("/providers/{name}")
def delete_provider(name: str):
    """删除一个动态添加的 provider"""
    if remove_provider(name):
        from ai_router.router import get_router
        get_router()._provider_cache.pop(name, None)
        return {"ok": True, "message": f"provider '{name}' 已删除"}
    raise HTTPException(status_code=404, detail=f"provider '{name}' 不存在或来自环境变量不可删")


# ============================================================
# 接口 7: PUT /providers/{name}/toggle — 启用/禁用
# ============================================================
@app.put("/providers/{name}/toggle")
def toggle_provider(name: str, req: ToggleRequest):
    """启用或禁用某 provider"""
    cfg = get_provider(name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"provider '{name}' 不存在")

    cfg.enabled = req.enabled
    add_provider(cfg)  # 覆盖更新
    return {"ok": True, "message": f"provider '{name}' 已{'启用' if req.enabled else '禁用'}"}


# ============================================================
# 接口 8: POST /providers/{name}/test — 测试连通性
# ============================================================
@app.post("/providers/{name}/test")
def test_provider(name: str):
    """测试某 provider 是否可用 (发一条简单请求)"""
    cfg = get_provider(name)
    if not cfg:
        raise HTTPException(status_code=404, detail=f"provider '{name}' 不存在")

    from ai_router.providers import create_provider
    provider = create_provider(cfg)

    start = time.time()
    try:
        resp = provider.call(
            messages=[AIMessage(role="user", content="说 'ok'")],
            max_tokens=10,
            temperature=0,
        )
        latency = int((time.time() - start) * 1000)
        return {
            "ok": True,
            "provider": name,
            "model": resp.model,
            "response": resp.content[:100],
            "latency_ms": latency,
        }
    except ProviderError as e:
        latency = int((time.time() - start) * 1000)
        return {
            "ok": False,
            "provider": name,
            "error": str(e),
            "latency_ms": latency,
        }


# ============================================================
# 健康检查
# ============================================================
@app.get("/health")
def health():
    router = get_router()
    return {
        "status": "ok",
        "providers": {
            p["name"]: {"enabled": p["enabled"], "ready": True}
            for p in list_provider_summaries()
        },
        "models_count": len(router.list_models()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)
