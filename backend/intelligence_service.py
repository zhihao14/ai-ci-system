"""intelligence_service.py — AI Competitive Intelligence Platform 核心服务

协调 Multi-Agent 流水线:
1. crawl_and_save()        — 爬取50条视频, 存入 video_analyses
2. run_analysis()          — PatternAgent + Evidence-based Analysis + Trend Prediction
3. generate_strategy()     — Growth Strategy Recommendation
4. compare_competitors()   — Multi Competitor Comparison Engine
5. get_dashboard_stats()   — Real-time Analytics Dashboard 数据

所有 AI 分析使用 RAG 知识库增强上下文。
所有结果存入数据库 + RAG 知识库供后续检索。
"""
import os
import json
import subprocess
import httpx
from typing import Optional

from db import upsert_competitor
from db_intelligence import (
    insert_video_analysis, update_video_analysis, get_video_analysis,
    list_video_analyses, insert_content_pattern, get_content_pattern,
    insert_trend_prediction, get_trend_prediction,
    insert_growth_strategy, get_growth_strategy,
    insert_comparison, dashboard_stats,
)
from rag.knowledge_base import get_kb

# 爬虫脚本路径
CRAWLER_SCRIPT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.getenv("CRAWLER_SCRIPT", "../crawler/crawl.js"))
)


# ============================================================
# 1. 爬取 + 存储
# ============================================================

def crawl_and_save(url: str, max_videos: int = 50) -> dict:
    """第1步: 调用爬虫爬取视频数据, 存入 video_analyses 表

    Returns: { video_analysis_id, url, account_name, account_info, account_fields, videos, video_count }
    """
    # 调用 Node 爬虫
    try:
        proc = subprocess.run(
            ["node", CRAWLER_SCRIPT, url],
            capture_output=True, text=True, timeout=180,
        )
        stdout = proc.stdout.strip()
        if not stdout:
            err = proc.stderr.strip() or f"exit code {proc.returncode}"
            raise RuntimeError(f"爬虫无输出: {err[:300]}")
        crawled = json.loads(stdout)
    except json.JSONDecodeError:
        raw = (proc.stdout or "")[:300]
        raise RuntimeError(f"爬虫输出解析失败: {raw}")
    except Exception as e:
        raise RuntimeError(f"爬虫执行失败: {str(e)}")

    if crawled.get("error"):
        raise RuntimeError(f"爬取失败: {crawled['error']}")

    # 提取数据
    account_info = crawled.get("content") or ""
    account_fields = crawled.get("account_fields") or {}
    videos = crawled.get("videos") or []
    account_name = account_fields.get("nickname") or crawled.get("title") or url

    # upsert 竞争对手
    competitor_id = upsert_competitor(account_name, url)

    # 存入 video_analyses
    va = insert_video_analysis({
        "competitor_id": competitor_id,
        "url": url,
        "account_name": account_name,
        "account_info": account_info,
        "account_fields": account_fields,
        "videos": videos,
        "video_count": len(videos),
        "ai_provider": "pending",
    })

    return {
        "video_analysis_id": va["id"],
        "competitor_id": competitor_id,
        "url": url,
        "account_name": account_name,
        "account_info": account_info,
        "account_fields": account_fields,
        "videos": videos,
        "video_count": len(videos),
    }


# ============================================================
# 2. AI 多 Agent 分析 (Pattern + Analysis + Trend)
# ============================================================

