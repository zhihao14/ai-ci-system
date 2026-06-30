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
        "ai_provider": "处理中",
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
# 2. AI 多 Agent 分析 (Pattern + Analysis + Trend) — 分步执行避免超时
# ============================================================

# ---- Python 预计算统计 (避免 AI 超时) ----

import re
from collections import Counter
from datetime import datetime

_CN_STOPWORDS = {"的", "了", "是", "在", "我", "有", "和", "就", "不", "人", "都", "一", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "看", "好", "这", "那", "他", "她", "它", "们", "个", "中", "来", "对", "下", "但", "把", "给", "为", "什么", "怎么", "这个", "那个", "一个", "可以", "已经", "还是", "或者", "如果", "因为", "所以", "但是", "不过"}


def _compute_aggregate_analysis(videos: list[dict], account_fields: dict | None = None) -> dict:
    """Python 预计算统计分析 (无需 AI, 秒级完成)"""
    if not videos:
        return {
            "high_frequency_keywords": [],
            "engagement_ranking": [],
            "posting_time_pattern": {"peak_hours": [], "weekday_distribution": {}, "confidence_score": None, "status": "数据不足，无法判断", "evidence_fields": ["发布时间"]},
            "like_comment_ratio": {"average_ratio": None, "min_ratio": None, "max_ratio": None, "confidence_score": None, "status": "数据不足，无法判断", "evidence_fields": ["点赞数", "评论数"]},
            "top_content_types": [],
        }

    # 1. 高频关键词
    word_counter = Counter()
    for v in videos:
        text = (v.get("title") or "") + " " + (v.get("desc") or "")
        # 提取中文词组 (2-6 字) 和英文单词
        cn_words = re.findall(r"[\u4e00-\u9fff]{2,6}", text)
        en_words = re.findall(r"[a-zA-Z]{3,}", text)
        for w in cn_words + en_words:
            if w not in _CN_STOPWORDS and len(w) >= 2:
                word_counter[w] += 1
    high_freq = [
        {"keyword": kw, "occurrence_count": cnt, "confidence_score": 1.0, "evidence_fields": ["标题", "描述"]}
        for kw, cnt in word_counter.most_common(10) if cnt >= 2
    ]

    # 2. 互动量排名
    ranked = sorted(
        videos,
        key=lambda v: (v.get("digg_count") or 0) + (v.get("comment_count") or 0) + (v.get("share_count") or 0),
        reverse=True,
    )[:5]
    engagement_ranking = [
        {
            "rank": i + 1,
            "video_title": (v.get("title") or v.get("desc") or "")[:50],
            "total_engagement": (v.get("digg_count") or 0) + (v.get("comment_count") or 0) + (v.get("share_count") or 0),
            "digg_count": v.get("digg_count") or 0,
            "comment_count": v.get("comment_count") or 0,
            "share_count": v.get("share_count") or 0,
            "confidence_score": 1.0,
            "evidence_fields": ["点赞数", "评论数", "转发数"],
        }
        for i, v in enumerate(ranked)
    ]

    # 3. 发布时间规律
    hour_counts = Counter()
    weekday_counts = Counter()
    weekday_names = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for v in videos:
        ts = v.get("create_time_str") or v.get("create_time")
        if ts:
            try:
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts)
                else:
                    ts_str = str(ts).replace("Z", "+00:00")
                    dt = datetime.fromisoformat(ts_str)
                hour_counts[dt.hour] += 1
                weekday_counts[weekday_names[dt.weekday()]] += 1
            except Exception:
                pass
    if hour_counts:
        top_hours = hour_counts.most_common(3)
        peak_hours = [f"{h:02d}:00-{(h+1)%24:02d}:00" for h, _ in top_hours]
        posting_pattern = {
            "peak_hours": peak_hours,
            "weekday_distribution": dict(weekday_counts),
            "confidence_score": 1.0,
            "evidence_fields": ["发布时间"],
            "status": "数据充足已计算",
        }
    else:
        posting_pattern = {"peak_hours": [], "weekday_distribution": {}, "confidence_score": None, "status": "数据不足，无法判断", "evidence_fields": ["发布时间"]}

    # 4. 点赞评论比
    ratios = []
    for v in videos:
        digg = v.get("digg_count") or 0
        comment = v.get("comment_count") or 0
        if comment > 0:
            ratios.append(digg / comment)
    if ratios:
        ratio_data = {
            "average_ratio": round(sum(ratios) / len(ratios), 2),
            "min_ratio": round(min(ratios), 2),
            "max_ratio": round(max(ratios), 2),
            "confidence_score": 1.0,
            "evidence_fields": ["点赞数", "评论数"],
            "status": "数据充足已计算",
        }
    else:
        ratio_data = {"average_ratio": None, "min_ratio": None, "max_ratio": None, "confidence_score": None, "status": "数据不足，无法判断", "evidence_fields": ["点赞数", "评论数"]}

    # 5. 高表现内容类型 (简单关键词分类)
    type_keywords = {
        "美食/饮食": ["美食", "吃", "餐", "味", "食", "饮", "菜", "厨"],
        "健康/养生": ["健康", "养生", "运动", "健身", "跑步", "医疗"],
        "旅游/风景": ["旅游", "风景", "旅行", "打卡", "景点", "出游"],
        "新闻/资讯": ["新闻", "报道", "消息", "快讯", "最新", "突发"],
        "生活/日常": ["生活", "日常", "日常", "记录", "分享"],
        "文化/传统": ["文化", "传统", "历史", "非遗", "民俗", "龙舟", "龙船"],
        "天气/灾害": ["天气", "台风", "暴雨", "高温", "寒潮", "预警"],
        "科技/数码": ["科技", "数码", "手机", "AI", "智能", "技术"],
    }
    type_stats = {}
    for v in videos:
        title = (v.get("title") or v.get("desc") or "")
        engagement = (v.get("digg_count") or 0) + (v.get("comment_count") or 0) + (v.get("share_count") or 0)
        matched = False
        for ctype, keywords in type_keywords.items():
            if any(kw in title for kw in keywords):
                if ctype not in type_stats:
                    type_stats[ctype] = {"count": 0, "total_engagement": 0}
                type_stats[ctype]["count"] += 1
                type_stats[ctype]["total_engagement"] += engagement
                matched = True
                break
        if not matched:
            if "其他" not in type_stats:
                type_stats["其他"] = {"count": 0, "total_engagement": 0}
            type_stats["其他"]["count"] += 1
            type_stats["其他"]["total_engagement"] += engagement
    top_content_types = [
        {
            "content_type": ctype,
            "video_count": s["count"],
            "avg_engagement": round(s["total_engagement"] / s["count"], 1) if s["count"] else 0,
            "confidence_score": 0.8,
            "evidence_fields": ["标题", "点赞数"],
        }
        for ctype, s in sorted(type_stats.items(), key=lambda x: x[1]["total_engagement"], reverse=True)
    ]

    return {
        "high_frequency_keywords": high_freq,
        "engagement_ranking": engagement_ranking,
        "posting_time_pattern": posting_pattern,
        "like_comment_ratio": ratio_data,
        "top_content_types": top_content_types,
    }


