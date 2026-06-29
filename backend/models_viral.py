"""models_viral.py - 爆款分析模块的数据模型"""
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# 请求模型
# ============================================================
class VideoInput(BaseModel):
    """单条视频输入 (与 videos 表 / 爬虫输出字段对齐)"""
    video_id: Optional[str] = None
    title: str
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0
    published_at: Optional[str] = None
    video_url: Optional[str] = None
    cover_url: Optional[str] = None


class ViralAnalysisRequest(BaseModel):
    """POST /analyze_viral 入参: 视频数组 + 模型选择"""
    videos: list[VideoInput] = Field(..., min_length=1, max_length=50)
    model: str = Field(
        default="auto",
        description="auto | deepseek | claude | 具体模型名",
    )
    save_to_db: bool = Field(
        default=False,
        description="是否写入 ai_analysis 表 (需传 account_id/video_id)",
    )
    account_id: Optional[str] = None


# ============================================================
# 响应模型 - 结构化爆款分析结果
# ============================================================
class ViralReason(BaseModel):
    """单条爆款原因"""
    factor: str                            # 因素, 如 "情感共鸣"
    detail: str                            # 详细说明
    evidence: str                         # 对应的视频证据 (哪个视频/标题)


class TitlePattern(BaseModel):
    """标题结构模式"""
    pattern: str                           # 模式, 如 "数字+痛点+解决方案"
    examples: list[str] = Field(default_factory=list)   # 从视频中提取的实例
    template: str                          # 可套用的模板


class ContentTactic(BaseModel):
    """内容套路"""
    name: str                              # 套路名称, 如 "痛点前置"
    description: str                       # 描述
    frequency: str                         # 出现频率, 如 "8/10 视频"


class TopicSuggestion(BaseModel):
    """可复制选题建议"""
    title: str                             # 建议的标题
    angle: str                             # 切入角度
    why_works: str                         # 为何可行 (基于分析)
    target_platform: str = "douyin"        # 适配平台


class ViralAnalysisResult(BaseModel):
    """完整爆款分析结果"""
    overview: str                          # 总体概述
    viral_reasons: list[ViralReason]                       # 爆款原因
    title_patterns: list[TitlePattern]                     # 标题结构
    content_tactics: list[ContentTactic]                  # 内容套路
    topic_suggestions: list[TopicSuggestion]              # 可复制选题
    model_used: str                                        # 实际使用的模型
    provider: str                                          # 'deepseek' | 'claude'
    prompt_tokens: int = 0
    completion_tokens: int = 0
