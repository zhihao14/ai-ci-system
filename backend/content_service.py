"""content_service.py — AI 内容生成业务逻辑

职责:
1. 把竞品视频数据格式化为 AI prompt
2. 通过 ai_router 调用 DeepSeek/Claude/GLM (统一接口, 自动切换)
3. 解析 AI 返回的结构化 JSON
4. 可选写入 ai_analysis 表

三种输出:
  - rewritten_titles  改写标题 (5条, 不同角度)
  - new_scripts       新脚本 (3条, 含分镜+钩子+CTA)
  - similar_topics    相似选题 (N条, 差异化)
"""
import os
from typing import Optional

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from ai_router.base import AIMessage
from ai_router.router import get_router
from models_content import (
    VideoRef,
    GenerateResult,
    RewrittenTitle,
    NewScript,
    SimilarTopic,
)


# ============================================================
# 系统提示词
# ============================================================
SYSTEM_PROMPT = """你是一名资深短视频内容策划师, 擅长从竞品爆款视频中提炼可复用的内容策略。

你会收到一条竞品视频的数据(标题、互动数据), 请完成三项任务:

【任务 1: 改写标题】
基于原视频标题, 从 5 个不同角度改写, 保留核心吸引力但避免直接抄袭:
- 每条给出切入角度和钩子点
- 标题要适合短视频平台(15字以内最佳)

【任务 2: 新脚本】
为同赛道创作 3 条全新脚本, 每条包含:
- title: 脚本标题
- hook_first3s: 前3秒钩子(开场白, 要抓人)
- body: 脚本正文(拆分为 3-5 个分镜头/段落, 每段一句话)
- cta: 结尾行动号召
- duration_estimate: 预估时长(如 "30-45s")
- target_emotion: 目标情绪(如 好奇/焦虑/认同/惊喜)

【任务 3: 相似选题】
给出 {count} 个同赛道相似但差异化的选题, 每条包含:
- title: 选题标题
- angle: 切入角度
- difference: 与原视频的差异化点
- predicted_appeal: 预估吸引力(高/中/低)
- content_type: 内容形式(video/image/live)

【输出格式】
必须输出严格 JSON (不要 Markdown 代码块), 结构如下:
{
  "rewritten_titles": [
    {"title": "...", "angle": "...", "hook": "..."}
  ],
  "new_scripts": [
    {
      "title": "...",
      "hook_first3s": "...",
      "body": ["段落1", "段落2", "段落3"],
      "cta": "...",
      "duration_estimate": "30-45s",
      "target_emotion": "好奇"
    }
  ],
  "similar_topics": [
    {"title": "...", "angle": "...", "difference": "...", "predicted_appeal": "高", "content_type": "video"}
  ]
}

【原则】
- 改写标题: 5条, 角度分别为 悬念/数字/痛点/反差/情绪
- 新脚本: 3条, 风格各不相同
- 相似选题: {count}条, 必须能直接拍摄, 与原视频同赛道但非抄袭
- 所有文案用中文
"""


# ============================================================
# 构造用户 prompt
# ============================================================
def build_prompt(video: VideoRef, count: int) -> str:
    """把竞品视频数据格式化为用户 prompt"""
    lines = [f"【竞品视频数据】"]
    lines.append(f"标题: {video.title}")
    if video.description:
        # 描述截断, 控制 token
        desc = video.description[:500]
        lines.append(f"描述: {desc}")
    lines.append(f"平台: {video.platform}")
    lines.append(
        f"互动: 点赞 {video.like_count} | 评论 {video.comment_count} | "
        f"分享 {video.share_count} | 播放 {video.view_count}"
    )

    # 互动分析提示
    if video.view_count > 0:
        rate = video.like_count / video.view_count * 100
        lines.append(f"点赞率: {rate:.1f}%")

    lines.append(f"\n请输出 JSON: 5条改写标题 + 3条新脚本 + {count}条相似选题。")
    return "\n".join(lines)