def _generate_insights(stats: dict, account_fields: dict | None, account_name: str = "") -> list[dict]:
    """调用 AI 生成 actionable_insights (只传统计摘要, 大幅减少 prompt 体积)"""
    from ai_service import _get_configs, _parse_json

    configs = _get_configs()
    if not configs:
        return [{"insight": "无可用 AI 配置", "confidence_score": None, "evidence_fields": [], "supporting_data": ""}]

    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)
    account_json = json.dumps(account_fields, ensure_ascii=False) if account_fields else "无"

    prompt = f"""基于以下预计算的统计数据, 生成 3-5 条可执行洞察。
每条洞察必须引用具体数值, 禁止推测或编造。
evidence_fields 使用中文字段名（如：标题、描述、发布时间、点赞数、评论数、转发数）。

【账号】{account_name}
【账号字段】{account_json}
【统计数据】
{stats_json}

以 JSON 对象输出, 格式:
{{"insights": [{{"insight": "结论", "confidence_score": 0.9, "evidence_fields": ["标题", "点赞数"], "supporting_data": "引用的具体数值"}}]}}
"""

    for cfg in configs:
        provider = cfg["provider"]
        try:
            if provider == "claude":
                from anthropic import Anthropic
                ac = Anthropic(api_key=cfg["api_key"])
                msg = ac.messages.create(
                    model=cfg["model"], max_tokens=1500,
                    system="你是数据分析师。只输出JSON数组, 不要额外文字。所有内容用中文输出。",
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
                        {"role": "system", "content": "你是数据分析师。只输出JSON数组, 不要额外文字。所有内容用中文输出。"},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                }
                with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                text = data["choices"][0]["message"]["content"]
            result = _parse_json(text)
            # 确保 result 是列表
            if isinstance(result, dict) and "insights" in result:
                result = result["insights"]
            if not isinstance(result, list):
                result = [result]
            return result
        except Exception as e:
            print(f"[InsightsGen] {cfg['label']} 失败: {e}")
            continue

    return [{"insight": "AI 分析失败, 请检查配置", "confidence_score": None, "evidence_fields": [], "supporting_data": ""}]


