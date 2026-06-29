"""models.py - Pydantic 数据模型 (请求/响应)"""
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


# ---- 请求模型 ----
class AnalyzeRequest(BaseModel):
    """前端提交分析请求"""
    url: HttpUrl                        # 竞争对手网站 URL
    name: Optional[str] = None          # 竞争对手名称(可选, 不填则用域名)


# ---- 响应模型 ----
class IntelligenceReport(BaseModel):
    """返回给前端的情报报告"""
    id: str
    competitor_id: Optional[str] = None
    url: str
    title: Optional[str] = None
    summary: Optional[str] = None
    products: list = Field(default_factory=list)
    pricing: list = Field(default_factory=list)
    positioning: dict = Field(default_factory=dict)
    strengths: list = Field(default_factory=list)
    weaknesses: list = Field(default_factory=list)
    recent_changes: Optional[str] = None
    ai_provider: Optional[str] = None
    created_at: Optional[str] = None
