"""main_viral.py - 爆款分析模块 FastAPI 路由

接口:
  POST /analyze_viral       提交视频数组, 返回爆款分析
  GET  /analyses            列出已保存的分析记录
  GET  /analyses/{id}       查看某条分析详情
  GET  /models              列出可用的 AI 模型

运行:
  cd backend
  uvicorn main_viral:app --reload --port 8002
"""
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models_viral import ViralAnalysisRequest, ViralAnalysisResult
from viral_service import analyze_viral, save_analysis_to_db
from ai_client import call_ai

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(
    title="AI 竞争情报系统 - 爆款分析模块",
    description="输入视频数据, AI 提炼爆款规律并给出可复制选题",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 接口 1: POST /analyze_viral - 核心爆款分析
# ============================================================
@app.post("/analyze_viral", response_model=ViralAnalysisResult)
def analyze_viral_api(req: ViralAnalysisRequest):
    """提交视频数据数组, 返回结构化爆款分析

    - 支持 1-50 条视频
    - model 参数: auto / deepseek / claude / 具体模型名
    - save_to_db=true 时写入 ai_analysis 表
    """
    try:
        result = analyze_viral(videos=req.videos, model=req.model)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")

    # 可选: 写入数据库
    if req.save_to_db:
        analysis_id = save_analysis_to_db(
            result,
            account_id=req.account_id,
        )
        # 把记录 id 附到响应里 (通过 model_extra 不行, 改用私有字段传递)
        # 这里直接 print 日志, 前端如需 id 可调 /analyses 查最新
        if analysis_id:
            print(f"[analyze_viral] 已写入 ai_analysis, id={analysis_id}")

    return result


# ============================================================
# 接口 2: GET /analyses - 列出已保存的分析
# ============================================================
@app.get("/analyses")
def list_analyses(
    limit: int = Query(20, ge=1, le=100),
    analysis_type: str = Query("viral_analysis"),
):
    """列出已保存的 AI 分析记录 (默认只看爆款分析)"""
    from db import get_supabase
    sb = get_supabase()
    res = (
        sb.table("ai_analysis")
        .select("id, account_id, video_id, analysis_type, summary, ai_provider, ai_model, created_at")
        .eq("analysis_type", analysis_type)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


# ============================================================
# 接口 3: GET /analyses/{id} - 分析详情
# ============================================================
@app.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: str):
    """查看某条 AI 分析的完整结果 (含 result jsonb)"""
    from db import get_supabase
    sb = get_supabase()
    res = sb.table("ai_analysis").select("*").eq("id", analysis_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return res.data[0]


# ============================================================
# 接口 4: GET /models - 可用模型列表
# ============================================================
@app.get("/models")
def list_models():
    """返回当前配置下可用的 AI 模型, 供前端切换"""
    import os
    models = []

    if os.getenv("DEEPSEEK_API_KEY"):
        models.append({
            "id": "deepseek",
            "label": f"DeepSeek ({os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')})",
            "provider": "deepseek",
        })

    if os.getenv("ANTHROPIC_API_KEY"):
        models.append({
            "id": "claude",
            "label": f"Claude ({os.getenv('CLAUDE_MODEL', 'claude-3-5-sonnet-20241022')})",
            "provider": "claude",
        })

    if len(models) >= 2:
        models.insert(0, {
            "id": "auto",
            "label": "自动 (DeepSeek 优先, 失败切 Claude)",
            "provider": "auto",
        })

    return {"models": models}


# ============================================================
# 健康检查
# ============================================================
@app.get("/health")
def health():
    return {
        "status": "ok",
        "deepseek_configured": bool(os.getenv("DEEPSEEK_API_KEY")),
        "claude_configured": bool(os.getenv("ANTHROPIC_API_KEY")),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