def run_pattern_analysis(video_analysis_id: str, use_rag: bool = True) -> dict:
    """PatternAgent: 内容模式识别 (~20s)"""
    va = get_video_analysis(video_analysis_id)
    if not va:
        raise ValueError(f"视频分析记录不存在: {video_analysis_id}")

    videos = va.get("videos") or []
    account_fields = va.get("account_fields") or {}
    account_name = va.get("account_name") or ""
    competitor_id = va.get("competitor_id")

    rag_context = ""
    rag_used = False
    if use_rag:
        try:
            rag_context = get_kb().build_context(f"{account_name} 内容模式", limit=3)
            if rag_context:
                rag_used = True
        except Exception as e:
            print(f"[intelligence] RAG 检索失败: {e}")

    patterns = None
    try:
        from agents.pattern_agent import _call_ai_for_patterns
        patterns = _call_ai_for_patterns(videos, account_fields, rag_context)
        insert_content_pattern({
            "video_analysis_id": video_analysis_id,
            "competitor_id": competitor_id,
            "patterns": patterns,
            "confidence_score": patterns.get("engagement_patterns", {}).get("confidence_score"),
            "ai_provider": patterns.get("ai_provider"),
        })
    except Exception as e:
        print(f"[intelligence] PatternAgent 失败: {e}")
        patterns = {"error": str(e), "ai_provider": "无"}

    try:
        if patterns.get("ai_provider") != "无":
            get_kb().store_entry(
                competitor_id=competitor_id,
                content_type="pattern",
                title=f"{account_name} - 内容模式识别",
                content=json.dumps(patterns, ensure_ascii=False),
                metadata={},
            )
    except Exception as e:
        print(f"[intelligence] RAG 存储失败: {e}")

    return {
        "video_analysis_id": video_analysis_id,
        "patterns": patterns,
        "ai_provider": patterns.get("ai_provider", "无"),
        "rag_context_used": rag_used,
    }


