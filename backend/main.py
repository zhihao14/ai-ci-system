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
            capture_output=True, text=True, timeout=90,
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
# 短视频增长策略分析 (4层框架)
# ============================================================

@app.post("/api/growth-analysis")
def growth_analysis(req: GrowthAnalysisRequest):
    """短视频增长策略分析: 爬取账号信息 -> AI 4层分析 -> 返回结构化JSON"""
    url = req.url.strip()
    videos = req.videos

    # 1) 爬取账号信息
    crawled = run_crawler(url)
    if crawled.get("error"):
        raise HTTPException(status_code=502, detail=f"爬取失败: {crawled['error']}")

    title = crawled.get("title") or url
    content = crawled.get("content") or ""
    if not content.strip():
        raise HTTPException(status_code=422, detail="页面正文为空, 无法分析")

    # 2) AI 增长策略分析
    result = growth_analyze(content, videos)
    if result.get("ai_provider") == "none":
        raise HTTPException(
            status_code=503,
            detail=result.get("error", "AI 分析失败, 请检查 AI 配置"),
        )

    # 3) 返回4层结构化结果
    return {
        "url": url,
        "title": title,
        "account_info": content,
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
