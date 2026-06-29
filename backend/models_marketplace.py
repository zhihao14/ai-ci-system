"""models_marketplace.py — API Marketplace 数据模型"""
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# API Key 管理
# ============================================================
class CreateKeyRequest(BaseModel):
    """创建 API Key"""
    name: str = Field(..., max_length=100, description="Key 名称")
    description: Optional[str] = None
    plan: str = Field("free", pattern="^(free|pro|enterprise)$")
    rate_limit_per_min: int = Field(10, ge=1, le=1000)
    rate_limit_per_day: int = Field(100, ge=1, le=100000)
    allowed_apis: list[str] = Field(
        default_factory=lambda: ["analyze_video", "competitor_monitor", "generate_strategy"]
    )


class APIKeyResponse(BaseModel):
    """API Key 信息"""
    id: str
    key: str
    name: str
    description: Optional[str] = None
    plan: str = "free"
    rate_limit_per_min: int = 10
    rate_limit_per_day: int = 100
    allowed_apis: list[str] = []
    is_active: bool = True
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    last_used_at: Optional[str] = None


# ============================================================
# 开放 API 请求模型
# ============================================================
class VideoItem(BaseModel):
    """视频数据 (简化版, 兼容多平台)"""
    title: str
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0
    published_at: Optional[str] = None
    video_url: Optional[str] = None


class AnalyzeVideoRequest(BaseModel):
    """POST /v1/analyze_video"""
    videos: list[VideoItem] = Field(..., min_length=1, max_length=50, description="视频数组 (1-50条)")
    model: str = Field("auto", description="AI 模型: auto/deepseek/claude")


class CompetitorMonitorRequest(BaseModel):
    """POST /v1/competitor_monitor"""
    platform: str = Field("douyin", description="平台: douyin/xiaohongshu/youtube/tiktok")
    url: str = Field(..., description="竞品账号 URL")
    max_videos: int = Field(20, ge=1, le=50)
    auto_analyze: bool = Field(True, description="是否自动 AI 分析新视频")
    analysis_model: str = Field("auto")


class StrategyVideoInput(BaseModel):
    """策略生成的参考视频"""
    title: str
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0
    view_count: int = 0


class GenerateStrategyRequest(BaseModel):
    """POST /v1/generate_strategy"""
    video: StrategyVideoInput = Field(..., description="参考竞品视频")
    model: str = Field("auto", description="AI 模型")
    topic_count: int = Field(20, ge=5, le=30, description="相似选题数量")


# ============================================================
# 开放 API 响应模型
# ============================================================
class AnalyzeVideoResponse(BaseModel):
    """分析结果"""
    success: bool = True
    analysis: dict
    tokens: dict = {}
    request_id: Optional[str] = None


class CompetitorMonitorResponse(BaseModel):
    """监控结果"""
    success: bool = True
    account_id: Optional[str] = None
    crawled: int = 0
    new_videos: int = 0
    analyzed: int = 0
    analysis_id: Optional[str] = None
    error: Optional[str] = None
    request_id: Optional[str] = None


class GenerateStrategyResponse(BaseModel):
    """策略生成结果"""
    success: bool = True
    titles: list[dict] = []
    scripts: list[dict] = []
    topics: list[dict] = []
    strategy: Optional[dict] = None
    tokens: dict = {}
    request_id: Optional[str] = None


# ============================================================
# API 产品目录
# ============================================================
class APIProductResponse(BaseModel):
    """API 产品信息"""
    name: str
    display_name: str
    description: Optional[str] = None
    category: str
    cost_per_call: int = 1
    free_quota: int = 10
    is_active: bool = True
    is_featured: bool = False
    example_request: Optional[dict] = None
    example_response: Optional[dict] = None


# ============================================================
# 调用日志
# ============================================================
class CallLogResponse(BaseModel):
    """调用日志"""
    id: str
    api_name: str
    endpoint: str
    status_code: int
    response_time_ms: Optional[int] = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    error: Optional[str] = None
    called_at: Optional[str] = None
