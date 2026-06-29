"""crawler_agent.py — 采集 Agent

职责: 调用多平台爬虫采集视频数据, 写入数据库
输入: ctx.params 中的 platform / url / account_id / max_videos
输出: ctx.crawled_videos + ctx.account_info
"""
from typing import Optional

from .base import BaseAgent, AgentContext


class CrawlerAgent(BaseAgent):
    def __init__(self):
        super().__init__("CrawlerAgent")

    async def execute(self, ctx: AgentContext) -> dict:
        from crawler_manager import crawl_and_save, run_crawler, detect_platform_from_url

        platform = ctx.params.get("platform")
        url = ctx.params.get("url")
        account_id = ctx.params.get("account_id")
        max_videos = ctx.params.get("max_videos", 20)
        save_to_db = ctx.params.get("save_to_db", True)

        # 自动检测平台
        if not platform and url:
            platform = detect_platform_from_url(url)
            if not platform:
                raise ValueError(f"无法从 URL 识别平台: {url}")

        if not platform:
            raise ValueError("缺少 platform 或 url 参数")

        ctx.log(self.name, f"开始采集: platform={platform}, url={url or '(from account)'}")

        if save_to_db:
            result = crawl_and_save(
                platform=platform,
                url=url,
                account_id=account_id,
                max_videos=max_videos,
            )
        else:
            raw = run_crawler(platform, url, max_videos)
            result = {
                "account_id": None,
                "platform": platform,
                "account_name": raw.get("account_name", ""),
                "follower_count": raw.get("follower_count", 0),
                "crawled": len(raw.get("videos", [])),
                "videos": raw.get("videos", []),
            }

        # 写入上下文
        ctx.crawled_videos = result.get("videos", [])
        ctx.account_info = {
            "account_id": result.get("account_id"),
            "platform": result.get("platform", platform),
            "account_name": result.get("account_name", ""),
            "follower_count": result.get("follower_count", 0),
            "crawled_count": result.get("crawled", 0),
        }

        return {
            "agent": self.name,
            "platform": platform,
            "crawled": result.get("crawled", 0),
            "account_name": result.get("account_name", ""),
        }