def run_growth_analysis(video_analysis_id: str) -> dict:
    """Evidence-based Analysis (~15s, 统计预计算 + AI 只生成洞察)"""
    va = get_video_analysis(video_analysis_id)
    if not va:
        raise ValueError(f"视频分析记录不存在: {video_analysis_id}")

    videos = va.get("videos") or []
    account_info = va.get("account_info") or ""
    account_fields = va.get("account_fields") or {}
    account_name = va.get("account_name") or ""
    competitor_id = va.get("competitor_id")

    # 1. Python 预计算统计分析 (秒级, 无需 AI)
    aggregate = _compute_aggregate_analysis(videos, account_fields)

    # 2. AI 只生成 actionable_insights (小 prompt, ~10s)
    insights = _generate_insights(aggregate, account_fields, account_name)

    # 3. 合并结果
    analysis = {
        "data_completeness": "full" if videos else "partial",
        "raw_data_summary": {
            "has_account_info": bool(account_info.strip()),
            "has_video_data": bool(videos),
            "video_count": len(videos),
            "available_video_fields": list(videos[0].keys()) if videos else [],
            "missing_video_fields": [],
        },
        "aggregate_analysis": aggregate,
        "actionable_insights": insights,
        "ai_provider": "deepseek",
    }

    try:
        update_video_analysis(video_analysis_id, {
            "analysis": analysis,
            "ai_provider": "deepseek",
        })
    except Exception as e:
        print(f"[intelligence] 更新分析结果失败: {e}")

    try:
        summary = json.dumps(analysis, ensure_ascii=False)[:500]
        get_kb().store_entry(
            competitor_id=competitor_id,
            content_type="analysis",
            title=f"{account_name} - 竞争情报分析",
            content=summary,
            metadata={"analysis_keys": list(analysis.keys())},
        )
    except Exception as e:
        print(f"[intelligence] RAG 存储失败: {e}")

    return {
        "video_analysis_id": video_analysis_id,
        "analysis": analysis,
        "ai_provider": "deepseek",
    }


def run_trend_prediction(video_analysis_id: str, use_rag: bool = True) -> dict:
    """Trend Prediction Engine (~20s)"""
    va = get_video_analysis(video_analysis_id)
    if not va:
        raise ValueError(f"视频分析记录不存在: {video_analysis_id}")

    videos = va.get("videos") or []
    account_fields = va.get("account_fields") or {}
    account_name = va.get("account_name") or ""
    competitor_id = va.get("competitor_id")

    rag_context = ""
    rag_used = False
    if use_rag:
        try:
            rag_context = get_kb().build_context(f"{account_name} 趋势预测", limit=3)
            if rag_context:
                rag_used = True
        except Exception as e:
            print(f"[intelligence] RAG 检索失败: {e}")

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
        trends = {"error": str(e), "ai_provider": "无"}

    try:
        if trends.get("ai_provider") != "无":
            get_kb().store_entry(
                competitor_id=competitor_id,
                content_type="trend",
                title=f"{account_name} - 趋势预测",
                content=json.dumps(trends, ensure_ascii=False),
                metadata={},
            )
    except Exception as e:
        print(f"[intelligence] RAG 存储失败: {e}")

    return {
        "video_analysis_id": video_analysis_id,
        "trends": trends,
        "ai_provider": trends.get("ai_provider", "无"),
        "rag_context_used": rag_used,
    }


def run_analysis(video_analysis_id: str, use_rag: bool = True) -> dict:
    """运行所有3个分析步骤 (本地调试用, Railway 请用 step 分步接口)"""
    pattern_result = run_pattern_analysis(video_analysis_id, use_rag)
    growth_result = run_growth_analysis(video_analysis_id)
    trend_result = run_trend_prediction(video_analysis_id, use_rag)

    return {
        "video_analysis_id": video_analysis_id,
        "patterns": pattern_result["patterns"],
        "analysis": growth_result["analysis"],
        "trends": trend_result["trends"],
        "ai_provider": pattern_result.get("ai_provider", "无"),
        "rag_context_used": pattern_result.get("rag_context_used") or trend_result.get("rag_context_used"),
    }


# ============================================================
# 3. Trend Prediction Engine
# ============================================================

TREND_SYSTEM_PROMPT = (
    "你是一名商业分析师。基于视频数据预测未来内容趋势。"
    "只基于实际数据分析, 禁止推测或编造。"
    "每条预测必须附带数据准确度 (0.0-1.0) 和数据来源。"
    "以严格 JSON 格式输出。"
    "你的分析报告要像给老板看的商业报告，用通俗语言，不要用技术术语。"
)

