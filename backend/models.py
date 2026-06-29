"""models.py - Pydantic 数据模型 (请求/响应)"""
from typing import Optional
from pydantic import BaseModel, Field


# ---- 请求模型 ----
class AnalyzeRequest(BaseModel):
    """前端提交分析请求"""
    url: str                             # 竞争对手主页分享链接或 URL
    name: Optional[str] = None          # 竞争对手名称(可选, 不填则用域名)


class AIConfigCreate(BaseModel):
    """新增 AI 配置"""
    provider: str                       # 'deepseek' | 'claude' | 'glm' | 'openai'
    label: str                          # 显示名称
    api_key: str                        # API 密钥
    base_url: Optional[str] = None      # 接口地址(可空)
    model: str                          # 模型名
    is_active: bool = True
    priority: int = 0


class AIConfigUpdate(BaseModel):
    """更新 AI 配置(所有字段可选)"""
    provider: Optional[str] = None
    label: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


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


class AIConfigResponse(BaseModel):
    """返回给前端的 AI 配置(api_key 脱敏)"""
    id: str
    provider: str
    label: str
    api_key: str                        # 脱敏后的 key
    base_url: Optional[str] = None
    model: str
    is_active: bool
    priority: int
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
