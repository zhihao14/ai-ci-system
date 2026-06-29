"""models_content.py — AI 内容生成模块的数据模型"""
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# 请求模型
# ============================================================
class VideoRef(BaseModel):
    """参考视频数据 (输入)"""
    title: str = Field(description="竞品视频标题")
    description: Optional[str] = Field(default=None, description="视频描述/文案")
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0
    platform: Optional[str] = Field(default="douyin", description="来源平台")


class GenerateRequest(BaseModel):
    """POST /generate 入参"""
    video: VideoRef = Field(description="参考视频数据")
    model: str = Field(
        default="auto",
        description="auto | deepseek | claude | glm | 具体模型名",
    )
    count: int = Field(default=20, ge=5, le=30, description="相似选题数量")
    save_to_db: bool = Field(default=False, description="是否写入 ai_analysis 表")
    account_id: Optional[str] = None


# ============================================================
# 响应模型 — 3 个输出维度
# ============================================================
class RewrittenTitle(BaseModel):
    """改写标题"""
    title: str                        # 改写后的标题
    angle: str                        # 切入角度
    hook: str                         # 钩子点 (为什么吸引人)


class NewScript(BaseModel):
    """新脚本"""
    title: str                        # 脚本标题
    hook_first3s: str                 # 前3秒钩子 (开场白)
    body: list[str]                   # 脚本正文 (分镜头/分段)
    cta: str                          # 结尾行动号召
    duration_estimate: str            # 预估时长, 如 "30-45s"
    target_emotion: str               # 目标情绪, 如 "好奇/焦虑/认同"


class SimilarTopic(BaseModel):
    """相似选题"""
    title: str                        # 选题标题
    angle: str                        # 切入角度
    difference: str                   # 与原视频的差异化点
    predicted_appeal: str             # 预估吸引力, 如 "高/中/低"
    content_type: str = "video"       # 内容形式: video/image/live


class GenerateResult(BaseModel):
    """完整生成结果"""
    # ---- 输入回显 ----
    source_title: str
    source_platform: str

    # ---- 3 个输出维度 ----
    rewritten_titles: list[RewrittenTitle]       # 改写标题 (5条)
    new_scripts: list[NewScript]                 # 新脚本 (3条)
    similar_topics: list[SimilarTopic]           # 相似选题 (N条)

    # ---- 元信息 ----
    model_used: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