TREND_SCHEMA = """{
  "content_trends": [
    {"trend": "上升/下降/稳定的话题", "direction": "rising|falling|stable", "current_frequency": 0, "confidence_score": 0.8, "evidence_fields": ["标题"]}
  ],
  "engagement_forecast": {
    "expected_avg_engagement": 0,
    "trend_direction": "upward|downward|flat",
    "key_driver": "驱动互动变化的主要因素",
    "confidence_score": 0.7,
    "evidence_fields": ["点赞数", "评论数"]
  },
  "growth_trajectory": {
    "current_momentum": "accelerating|steady|decelerating",
    "projected_growth": "基于发布频率和互动趋势的预测",
    "bottleneck": "增长瓶颈",
    "confidence_score": 0.6,
    "evidence_fields": ["粉丝数", "视频数"]
  },
  "emerging_opportunities": [
    {"opportunity": "机会描述", "action": "建议行动", "confidence_score": 0.6, "evidence_fields": ["标题"]}
  ]
}"""


def _predict_trends(videos: list[dict], account_fields: dict | None, rag_context: str = "") -> dict:
    """趋势预测引擎"""
    from ai_service import _get_configs, _parse_json

    configs = _get_configs()
    if not configs:
        return {"error": "无可用 AI 配置", "ai_provider": "无"}

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

evidence_fields 必须使用中文字段名: 标题, 点赞数, 评论数, 转发数, 粉丝数, 视频数
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

    return {"error": "所有 AI 供应商均不可用", "ai_provider": "无"}


# ============================================================
# 4. Growth Strategy Recommendation Engine
# ============================================================

STRATEGY_SYSTEM_PROMPT = (
    "你是一个短视频增长策略专家。基于竞争情报分析结果, 生成可执行的增长策略建议。"
    "只基于提供的实际数据分析, 禁止推测或编造。"
    "每条建议必须附带数据准确度和数据来源。"
    "以严格 JSON 格式输出。"
    "你的分析报告要像给老板看的商业报告，用通俗语言，不要用技术术语。"
)

STRATEGY_SCHEMA = """{
  "executive_summary": "一段话概述核心策略方向",
  "short_term_actions": [
    {"action": "短期行动(1-2周)", "expected_impact": "预期效果", "priority": "high|medium|low", "confidence_score": 0.8, "evidence_fields": ["点赞数"]}
  ],
  "mid_term_strategy": [
    {"strategy": "中期策略(1-3月)", "milestone": "里程碑", "confidence_score": 0.7, "evidence_fields": ["粉丝数"]}
  ],
  "content_calendar": {
    "recommended_topics": ["建议选题1", "建议选题2"],
    "optimal_posting_times": ["最佳发布时段"],
    "content_mix": {"比例描述": "如 40%教育/30%娱乐/30%互动"},
    "confidence_score": 0.7,
    "evidence_fields": ["发布时间", "标题"]
  },
  "kpi_targets": [
    {"metric": "指标名", "current": "当前值", "target": "目标值", "timeline": "时间线", "confidence_score": 0.6, "evidence_fields": ["粉丝数"]}
  ],
  "risk_mitigation": [
    {"risk": "风险描述", "mitigation": "缓解措施", "confidence_score": 0.5, "evidence_fields": ["视频数"]}
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
        return {"error": "无可用 AI 配置", "ai_provider": "无"}

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

【内容规律摘要】
{patterns_json}

【未来走势摘要】
{trends_json}
{rag_section}
请严格按照以下 JSON Schema 输出:
{STRATEGY_SCHEMA}

evidence_fields 必须使用中文字段名: 粉丝数, 点赞数, 评论数, 转发数, 视频数, 标题, 发布时间
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

    return {"error": "所有 AI 供应商均不可用", "ai_provider": "无"}


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
        "ai_provider": result.get("ai_provider", "无"),
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
        "ai_provider": result.get("ai_provider", "无"),
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
