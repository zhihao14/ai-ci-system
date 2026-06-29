"""main_content.py — AI 内容生成模块 API

接口:
  POST /generate          提交竞品视频, 生成改写标题+新脚本+相似选题
  POST /generate/titles   仅生成改写标题
  POST /generate/scripts  仅生成新脚本
  POST /generate/topics   仅生成相似选题
  GET  /history           已保存的生成记录
  GET  /history/{id}       生成记录详情
  GET  /models            可用模型列表

运行:
  cd backend
  uvicorn main_content:app --reload --port 8006
"""
import os
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(
    title="AI 竞争情报系统 - 内容生成模块",
    description="输入竞品视频, 生成改写标题/新脚本/相似选题 (DeepSeek/Claude/GLM)",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from models_content import GenerateRequest, GenerateResult, VideoRef
from content_service import generate_content, save_to_db
from ai_router.router import get_router


# ============================================================
# 接口 1: POST /generate — 完整生成 (核心)
# ============================================================
@app.post("/generate", response_model=GenerateResult)
def generate(req: GenerateRequest):
    """提交竞品视频数据, 一次生成 3 个维度:
    - 5 条改写标题 (不同角度)
    - 3 条新脚本 (含分镜+钩子+CTA)
    - N 条相似选题 (差异化)

    model 参数支持: auto / deepseek / claude / glm / 具体模型名
    """
    try:
        result = generate_content(
            video=req.video,
            model=req.model,
            count=req.count,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")

    # 可选落库
    if req.save_to_db:
        save_to_db(result, account_id=req.account_id)

    return result


# ============================================================
# 单维度生成请求模型
# ============================================================
class TitleOnlyRequest(BaseModel):
    video: VideoRef
    model: str = "auto"


class ScriptOnlyRequest(BaseModel):
    video: VideoRef
    model: str = "auto"


class TopicOnlyRequest(BaseModel):
    video: VideoRef
    model: str = "auto"
    count: int = Field(default=20, ge=5, le=30)


# ============================================================
# 接口 2: POST /generate/titles — 仅改写标题
# ============================================================
@app.post("/generate/titles")
def generate_titles(req: TitleOnlyRequest):
    """仅生成 5 条改写标题"""
    try:
        result = generate_content(video=req.video, model=req.model, count=5)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "source_title": result.source_title,
        "titles": result.rewritten_titles,
        "model_used": result.model_used,
        "provider": result.provider,
        "latency_ms": result.latency_ms,
    }


# ============================================================
# 接口 3: POST /generate/scripts — 仅新脚本
# ============================================================
@app.post("/generate/scripts")
def generate_scripts(req: ScriptOnlyRequest):
    """仅生成 3 条新脚本"""
    try:
        result = generate_content(video=req.video, model=req.model, count=5)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "source_title": result.source_title,
        "scripts": result.new_scripts,
        "model_used": result.model_used,
        "provider": result.provider,
        "latency_ms": result.latency_ms,
    }


# ============================================================
# 接口 4: POST /generate/topics — 仅相似选题
# ============================================================
@app.post("/generate/topics")
def generate_topics(req: TopicOnlyRequest):
    """仅生成 N 条相似选题"""
    try:
        result = generate_content(video=req.video, model=req.model, count=req.count)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    return {
        "source_title": result.source_title,
        "topics": result.similar_topics,
        "model_used": result.model_used,
        "provider": result.provider,
        "latency_ms": result.latency_ms,
    }


# ============================================================
# 接口 5: GET /history — 已保存的生成记录
# ============================================================
@app.get("/history")
def list_history(
    limit: int = Query(20, ge=1, le=100),
):
    """列出已保存的内容生成记录"""
    from db import get_supabase
    sb = get_supabase()
    res = (
        sb.table("ai_analysis")
        .select("id, summary, ai_provider, ai_model, prompt_tokens, completion_tokens, created_at")
        .eq("analysis_type", "content_generation")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


# ============================================================
# 接口 6: GET /history/{id} — 记录详情
# ============================================================
@app.get("/history/{record_id}")
def get_history(record_id: str):
    """查看某条生成记录的完整结果"""
    from db import get_supabase
    sb = get_supabase()
    res = sb.table("ai_analysis").select("*").eq("id", record_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="记录不存在")
    return res.data[0]


# ============================================================
# 接口 7: GET /models — 可用模型
# ============================================================
@app.get("/models")
def models():
    """返回可用 AI 模型列表 (供前端切换)"""
    router = get_router()
    return {"models": router.list_models()}


# ============================================================
# 健康检查
# ============================================================
@app.get("/health")
def health():
    router = get_router()
    return {
        "status": "ok",
        "models_available": len(router.list_models()),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
