"""knowledge_base.py — RAG 知识库

基于 Supabase 全文检索 (tsvector) 的知识库,
存储所有分析结果供后续 AI 分析时检索相关上下文。

功能:
1. store_entry()     — 存储知识条目
2. search()           — 全文检索
3. build_context()    — 构造 RAG 上下文文本 (供 AI prompt 注入)
4. store_analysis()   — 便捷方法: 把完整分析结果拆分存储
"""
import json
from typing import Optional

from db import get_supabase


class KnowledgeBase:
    """RAG 知识库 (单例)"""

    def store_entry(
        self,
        competitor_id: Optional[str],
        content_type: str,
        title: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> dict:
        """存储一条知识条目"""
        sb = get_supabase()
        row = sb.table("knowledge_base").insert({
            "competitor_id": competitor_id,
            "content_type": content_type,
            "title": title,
            "content": content,
            "metadata": metadata or {},
        }).execute()
        return row.data[0] if row.data else {}

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """全文检索知识库

        使用 Supabase textSearch 对 search_vector 做全文检索,
        返回匹配度排序的结果。
        """
        sb = get_supabase()
        res = (
            sb.table("knowledge_base")
            .select("id, competitor_id, content_type, title, content, metadata, created_at")
            .text_search("search_vector", query, {"type": "websearch", "config": "simple"})
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def build_context(self, query: str, limit: int = 3) -> str:
        """构造 RAG 上下文文本, 供 AI prompt 注入

        检索与 query 相关的历史知识, 格式化为文本块。
        如果无匹配结果, 返回空字符串。
        """
        results = self.search(query, limit=limit)
        if not results:
            return ""

        blocks = []
        for r in results:
            title = r.get("title") or "未命名"
            content_type = r.get("content_type", "")
            content = r.get("content", "")
            # 截断过长的内容, 避免上下文爆炸
            if len(content) > 500:
                content = content[:500] + "..."
            blocks.append(f"[{content_type}] {title}:\n{content}")

        return "\n\n---\n\n".join(blocks)

    def store_analysis(
        self,
        competitor_id: str,
        account_name: str,
        analysis: dict,
        patterns: Optional[dict] = None,
        trends: Optional[dict] = None,
        strategy: Optional[dict] = None,
    ) -> int:
        """便捷方法: 把完整分析结果拆分为多条知识条目存储

        Returns: 存储的条目数
        """
        count = 0

        # 1. 存储分析概要
        if analysis:
            summary = analysis.get("summary") or json.dumps(analysis, ensure_ascii=False)[:500]
            self.store_entry(
                competitor_id=competitor_id,
                content_type="analysis",
                title=f"{account_name} - 竞争情报分析",
                content=summary,
                metadata={"analysis_keys": list(analysis.keys())},
            )
            count += 1

        # 2. 存储内容模式
        if patterns:
            patterns_text = json.dumps(patterns, ensure_ascii=False)
            self.store_entry(
                competitor_id=competitor_id,
                content_type="pattern",
                title=f"{account_name} - 内容模式识别",
                content=patterns_text,
                metadata={},
            )
            count += 1

        # 3. 存储趋势预测
        if trends:
            trends_text = json.dumps(trends, ensure_ascii=False)
            self.store_entry(
                competitor_id=competitor_id,
                content_type="trend",
                title=f"{account_name} - 趋势预测",
                content=trends_text,
                metadata={},
            )
            count += 1

        # 4. 存储增长策略
        if strategy:
            strategy_text = json.dumps(strategy, ensure_ascii=False)
            self.store_entry(
                competitor_id=competitor_id,
                content_type="strategy",
                title=f"{account_name} - 增长策略",
                content=strategy_text,
                metadata={},
            )
            count += 1

        return count

    def list_entries(self, competitor_id: Optional[str] = None, limit: int = 20) -> list[dict]:
        """列出知识库条目"""
        sb = get_supabase()
        q = sb.table("knowledge_base").select(
            "id, competitor_id, content_type, title, content, created_at"
        ).order("created_at", desc=True).limit(limit)
        if competitor_id:
            q = q.eq("competitor_id", competitor_id)
        res = q.execute()
        return res.data or []

    def stats(self) -> dict:
        """知识库统计"""
        sb = get_supabase()
        res = sb.table("knowledge_base").select("content_type", count="exact").execute()
        total = res.count or 0
        # 按 content_type 分组统计
        type_counts = {}
        for row in (res.data or []):
            t = row.get("content_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1
        return {"total": total, "by_type": type_counts}


# ============================================================
# 单例
# ============================================================
_kb: Optional[KnowledgeBase] = None


def get_kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
    return _kb
