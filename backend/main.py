"""main.py - FastAPI 应用入口

职责:
1. 接收前端分析请求 -> 调用 Node 爬虫 -> 调用 AI -> 存 Supabase -> 返回报告
2. 提供报告列表与详情查询接口
"""
import os
import json
import subprocess
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from models import AnalyzeRequest, IntelligenceReport
from db import upsert_competitor, insert_report, list_reports, get_report
from ai_service import analyze

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

app = FastAPI(title="AI 竞争情报系统 - 竞争对手分析模块")

# 允许 Next.js 前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError:
        return {"url": url, "title": "", "content": "", "error": "爬虫输出解析失败"}
    except Exception as e:
        return {"url": url, "title": "", "content": "", "error": str(e)}


@app.get("/api/health")
def health():
    return {"status": "ok", "crawler": os.path.exists(CRAWLER_SCRIPT)}


@app.post("/api/analyze", response_model=IntelligenceReport)
def analyze_competitor(req: AnalyzeRequest):
    url = str(req.url)
    # 名称缺省时用域名
    name = req.name or urlparse(url).netloc

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
