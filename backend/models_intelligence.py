"""models_intelligence.py — 智能分析模块的 Pydantic 模型"""
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# 请求模型
# ============================================================

class IntelligenceCrawlRequest(BaseModel):
    """第1步: 爬取 50 条视频"""
    url: str
    max_videos: int = 50


class IntelligenceAnalyzeRequest(BaseModel):
    """第2步: AI 多 Agent 分析 (模式识别 + 情报分析 + 趋势预测)"""
    video_analysis_id: str
    use_rag: bool = True


class IntelligenceStrategyRequest(BaseModel):
    """第3步: 增长策略生成"""
    video_analysis_id: str
    use_rag: bool = True


class ComparisonRequest(BaseModel):
    """多竞争对手对比"""
    analysis_ids: list[str] = Field(..., min_length=2, max_length=5)


class KnowledgeSearchRequest(BaseModel):
    """RAG 知识库搜索"""
    query: str
    limit: int = 5


# ============================================================
# 响应模型
# ============================================================

class CrawlResponse(BaseModel):
    """爬取结果"""
    video_analysis_id: str
    url: str
    account_name: str
    account_info: str
    account_fields: Optional[dict] = None
    videos: list = Field(default_factory=list)
    video_count: int = 0


class AnalyzeResponse(BaseModel):
    """分析结果"""
    video_analysis_id: str
    patterns: Optional[dict] = None
    analysis: Optional[dict] = None
    trends: Optional[dict] = None
    ai_provider: str = "none"
    rag_context_used: bool = False


class StrategyResponse(BaseModel):
    """策略结果"""
    video_analysis_id: str
    strategy: Optional[dict] = None
    ai_provider: str = "none"
    rag_context_used: bool = False


class ComparisonResponse(BaseModel):
    """对比结果"""
    comparison_id: str
    comparison_data: Optional[dict] = None
    ai_provider: str = "none"


class KnowledgeSearchResult(BaseModel):
    """知识库搜索结果条目"""
    id: str
    content_type: str
    title: Optional[str] = None
    content: str
    created_at: Optional[str] = None


class DashboardStats(BaseModel):
    """仪表盘统计数据"""
    total_analyses: int = 0
    total_competitors: int = 0
    total_knowledge_entries: int = 0
    total_comparisons: int = 0
    recent_analyses: list = Field(default_factory=list)
    knowledge_by_type: dict = Field(default_factory=dict)