# ============================================================
# 主生成函数
# ============================================================
def generate_content(
    video: VideoRef,
    model: str = "auto",
    count: int = 20,
) -> GenerateResult:
    """执行内容生成

    Args:
        video: 竞品视频数据
        model: AI 模型 (auto/deepseek/claude/glm/具体名)
        count: 相似选题数量
    Returns:
        GenerateResult 结构化结果
    """
    router = get_router()

    # 构造消息 (system 中嵌入 count)
    system = SYSTEM_PROMPT.replace("{count}", str(count))
    user_prompt = build_prompt(video, count)

    messages = [
        AIMessage(role="system", content=system),
        AIMessage(role="user", content=user_prompt),
    ]

    # 调用 AI (带重试, json_mode 强制 JSON 输出)
    resp = router.call_with_retry(
        messages=messages,
        model=model,
        max_retries=3,
        retry_delay=1.0,
        temperature=0.6,       # 内容生成用稍高温度增加创意
        json_mode=True,
    )

    content = resp.json_content or {}
    if not content:
        # JSON 解析失败, 用原始文本兜底
        raise RuntimeError(
            f"AI 返回内容无法解析为 JSON, provider={resp.provider}, "
            f"content={resp.content[:200]}"
        )

    # 解析三个维度
    rewritten = _parse_rewritten_titles(content.get("rewritten_titles", []))
    scripts = _parse_new_scripts(content.get("new_scripts", []))
    topics = _parse_similar_topics(content.get("similar_topics", []))

    return GenerateResult(
        source_title=video.title,
        source_platform=video.platform,
        rewritten_titles=rewritten,
        new_scripts=scripts,
        similar_topics=topics,
        model_used=resp.model,
        provider=resp.provider,
        prompt_tokens=resp.prompt_tokens,
        completion_tokens=resp.completion_tokens,
        latency_ms=resp.latency_ms,
    )


# ============================================================
# 解析函数 (容错处理)
# ============================================================
def _parse_rewritten_titles(items: list) -> list[RewrittenTitle]:
    """解析改写标题"""
    result = []
    for item in (items or [])[:5]:
        if not isinstance(item, dict):
            continue
        result.append(RewrittenTitle(
            title=str(item.get("title", "")).strip(),
            angle=str(item.get("angle", "")),
            hook=str(item.get("hook", "")),
        ))
    return result


def _parse_new_scripts(items: list) -> list[NewScript]:
    """解析新脚本"""
    result = []
    for item in (items or [])[:3]:
        if not isinstance(item, dict):
            continue
        body = item.get("body", [])
        if isinstance(body, str):
            body = [body]
        result.append(NewScript(
            title=str(item.get("title", "")).strip(),
            hook_first3s=str(item.get("hook_first3s", "")),
            body=[str(b) for b in body] if body else [],
            cta=str(item.get("cta", "")),
            duration_estimate=str(item.get("duration_estimate", "30-45s")),
            target_emotion=str(item.get("target_emotion", "")),
        ))
    return result


def _parse_similar_topics(items: list) -> list[SimilarTopic]:
    """解析相似选题"""
    result = []
    for item in (items or []):
        if not isinstance(item, dict):
            continue
        result.append(SimilarTopic(
            title=str(item.get("title", "")).strip(),
            angle=str(item.get("angle", "")),
            difference=str(item.get("difference", "")),
            predicted_appeal=str(item.get("predicted_appeal", "中")),
            content_type=str(item.get("content_type", "video")),
        ))
    return result


# ============================================================
# 可选: 写入数据库
# ============================================================
def save_to_db(
    result: GenerateResult,
    video_id: Optional[str] = None,
    account_id: Optional[str] = None,
) -> Optional[str]:
    """把生成结果写入 ai_analysis 表

    Returns: 插入的记录 id, 失败返回 None
    """
    from db import get_supabase

    result_json = {
        "source_title": result.source_title,
        "rewritten_titles": [t.model_dump() for t in result.rewritten_titles],
        "new_scripts": [s.model_dump() for s in result.new_scripts],
        "similar_topics": [t.model_dump() for t in result.similar_topics],
    }

    row = {
        "video_id": video_id,
        "account_id": account_id,
        "analysis_type": "content_generation",
        "summary": f"基于「{result.source_title[:30]}」生成 "
                   f"{len(result.rewritten_titles)}条标题 + "
                   f"{len(result.new_scripts)}条脚本 + "
                   f"{len(result.similar_topics)}条选题",
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
        print(f"[content_service] 写入数据库失败: {e}")
        return None
