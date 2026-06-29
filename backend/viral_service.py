"""viral_service.py - 爆款分析业务逻辑

职责:
1. 把视频数据格式化为 AI 可读文本
2. 构造爆款分析 prompt
3. 调用 ai_client 获取结构化结果
4. 可选写入 ai_analysis 表
"""
import json
from typing import Optional

from ai_client import call_ai, AIResponse
from models_viral import VideoInput, ViralAnalysisResult


# ============================================================
# 系统提示词: 定义 AI 角色 + 输出格式约束
# ============================================================
SYSTEM_PROMPT = """你是一名资深的短视频爆款分析师, 专注抖音/TikTok 内容研究。
你擅长从视频数据中提炼爆款规律: 标题结构、内容套路、情绪触发点、可复制的选题方向。

【输出要求】
必须输出严格 JSON (不要 Markdown 代码块, 不要额外文字), 结构如下:
{
  "overview": "总体概述, 一段话总结这批视频的爆款特征 (<=200字)",
  "viral_reasons": [
    {
      "factor": "因素名, 如 情感共鸣/反差冲击/实用价值/稀缺性",
      "detail": "为什么这个因素促成了爆款",
      "evidence": "对应哪条视频/标题佐证"
    }
  ],
  "title_patterns": [
    {
      "pattern": "标题结构模式, 如 数字+痛点+解决方案",
      "examples": ["从视频中提取的实例标题1", "实例标题2"],
      "template": "可套用的模板, 如 '3个{领域}{痛点}的{解决方案}'"
    }
  ],
  "content_tactics": [
    {
      "name": "套路名称, 如 痛点前置/悬念钩子/数据对比",
      "description": "具体做法描述",
      "frequency": "出现频率, 如 '8/10视频'"
    }
  ],
  "topic_suggestions": [
    {
      "title": "建议的可复制标题",
      "angle": "切入角度",
      "why_works": "为何可行, 基于上述分析",
      "target_platform": "douyin"
    }
  ]
}

【分析原则】
- viral_reasons: 3-5 条, 从数据/情绪/内容/时机多维度
- title_patterns: 提炼 2-4 种标题模式, 必须从输入标题中归纳而非臆造
- content_tactics: 3-5 条, 描述具体可操作的套路
- topic_suggestions: 3-5 条, 必须能直接拿来拍, 与原视频同赛道但非抄袭
"""


# ============================================================
# 视频数据格式化: 把列表转成 AI 易读的文本表格
# ============================================================
def _format_videos(videos: list[VideoInput]) -> str:
    """把视频列表格式化为紧凑的文本, 控制 token 消耗"""
    lines = []
    for i, v in enumerate(videos, 1):
        # 计算互动率 (点赞/播放), 若无播放数则留空
        eng_rate = ""
        if v.view_count > 0:
            eng_rate = f"{(v.like_count / v.view_count * 100):.1f}%"

        lines.append(
            f"{i}. 标题: {v.title}\n"
            f"   点赞: {v.like_count} | 评论: {v.comment_count} | "
            f"分享: {v.share_count} | 播放: {v.view_count}"
            + (f" | 互动率: {eng_rate}" if eng_rate else "")
            + (f" | 发布: {v.published_at}" if v.published_at else "")
        )
    return "\n".join(lines)


# ============================================================
# 构造用户 prompt
# ============================================================
def build_prompt(videos: list[VideoInput]) -> str:
    """构造用户提示词, 包含视频数据与分析要求"""
    video_text = _format_videos(videos)
    return f"""请分析以下 {len(videos)} 条视频数据, 找出爆款规律并给出可复制建议。

【视频数据】
{video_text}

【分析要求】
1. 从点赞/评论/分享数据判断哪些是真爆款 (高互动)
2. 归纳标题的共同结构, 给出可套用的模板
3. 总结内容创作套路 (开场/节奏/钩子/结尾)
4. 给出 3-5 个同赛道可立即复制的选题, 标题要具体

请输出 JSON。"""


# ============================================================
# 主分析函数
# ============================================================
def analyze_viral(
    videos: list[VideoInput],
    model: str = "auto",
) -> ViralAnalysisResult:
    """执行爆款分析

    Args:
        videos: 视频数据列表
        model:  AI 模型选择
    Returns:
        ViralAnalysisResult 结构化结果
    """
    prompt = build_prompt(videos)
    resp: AIResponse = call_ai(
        prompt=prompt,
        system=SYSTEM_PROMPT,
        model=model,
        temperature=0.4,
    )

    content = resp.content
    return ViralAnalysisResult(
        overview=content.get("overview", ""),
        viral_reasons=content.get("viral_reasons", []),
        title_patterns=content.get("title_patterns", []),
        content_tactics=content.get("content_tactics", []),
        topic_suggestions=content.get("topic_suggestions", []),
        model_used=resp.model,
        provider=resp.provider,
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
    )


# ============================================================
# 可选: 写入数据库 (ai_analysis 表)
# ============================================================
def save_analysis_to_db(
    result: ViralAnalysisResult,
    account_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Optional[str]:
    """把分析结果写入 ai_analysis 表

    Returns: 插入的记录 id, 失败返回 None
    """
    from db import get_supabase

    # 构建 jsonb 结果 (存原始分析, 便于后续查询)
    result_json = {
        "overview": result.overview,
        "viral_reasons": [r.model_dump() for r in result.viral_reasons],
        "title_patterns": [p.model_dump() for p in result.title_patterns],
        "content_tactics": [t.model_dump() for t in result.content_tactics],
        "topic_suggestions": [s.model_dump() for s in result.topic_suggestions],
    }

    row = {
        "account_id": account_id,
        "video_id": video_id,
        "analysis_type": "viral_analysis",
        "summary": result.overview[:500] if result.overview else None,
        "result": result_json,
        "ai_provider": result.provider,
        "ai_model": result.model_used,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }

    try:
        sb = get_supabase()
        res = sb.table("ai_analysis").insert(row).execute()
        return res.data[0]["id"] if res.data else None
    except Exception as e:
        print(f"[viral_service] 写入数据库失败: {e}")
        return None
