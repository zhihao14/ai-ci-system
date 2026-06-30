"""main.py - FastAPI 应用入口

职责:
1. 接收前端分析请求 -> 调用 Node 爬虫 -> 调用 AI -> 存 Supabase -> 返回报告
2. 提供报告列表与详情查询接口
3. 提供 AI 配置 CRUD 接口 (前台管理)
"""
import os
import json
import subprocess
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models import (
    AnalyzeRequest, IntelligenceReport,
    AIConfigCreate, AIConfigUpdate, AIConfigResponse,
    GrowthAnalysisRequest,
)
from db import (
    upsert_competitor, insert_report, list_reports, get_report,
    list_ai_configs, get_active_ai_configs, insert_ai_config,
    update_ai_config, delete_ai_config,
)
from ai_service import analyze, growth_analyze

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(title="AI 竞争情报系统 - 竞争对手分析模块")

# 允许 Next.js 前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://ai-ci-system.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 爬虫脚本路径 (相对本文件)
CRAWLER_SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.getenv("CRAWLER_SCRIPT", "../crawler/crawl.js"))
)


def run_crawler(url: str) -> dict:
    """以子进程方式调用 Node 爬虫, 解析其 stdout JSON"""
    try:
        proc = subprocess.run(
            ["node", CRAWLER_SCRIPT, url],
            capture_output=True, text=True, timeout=180,
        )
        stdout = proc.stdout.strip()
        if not stdout:
            # node 进程崩溃, stderr 里通常有模块缺失等错误
            err = proc.stderr.strip() or f"exit code {proc.returncode}, stdout 为空"
            return {"url": url, "title": "", "content": "", "error": f"爬虫无输出: {err[:500]}"}
        return json.loads(stdout)
    except json.JSONDecodeError:
        # stdout 不是合法 JSON, 把原始输出截断后返回便于排查
        raw = (proc.stdout or "")[:500]
        return {"url": url, "title": "", "content": "", "error": f"爬虫输出解析失败: {raw}"}
    except Exception as e:
        return {"url": url, "title": "", "content": "", "error": str(e)}


def _mask_key(key: str) -> str:
    """API Key 脱敏: 只显示前4位和后4位"""
    if not key or len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]}"


# ============================================================
# 健康检查
# ============================================================

@app.get("/api/health")
def health():
    return {"status": "ok", "crawler": os.path.exists(CRAWLER_SCRIPT)}


# ============================================================
# 竞争对手分析
# ============================================================

@app.post("/api/analyze", response_model=IntelligenceReport)
def analyze_competitor(req: AnalyzeRequest):
    url = req.url.strip()
    # 名称缺省时用域名
    name = req.name or urlparse(url).netloc or url

    # 1) 爬取页面
    crawled = run_crawler(url)
    if crawled.get("error"):
        raise HTTPException(status_code=502, detail=f"爬取失败: {crawled['error']}")

    title = crawled.get("title") or name
    content = crawled.get("content") or ""
    if not content.strip():
        raise HTTPException(status_code=422, detail="页面正文为空, 无法分析")

    # 2) AI 情报分析
    ai = analyze(title, content)
    if not ai or ai.get("ai_provider") == "none":
        raise HTTPException(status_code=503, detail=ai.get("summary", "AI 分析失败, 请检查 AI 配置"))

    # 3) 落库: 先 upsert 竞争对手, 再插入报告
    competitor_id = upsert_competitor(name, url)
    report = {
        "competitor_id": competitor_id,
        "url": url,
        "title": title,
        "raw_content": content,
        "summary": ai.get("summary"),
        "products": ai.get("products", []),
        "pricing": ai.get("pricing", []),
        "positioning": ai.get("positioning", {}),
        "strengths": ai.get("strengths", []),
        "weaknesses": ai.get("weaknesses", []),
        "recent_changes": ai.get("recent_changes"),
        "ai_provider": ai.get("ai_provider"),
    }
    saved = insert_report(report)

    # 4) 返回
    return IntelligenceReport(
        id=saved["id"],
        competitor_id=saved.get("competitor_id"),
        url=saved["url"],
        title=saved.get("title"),
        summary=saved.get("summary"),
        products=saved.get("products") or [],
        pricing=saved.get("pricing") or [],
        positioning=saved.get("positioning") or {},
        strengths=saved.get("strengths") or [],
        weaknesses=saved.get("weaknesses") or [],
        recent_changes=saved.get("recent_changes"),
        ai_provider=saved.get("ai_provider"),
        created_at=saved.get("created_at"),
    )


