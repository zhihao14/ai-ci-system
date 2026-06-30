"""base.py — Agent 基类 + 消息总线 + 状态机

设计:
  - BaseAgent:  所有 Agent 的抽象基类, 定义统一接口 run()
  - AgentContext: Agent 间共享的上下文 (数据传递)
  - AgentMessage: Agent 间通信的消息
  - AgentStatus: 状态枚举 (idle/running/success/failed)

Agent 生命周期:
  idle → running → success / failed
"""
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Optional

_CST = timezone(timedelta(hours=8))


class AgentStatus(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class AgentMessage:
    """Agent 间传递的消息"""
    from_agent: str               # 发送方 agent 名
    to_agent: str                 # 接收方 agent 名
    content: dict                 # 消息内容
    timestamp: str = field(default_factory=lambda: datetime.now(_CST).isoformat())


@dataclass
class AgentContext:
    """Agent 间共享的上下文 (流水线数据传递)

    每个 Agent 从 context 读取输入, 把输出写回 context,
    下游 Agent 从 context 读取上游的输出。
    """
    pipeline_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    started_at: str = field(default_factory=lambda: datetime.now(_CST).isoformat())

    # ---- 各阶段产出 (Agent 写入, 下游读取) ----
    # Crawler Agent 产出
    crawled_videos: list[dict] = field(default_factory=list)
    account_info: dict = field(default_factory=dict)

    # Trend Agent 产出
    anomalies: list[dict] = field(default_factory=list)
    viral_videos: list[dict] = field(default_factory=list)
    snapshot_result: dict = field(default_factory=dict)

    # Analysis Agent 产出
    analysis_result: dict = field(default_factory=dict)

    # Pattern Agent 产出
    pattern_result: dict = field(default_factory=dict)

    # Comparison Agent 产出
    comparison_result: dict = field(default_factory=dict)

    # Strategy Agent 产出
    strategy_result: dict = field(default_factory=dict)

    # ---- 流水线配置 ----
    params: dict = field(default_factory=dict)

    # ---- 日志 ----
    logs: list[dict] = field(default_factory=list)

    def log(self, agent: str, message: str, level: str = "info"):
        self.logs.append({
            "agent": agent,
            "message": message,
            "level": level,
            "time": datetime.now(_CST).isoformat(),
        })


class BaseAgent(ABC):
    """Agent 抽象基类

    子类必须实现 execute() 方法
    """

    def __init__(self, name: str):
        self.name = name
        self.status = AgentStatus.IDLE
        self.last_error: Optional[str] = None
        self.last_run_at: Optional[str] = None
        self.duration_ms: int = 0

    @abstractmethod
    async def execute(self, ctx: AgentContext) -> dict:
        """执行 Agent 任务

        Args:
            ctx: 共享上下文, 从中读取输入, 写回输出
        Returns:
            dict: 本 Agent 的产出摘要
        """
        ...

    async def run(self, ctx: AgentContext) -> dict:
        """运行 Agent (带状态管理与计时)

        子类不应重写此方法, 只实现 execute()
        """
        self.status = AgentStatus.RUNNING
        self.last_error = None
        ctx.log(self.name, f"{self.name} 开始执行")

        start = time.time()
        try:
            result = await self.execute(ctx)
            self.status = AgentStatus.SUCCESS
            self.last_run_at = datetime.now(_CST).isoformat()
            self.duration_ms = int((time.time() - start) * 1000)
            ctx.log(self.name, f"{self.name} 完成 ({self.duration_ms}ms)", "success")
            return result
        except Exception as e:
            self.status = AgentStatus.FAILED
            self.last_error = str(e)
            self.last_run_at = datetime.now(_CST).isoformat()
            self.duration_ms = int((time.time() - start) * 1000)
            ctx.log(self.name, f"{self.name} 失败: {e}", "error")
            raise

    def summary(self) -> dict:
        """返回 Agent 状态摘要"""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_run_at": self.last_run_at,
            "duration_ms": self.duration_ms,
            "last_error": self.last_error,
        }