def run_analysis(video_analysis_id: str, use_rag: bool = True) -> dict:
    """第2步: 运行 PatternAgent + Evidence-based Analysis + Trend Prediction

    Returns: { video_analysis_id, patterns, analysis, trends, ai_provider, rag_context_used }
    """
    va = get_video_analysis(video_analysis_id)
    if not va:
        raise ValueError(f"视频分析记录不存在: {video_analysis_id}")

    videos = va.get("videos") or []
    account_info = va.get("account_info") or ""
    account_fields = va.get("account_fields") or {}
    account_name = va.get("account_name") or ""
    competitor_id = va.get("competitor_id")

    # 获取 RAG 上下文
    rag_context = ""
    rag_used = False
    if use_rag:
        try:
            rag_context = get_kb().build_context(f"{account_name} 竞争情报 内容模式 趋势", limit=3)
            if rag_context:
                rag_used = True
        except Exception as e:
            print(f"[intelligence] RAG 检索失败: {e}")

    # ---- 2a. PatternAgent: 内容模式识别 ----
    patterns = None
    try:
        from agents.pattern_agent import _call_ai_for_patterns
        patterns = _call_ai_for_patterns(videos, account_fields, rag_context)
        # 存入 content_patterns
        insert_content_pattern({
            "video_analysis_id": video_analysis_id,
            "competitor_id": competitor_id,
            "patterns": patterns,
            "confidence_score": patterns.get("engagement_patterns", {}).get("confidence_score"),
            "ai_provider": patterns.get("ai_provider"),
        })
    except Exception as e:
        print(f"[intelligence] PatternAgent 失败: {e}")
        patterns = {"error": str(e), "ai_provider": "none"}

    # ---- 2b. Evidence-based Analysis (复用 ai_service.growth_analyze) ----
    analysis = None
    try:
        from ai_service import growth_analyze
        analysis = growth_analyze(account_info, videos, account_fields)
        # 更新 video_analyses 的 analysis 字段
        update_video_analysis(video_analysis_id, {
            "analysis": analysis,
            "ai_provider": analysis.get("ai_provider", "none"),
        })
    except Exception as e:
        print(f"[intelligence] Evidence-based Analysis 失败: {e}")
        analysis = {"error": str(e), "ai_provider": "none"}

    # ---- 2c. Trend Prediction ----
    trends = None
    try:
        trends = _predict_trends(videos, account_fields, rag_context)
        insert_trend_prediction({
            "video_analysis_id": video_analysis_id,
            "competitor_id": competitor_id,
            "predictions": trends,
            "confidence_score": trends.get("confidence_score"),
            "ai_provider": trends.get("ai_provider"),
        })
    except Exception as e:
        print(f"[intelligence] Trend Prediction 失败: {e}")
        trends = {"error": str(e), "ai_provider": "none"}

    # ---- 存入 RAG 知识库 ----
    try:
        get_kb().store_analysis(
            competitor_id=competitor_id,
            account_name=account_name,
            analysis=analysis if analysis.get("ai_provider") != "none" else None,
            patterns=patterns if patterns.get("ai_provider") != "none" else None,
            trends=trends if trends.get("ai_provider") != "none" else None,
        )
    except Exception as e:
        print(f"[intelligence] RAG 存储失败: {e}")

    return {
        "video_analysis_id": video_analysis_id,
        "patterns": patterns,
        "analysis": analysis,
        "trends": trends,
        "ai_provider": (patterns or {}).get("ai_provider", "none"),
        "rag_context_used": rag_used,
    }


# ============================================================
# 3. Trend Prediction Engine
# ============================================================

TREND_SYSTEM_PROMPT = (
    "你是一个短视频趋势预测专家。基于视频数据预测未来内容趋势。"
    "只基于实际数据分析, 禁止推测或编造。"
    "每条预测必须附带 confidence_score (0.0-1.0) 和 evidence_fields。"
    "以严格 JSON 格式输出。"
)

TREND_SCHEMA = """{
  "content_trends": [
    {"trend": "上升/下降/稳定的话题", "direction": "rising|falling|stable", "current_frequency": 0, "confidence_score": 0.8, "evidence_fields": ["title"]}
  ],
  "engagement_forecast": {
    "expected_avg_engagement": 0,
    "trend_direction": "upward|downward|flat",
    "key_driver": "驱动互动变化的主要因素",
    "confidence_score": 0.7,
    "evidence_fields": ["digg_count", "comment_count"]
  },
  "growth_trajectory": {
    "current_momentum": "accelerating|steady|decelerating",
    "projected_growth": "基于发布频率和互动趋势的预测",
    "bottleneck": "增长瓶颈",
    "confidence_score": 0.6,
    "evidence_fields": ["follower_count", "aweme_count"]
  },
  "emerging_opportunities": [
    {"opportunity": "机会描述", "action": "建议行动", "confidence_score": 0.6, "evidence_fields": ["title"]}
  ]
}"""