@app.get("/api/reports")
def reports():
    """最近报告列表"""
    return list_reports(limit=50)


@app.get("/api/reports/{report_id}", response_model=IntelligenceReport)
def report_detail(report_id: str):
    """单条报告详情"""
    row = get_report(report_id)
    if not row:
        raise HTTPException(status_code=404, detail="报告不存在")
    return IntelligenceReport(
        id=row["id"],
        competitor_id=row.get("competitor_id"),
        url=row["url"],
        title=row.get("title"),
        summary=row.get("summary"),
        products=row.get("products") or [],
        pricing=row.get("pricing") or [],
        positioning=row.get("positioning") or {},
        strengths=row.get("strengths") or [],
        weaknesses=row.get("weaknesses") or [],
        recent_changes=row.get("recent_changes"),
        ai_provider=row.get("ai_provider"),
        created_at=row.get("created_at"),
    )


# ============================================================
# 短视频数据分析 (拆分为两步: 爬取 + 分析, 避免Railway 60s超时)
# ============================================================

@app.post("/api/crawl")
def crawl_data(req: GrowthAnalysisRequest):
    """第1步: 爬取账号信息和视频列表 (Playwright, ~30s)"""
    url = req.url.strip()

    crawled = run_crawler(url)
    if crawled.get("error"):
        raise HTTPException(status_code=502, detail=f"爬取失败: {crawled['error']}")

    title = crawled.get("title") or url
    content = crawled.get("content") or ""
    if not content.strip():
        raise HTTPException(status_code=422, detail="页面正文为空, 无法分析")

    account_fields = crawled.get("account_fields")
    videos = crawled.get("videos") or req.videos

    return {
        "url": url,
        "title": title,
        "account_info": content,
        "account_fields": account_fields,
        "videos": videos,
        "video_count": len(videos) if videos else 0,
    }


@app.post("/api/analyze-growth")
def analyze_growth(req: dict):
    """第2步: AI evidence-based 聚合分析 (~15s)"""
    account_info = req.get("account_info", "")
    videos = req.get("videos")
    account_fields = req.get("account_fields")

    if not account_info.strip() and not videos:
        raise HTTPException(status_code=422, detail="账号信息和视频数据均为空")

    result = growth_analyze(account_info, videos, account_fields)
    if result.get("ai_provider") == "none":
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "AI 分析失败, 请检查 AI 配置"),
        )

    return {
        "analysis": result,
        "ai_provider": result.get("ai_provider"),
    }


@app.post("/api/growth-analysis")
def growth_analysis(req: GrowthAnalysisRequest):
    """一体化接口 (本地调试用, Railway 60s 超时请用 /api/crawl + /api/analyze-growth)"""
    url = req.url.strip()

    # 1) 爬取
    crawled = run_crawler(url)
    if crawled.get("error"):
        raise HTTPException(status_code=502, detail=f"爬取失败: {crawled['error']}")

    title = crawled.get("title") or url
    content = crawled.get("content") or ""
    if not content.strip():
        raise HTTPException(status_code=422, detail="页面正文为空, 无法分析")

    account_fields = crawled.get("account_fields")
    videos = crawled.get("videos") or req.videos

    # 2) AI 分析
    result = growth_analyze(content, videos, account_fields)
    if result.get("ai_provider") == "none":
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "AI 分析失败, 请检查 AI 配置"),
        )

    return {
        "url": url,
        "title": title,
        "account_info": content,
        "account_fields": account_fields,
        "videos": videos,
        "video_count": len(videos) if videos else 0,
        "analysis": result,
        "ai_provider": result.get("ai_provider"),
    }


# ============================================================
# AI 配置 CRUD (前台管理)
# ============================================================

@app.get("/api/config", response_model=list[AIConfigResponse])
def get_configs():
    """列出所有 AI 配置 (api_key 脱敏)"""
    configs = list_ai_configs()
    return [
        AIConfigResponse(
            id=c["id"],
            provider=c["provider"],
            label=c["label"],
            api_key=_mask_key(c["api_key"]),
            base_url=c.get("base_url"),
            model=c["model"],
            is_active=c["is_active"],
            priority=c["priority"],
            created_at=c.get("created_at"),
            updated_at=c.get("updated_at"),
        )
        for c in configs
    ]


@app.post("/api/config", response_model=AIConfigResponse)
def create_config(cfg: AIConfigCreate):
    """新增 AI 配置"""
    data = cfg.model_dump()
    saved = insert_ai_config(data)
    return AIConfigResponse(
        id=saved["id"],
        provider=saved["provider"],
        label=saved["label"],
        api_key=_mask_key(saved["api_key"]),
        base_url=saved.get("base_url"),
        model=saved["model"],
        is_active=saved["is_active"],
        priority=saved["priority"],
        created_at=saved.get("created_at"),
        updated_at=saved.get("updated_at"),
    )