def _predict_trends(videos: list[dict], account_fields: dict | None, rag_context: str = "") -> dict:
    """趋势预测引擎"""
    from ai_service import _get_configs, _parse_json

    configs = _get_configs()
    if not configs:
        return {"error": "无可用 AI 配置", "ai_provider": "none"}

    # 构造 prompt: 只传统计摘要, 减少上下文
    total_likes = sum(v.get("digg_count") or 0 for v in videos)
    total_comments = sum(v.get("comment_count") or 0 for v in videos)
    total_shares = sum(v.get("share_count") or 0 for v in videos)

    # 按互动量取前 10 条标题
    top_videos = sorted(videos, key=lambda v: (v.get("digg_count") or 0), reverse=True)[:10]
    top_titles = "\n".join(
        f"- {(v.get('title') or '')[:50]} (点赞={v.get('digg_count', 0)})"
        for v in top_videos
    )

    account_json = json.dumps(account_fields, ensure_ascii=False) if account_fields else "无"

    rag_section = f"\n【RAG 上下文】\n{rag_context}\n" if rag_context else ""

    prompt = f"""请基于以下数据预测未来内容趋势。

【账号信息】
{account_json}

【视频统计】
- 视频总数: {len(videos)}
- 总点赞: {total_likes}
- 总评论: {total_comments}
- 总转发: {total_shares}
- 平均互动: {(total_likes + total_comments + total_shares) // max(len(videos), 1)}
{rag_section}
【高互动视频标题 (前10)】
{top_titles}

请严格按照以下 JSON Schema 输出:
{TREND_SCHEMA}

evidence_fields 必须使用真实字段名: title, digg_count, comment_count, share_count, follower_count, aweme_count
"""

    for cfg in configs:
        provider = cfg["provider"]
        try:
            if provider == "claude":
                from anthropic import Anthropic
                ac = Anthropic(api_key=cfg["api_key"])
                msg = ac.messages.create(
                    model=cfg["model"], max_tokens=2500,
                    system=TREND_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = msg.content[0].text
            else:
                base_url = cfg["base_url"]
                url = f"{base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": TREND_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                }
                with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                text = data["choices"][0]["message"]["content"]

            result = _parse_json(text)
            result["ai_provider"] = provider
            return result
        except Exception as e:
            print(f"[TrendPrediction] {cfg['label']} 失败: {e}")
            continue

    return {"error": "所有 AI 供应商均不可用", "ai_provider": "none"}


# ============================================================
# 4. Growth Strategy Recommendation Engine
# ============================================================

STRATEGY_SYSTEM_PROMPT = (
    "你是一个短视频增长策略专家。基于竞争情报分析结果, 生成可执行的增长策略建议。"
    "只基于提供的实际数据分析, 禁止推测或编造。"
    "每条建议必须附带 confidence_score 和 evidence_fields。"
    "以严格 JSON 格式输出。"
)

STRATEGY_SCHEMA = """{
  "executive_summary": "一段话概述核心策略方向",
  "short_term_actions": [
    {"action": "短期行动(1-2周)", "expected_impact": "预期效果", "priority": "high|medium|low", "confidence_score": 0.8, "evidence_fields": ["digg_count"]}
  ],
  "mid_term_strategy": [
    {"strategy": "中期策略(1-3月)", "milestone": "里程碑", "confidence_score": 0.7, "evidence_fields": ["follower_count"]}
  ],
  "content_calendar": {
    "recommended_topics": ["建议选题1", "建议选题2"],
    "optimal_posting_times": ["最佳发布时段"],
    "content_mix": {"比例描述": "如 40%教育/30%娱乐/30%互动"},
    "confidence_score": 0.7,
    "evidence_fields": ["create_time", "title"]
  },
  "kpi_targets": [
    {"metric": "指标名", "current": "当前值", "target": "目标值", "timeline": "时间线", "confidence_score": 0.6, "evidence_fields": ["follower_count"]}
  ],
  "risk_mitigation": [
    {"risk": "风险描述", "mitigation": "缓解措施", "confidence_score": 0.5, "evidence_fields": ["aweme_count"]}
  ]
}"""