@app.put("/api/config/{config_id}", response_model=AIConfigResponse)
def update_config(config_id: str, cfg: AIConfigUpdate):
    """更新 AI 配置 (只更新非 None 字段)"""
    updates = cfg.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")
    saved = update_ai_config(config_id, updates)
    if not saved:
        raise HTTPException(status_code=404, detail="配置不存在")
    return AIConfigResponse(
        id=saved["id"],
        provider=saved["provider"],
        label=saved["label"],
        api_key=_mask_key(saved["api_key"]),
        base_url=saved.get("base_url"),
        model=saved["model"],
        is_active=saved["is_active"],
        priority=saved["priority"],
        created_at=saved.get("created_at"),
        updated_at=saved.get("updated_at"),
    )


@app.delete("/api/config/{config_id}")
def remove_config(config_id: str):
    """删除 AI 配置"""
    ok = delete_ai_config(config_id)
    if not ok:
        raise HTTPException(status_code=404, detail="配置不存在")
    return {"status": "deleted"}


# ============================================================
# AI Competitive Intelligence Platform — 核心智能分析
# ============================================================

@app.post("/api/intelligence/crawl")
def intelligence_crawl(req: GrowthAnalysisRequest):
    """第1步: 爬取50条视频, 存入 video_analyses 表 (~20s)"""
    from intelligence_service import crawl_and_save
    try:
        result = crawl_and_save(req.url.strip())
        return result
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/intelligence/analyze")
def intelligence_analyze(req: dict):
    """第2步: Multi-Agent 分析 (Pattern + Analysis + Trend) (~40s)"""
    from intelligence_service import run_analysis
    analysis_id = req.get("video_analysis_id")
    use_rag = req.get("use_rag", True)
    if not analysis_id:
        raise HTTPException(status_code=422, detail="video_analysis_id 必填")
    try:
        result = run_analysis(analysis_id, use_rag)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/intelligence/strategy")
def intelligence_strategy(req: dict):
    """第3步: Growth Strategy Recommendation Engine (~20s)"""
    from intelligence_service import generate_strategy
    analysis_id = req.get("video_analysis_id")
    use_rag = req.get("use_rag", True)
    if not analysis_id:
        raise HTTPException(status_code=422, detail="video_analysis_id 必填")
    try:
        result = generate_strategy(analysis_id, use_rag)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/intelligence/compare")
def intelligence_compare(req: dict):
    """Multi Competitor Comparison Engine (~20s)"""
    from intelligence_service import compare_competitors
    analysis_ids = req.get("analysis_ids", [])
    if len(analysis_ids) < 2:
        raise HTTPException(status_code=422, detail="至少需要 2 个 analysis_id")
    try:
        result = compare_competitors(analysis_ids)
        return result
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/intelligence/knowledge/search")
def knowledge_search(req: dict):
    """RAG 知识库搜索 (~2s)"""
    from rag.knowledge_base import get_kb
    query = req.get("query", "")
    limit = req.get("limit", 5)
    if not query:
        raise HTTPException(status_code=422, detail="query 必填")
    results = get_kb().search(query, limit=limit)
    return {"results": results, "count": len(results)}


@app.get("/api/intelligence/analyses")
def intelligence_list(limit: int = 20):
    """列出所有智能分析记录"""
    from db_intelligence import list_video_analyses
    return list_video_analyses(limit=limit)


@app.get("/api/intelligence/analyses/{analysis_id}")
def intelligence_detail(analysis_id: str):
    """获取完整分析详情 (含 videos + patterns + trends + strategy)"""
    from db_intelligence import get_video_analysis, get_content_pattern, get_trend_prediction, get_growth_strategy
    va = get_video_analysis(analysis_id)
    if not va:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    patterns = get_content_pattern(analysis_id)
    trends = get_trend_prediction(analysis_id)
    strategy = get_growth_strategy(analysis_id)
    return {
        **va,
        "patterns": patterns.get("patterns") if patterns else None,
        "trends": trends.get("predictions") if trends else None,
        "strategy": strategy.get("strategy") if strategy else None,
    }


@app.get("/api/intelligence/dashboard")
def intelligence_dashboard():
    """Real-time Analytics Dashboard 统计数据"""
    from intelligence_service import get_intelligence_dashboard
    return get_intelligence_dashboard()