def generate_strategy(video_analysis_id: str, use_rag: bool = True) -> dict:
    """第3步: 增长策略推荐引擎

    Returns: { video_analysis_id, strategy, ai_provider, rag_context_used }
    """
    va = get_video_analysis(video_analysis_id)
    if not va:
        raise ValueError(f"视频分析记录不存在: {video_analysis_id}")

    videos = va.get("videos") or []
    account_fields = va.get("account_fields") or {}
    account_name = va.get("account_name") or ""
    competitor_id = va.get("competitor_id")
    analysis = va.get("analysis") or {}

    # 获取已有 pattern 和 trend
    patterns = get_content_pattern(video_analysis_id)
    trends = get_trend_prediction(video_analysis_id)

    # RAG 上下文
    rag_context = ""
    rag_used = False
    if use_rag:
        try:
            rag_context = get_kb().build_context(f"{account_name} 增长策略", limit=3)
            if rag_context:
                rag_used = True
        except Exception as e:
            print(f"[intelligence] RAG 检索失败: {e}")

    from ai_service import _get_configs, _parse_json

    configs = _get_configs()
    if not configs:
        return {"error": "无可用 AI 配置", "ai_provider": "none"}

    # 构造 prompt
    account_json = json.dumps(account_fields, ensure_ascii=False) if account_fields else "无"
    patterns_json = json.dumps(patterns.get("patterns") if patterns else {}, ensure_ascii=False)[:800]
    trends_json = json.dumps(trends.get("predictions") if trends else {}, ensure_ascii=False)[:800]
    analysis_summary = json.dumps(analysis, ensure_ascii=False)[:800]

    rag_section = f"\n【RAG 上下文】\n{rag_context}\n" if rag_context else ""

    prompt = f"""基于以下竞争情报, 生成增长策略建议。

【账号信息】
{account_json}

【情报分析摘要】
{analysis_summary}

【内容模式摘要】
{patterns_json}

【趋势预测摘要】
{trends_json}
{rag_section}
请严格按照以下 JSON Schema 输出:
{STRATEGY_SCHEMA}

evidence_fields 必须使用真实字段名: follower_count, digg_count, comment_count, share_count, aweme_count, title, create_time
"""

    for cfg in configs:
        provider = cfg["provider"]
        try:
            if provider == "claude":
                from anthropic import Anthropic
                ac = Anthropic(api_key=cfg["api_key"])
                msg = ac.messages.create(
                    model=cfg["model"], max_tokens=3000,
                    system=STRATEGY_SYSTEM_PROMPT,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = msg.content[0].text
            else:
                base_url = cfg["base_url"]
                url = f"{base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": STRATEGY_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                }
                with httpx.Client(timeout=httpx.Timeout(120.0, connect=10.0)) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                text = data["choices"][0]["message"]["content"]

            result = _parse_json(text)
            result["ai_provider"] = provider

            # 存入 growth_strategies
            insert_growth_strategy({
                "video_analysis_id": video_analysis_id,
                "competitor_id": competitor_id,
                "strategy": result,
                "ai_provider": provider,
            })

            # 存入 RAG 知识库
            try:
                get_kb().store_entry(
                    competitor_id=competitor_id,
                    content_type="strategy",
                    title=f"{account_name} - 增长策略",
                    content=json.dumps(result, ensure_ascii=False),
                    metadata={},
                )
            except Exception as e:
                print(f"[intelligence] RAG 存储失败: {e}")

            return {
                "video_analysis_id": video_analysis_id,
                "strategy": result,
                "ai_provider": provider,
                "rag_context_used": rag_used,
            }
        except Exception as e:
            print(f"[StrategyEngine] {cfg['label']} 失败: {e}")
            continue

    return {"error": "所有 AI 供应商均不可用", "ai_provider": "none"}


# ============================================================
# 5. Multi Competitor Comparison Engine
# ============================================================

def compare_competitors(analysis_ids: list[str]) -> dict:
    """多竞争对手对比引擎

    Returns: { comparison_id, comparison_data, ai_provider }
    """
    if len(analysis_ids) < 2:
        raise ValueError("至少需要 2 个竞争对手才能对比")

    # 获取所有分析记录
    analyses = []
    for aid in analysis_ids:
        va = get_video_analysis(aid)
        if va:
            analyses.append(va)

    if len(analyses) < 2:
        raise ValueError("有效分析记录不足 2 条")

    # 调用 ComparisonAgent
    from agents.comparison_agent import _call_ai_for_comparison

    # 获取 RAG 上下文
    rag_context = ""
    try:
        names = [a.get("account_name", "") for a in analyses]
        rag_context = get_kb().build_context(" ".join(names), limit=3)
    except Exception:
        pass

    result = _call_ai_for_comparison(analyses, rag_context)

    # 存入 competitor_comparisons
    comparison = insert_comparison({
        "analysis_ids": analysis_ids,
        "comparison_data": result,
        "ai_provider": result.get("ai_provider", "none"),
    })

    # 存入 RAG
    try:
        get_kb().store_entry(
            competitor_id=None,
            content_type="comparison",
            title=f"多竞争对手对比 ({len(analyses)}个)",
            content=json.dumps(result, ensure_ascii=False),
            metadata={"analysis_ids": analysis_ids},
        )
    except Exception as e:
        print(f"[intelligence] RAG 存储失败: {e}")

    return {
        "comparison_id": comparison["id"],
        "comparison_data": result,
        "ai_provider": result.get("ai_provider", "none"),
    }


# ============================================================
# 6. Dashboard 数据
# ============================================================

def get_intelligence_dashboard() -> dict:
    """Real-time Analytics Dashboard 数据"""
    stats = dashboard_stats()
    kb_stats = get_kb().stats()
    stats["total_knowledge_entries"] = kb_stats.get("total", 0)
    stats["knowledge_by_type"] = kb_stats.get("by_type", {})
    return stats
