"""monitor_service.py — 自动监控调度核心逻辑

职责:
  1. 扫描数据库中所有账号
  2. 对每个账号: 调爬虫抓新视频 → 入库
  3. 对新视频: 调 AI 做爆款分析 → 存 ai_analysis 表
  4. 记录每轮监控到 monitor_runs / monitor_tasks 表

复用已有模块:
  - crawler_manager.crawl_and_save()  — 爬虫采集
  - viral_service.analyze_viral()     — AI 爆款分析
  - db_accounts.list_accounts()       — 账号列表
"""
import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from db import get_supabase
from db_accounts import list_accounts, upsert_video
from crawler_manager import crawl_and_save, build_profile_url

logger = logging.getLogger("monitor")

_CST = timezone(timedelta(hours=8))


# ============================================================
# WebSocket 事件推送 (安全调用, 无连接时静默跳过)
# ============================================================
def _emit(coro):
    """安全执行异步广播 (在同步函数中调用)"""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        # 无事件循环 (同步调用), 创建新线程运行
        import threading
        def _run():
            try:
                asyncio.run(coro)
            except Exception:
                pass
        threading.Thread(target=_run, daemon=True).start()
    except Exception:
        pass


# ============================================================
# 监控轮次管理
# ============================================================
def create_monitor_run(run_type: str = "scheduled") -> str:
    """创建一轮监控记录, 返回 run_id"""
    sb = get_supabase()
    row = {
        "run_type": run_type,
        "status": "running",
        "started_at": datetime.now(_CST).isoformat(),
    }
    res = sb.table("monitor_runs").insert(row).execute()
    return res.data[0]["id"]


def finish_monitor_run(
    run_id: str,
    status: str = "success",
    stats: Optional[dict] = None,
    error: Optional[str] = None,
):
    """完成监控轮次, 更新统计"""
    sb = get_supabase()
    update_data = {
        "status": status,
        "finished_at": datetime.now(_CST).isoformat(),
    }
    if stats:
        update_data.update({
            "total_accounts": stats.get("total", 0),
            "crawled_accounts": stats.get("crawled", 0),
            "failed_accounts": stats.get("failed", 0),
            "skipped_accounts": stats.get("skipped", 0),
            "new_videos": stats.get("new_videos", 0),
            "analyzed_videos": stats.get("analyzed", 0),
            "total_tokens": stats.get("total_tokens", 0),
        })
    if error:
        update_data["error"] = error
    sb.table("monitor_runs").update(update_data).eq("id", run_id).execute()


def create_monitor_task(run_id: str, account: dict) -> str:
    """创建单账号监控任务, 返回 task_id"""
    sb = get_supabase()
    row = {
        "run_id": run_id,
        "account_id": account.get("id"),
        "platform": account.get("platform"),
        "account_name": account.get("name"),
        "status": "pending",
    }
    res = sb.table("monitor_tasks").insert(row).execute()
    return res.data[0]["id"]


def update_monitor_task(task_id: str, data: dict):
    """更新监控任务"""
    sb = get_supabase()
    update_data = dict(data)
    update_data["finished_at"] = datetime.now(_CST).isoformat()
    sb.table("monitor_tasks").update(update_data).eq("id", task_id).execute()


# ============================================================
# 单账号监控: 采集 + 分析
# ============================================================
def monitor_account(
    run_id: str,
    account: dict,
    max_videos: int = 20,
    analyze: bool = True,
    analysis_model: str = "auto",
) -> dict:
    """监控单个账号: 采集新视频 → AI 分析

    Args:
        run_id:     监控轮次 ID
        account:    账号信息 (含 id, platform, platform_uid, name)
        max_videos: 爬取上限
        analyze:    是否做 AI 分析
        analysis_model: AI 模型

    Returns:
        dict: { status, crawled, new_count, analyzed, tokens, errors }
    """
    account_id = account["id"]
    platform = account.get("platform", "")
    platform_uid = account.get("platform_uid", "")
    account_name = account.get("name", "")

    task_id = create_monitor_task(run_id, account)

    update_monitor_task(task_id, {"status": "running", "started_at": datetime.now(_CST).isoformat()})

    result = {
        "task_id": task_id,
        "account_id": account_id,
        "platform": platform,
        "account_name": account_name,
        "status": "success",
        "crawled": 0,
        "new_count": 0,
        "analyzed": 0,
        "tokens": 0,
        "crawl_error": None,
        "analysis_error": None,
    }

    # ---- Step 1: 采集 ----
    crawl_start = time.time()

    # WebSocket: 推送"正在采集"
    from ws_manager import emit_account_crawling
    _emit(emit_account_crawling(run_id, account_name, platform, 0, 0))

    try:
        # 构建 URL
        url = build_profile_url(platform, platform_uid)

        # 调爬虫采集并入库
        crawl_result = crawl_and_save(
            platform=platform,
            url=url,
            account_id=account_id,
            max_videos=max_videos,
        )

        crawl_duration = int((time.time() - crawl_start) * 1000)
        videos = crawl_result.get("videos", [])
        result["crawled"] = len(videos)

        # 找出新增视频 (之前 DB 中不存在的)
        new_video_ids = _find_new_videos(account_id, videos)
        result["new_count"] = len(new_video_ids)

        update_monitor_task(task_id, {
            "status": "success" if videos else "skipped",
            "crawled_count": len(videos),
            "new_count": len(new_video_ids),
            "video_ids": new_video_ids,
            "crawl_duration_ms": crawl_duration,
        })

        logger.info(
            f"  [{account_name}] 采集完成: {len(videos)} 条视频, "
            f"新增 {len(new_video_ids)} 条 ({crawl_duration}ms)"
        )

        # WebSocket: 推送"采集完成"
        from ws_manager import emit_crawl_done
        _emit(emit_crawl_done(run_id, account_name, len(videos), len(new_video_ids), crawl_duration))

    except Exception as e:
        crawl_duration = int((time.time() - crawl_start) * 1000)
        result["status"] = "failed"
        result["crawl_error"] = str(e)
        update_monitor_task(task_id, {
            "status": "failed",
            "crawl_error": str(e),
            "crawl_duration_ms": crawl_duration,
        })
        logger.error(f"  [{account_name}] 采集失败: {e}")

        # WebSocket: 推送错误
        from ws_manager import emit_error
        _emit(emit_error(run_id, account_name, "crawl", str(e)))
        return result

    # ---- Step 2: AI 分析 (只分析新增视频) ----
    if analyze and result["new_count"] > 0:
        analysis_start = time.time()

        # WebSocket: 推送"正在 AI 分析"
        from ws_manager import emit_analysis_start
        _emit(emit_analysis_start(run_id, account_name, result["new_count"]))

        try:
            analysis_result = _analyze_new_videos(
                account_id=account_id,
                new_video_ids=new_video_ids,
                videos=videos,
                model=analysis_model,
            )

            analysis_duration = int((time.time() - analysis_start) * 1000)
            prompt_tokens = analysis_result.get("prompt_tokens", 0)
            completion_tokens = analysis_result.get("completion_tokens", 0)

            result["analyzed"] = analysis_result.get("analyzed", 0)
            result["tokens"] = prompt_tokens + completion_tokens
            result["analysis_error"] = analysis_result.get("error")

            update_monitor_task(task_id, {
                "analysis_id": analysis_result.get("analysis_id"),
                "analysis_type": analysis_result.get("analysis_type"),
                "analysis_status": analysis_result.get("status", "success"),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "analysis_duration_ms": analysis_duration,
            })

            logger.info(
                f"  [{account_name}] 分析完成: {result['analyzed']} 条视频, "
                f"消耗 {result['tokens']} tokens ({analysis_duration}ms)"
            )

            # WebSocket: 推送"分析完成"
            from ws_manager import emit_analysis_done
            _emit(emit_analysis_done(run_id, account_name, result["analyzed"], result["tokens"], analysis_duration))

        except Exception as e:
            analysis_duration = int((time.time() - analysis_start) * 1000)
            result["analysis_error"] = str(e)
            update_monitor_task(task_id, {
                "analysis_status": "failed",
                "analysis_error": str(e),
                "analysis_duration_ms": analysis_duration,
            })
            logger.error(f"  [{account_name}] 分析失败: {e}")

            # WebSocket: 推送分析错误
            from ws_manager import emit_error
            _emit(emit_error(run_id, account_name, "analysis", str(e)))
    else:
        # 无新视频或不需要分析
        update_monitor_task(task_id, {
            "analysis_status": "skipped",
        })

    return result


# ============================================================
# 完整监控轮次
# ============================================================
def run_monitor_cycle(
    max_accounts: int = 100,
    max_videos: int = 20,
    analyze: bool = True,
    analysis_model: str = "auto",
    run_type: str = "scheduled",
) -> dict:
    """执行一轮完整监控: 扫描所有账号 → 采集 → 分析

    Args:
        max_accounts:  最大扫描账号数
        max_videos:    每个账号爬取上限
        analyze:       是否做 AI 分析
        analysis_model: AI 模型
        run_type:      'scheduled' | 'manual'

    Returns:
        dict: 完整监控结果
    """
    run_id = create_monitor_run(run_type)
    logger.info(f"{'=' * 60}")
    logger.info(f"开始监控轮次 {run_id} (类型: {run_type})")

    # 1. 获取所有账号
    accounts = list_accounts(limit=max_accounts)
    total = len(accounts)
    logger.info(f"扫描到 {total} 个账号")

    # WebSocket: 推送"监控开始"
    from ws_manager import emit_monitor_start, emit_monitor_done
    _emit(emit_monitor_start(run_id, total, run_type))

    if total == 0:
        finish_monitor_run(run_id, status="success", stats={
            "total": 0, "crawled": 0, "failed": 0, "skipped": 0,
            "new_videos": 0, "analyzed": 0, "total_tokens": 0,
        })
        _emit(emit_monitor_done(run_id, {"total": 0}, "success"))
        logger.info("无账号需要监控, 轮次结束")
        return {"run_id": run_id, "total": 0, "message": "无账号"}

    # 2. 逐个账号监控
    stats = {
        "total": total,
        "crawled": 0,
        "failed": 0,
        "skipped": 0,
        "new_videos": 0,
        "analyzed": 0,
        "total_tokens": 0,
    }
    account_results = []

    for i, account in enumerate(accounts, 1):
        logger.info(f"[{i}/{total}] 监控账号: {account.get('name', '')} ({account.get('platform', '')})")

        # WebSocket: 推送"正在采集" (带进度)
        from ws_manager import emit_account_crawling
        _emit(emit_account_crawling(run_id, account.get('name', ''), account.get('platform', ''), i, total))

        try:
            result = monitor_account(
                run_id=run_id,
                account=account,
                max_videos=max_videos,
                analyze=analyze,
                analysis_model=analysis_model,
            )
            account_results.append(result)

            if result["status"] == "success":
                if result["new_count"] > 0:
                    stats["crawled"] += 1
                else:
                    stats["skipped"] += 1
            else:
                stats["failed"] += 1

            stats["new_videos"] += result["new_count"]
            stats["analyzed"] += result["analyzed"]
            stats["total_tokens"] += result["tokens"]

        except Exception as e:
            logger.error(f"  账号 {account.get('name')} 监控异常: {e}")
            stats["failed"] += 1
            account_results.append({
                "account_id": account.get("id"),
                "account_name": account.get("name"),
                "status": "failed",
                "error": str(e),
            })

    # 3. 完成轮次
    overall_status = "success"
    if stats["failed"] == total:
        overall_status = "failed"
    elif stats["failed"] > 0:
        overall_status = "partial"

    finish_monitor_run(run_id, status=overall_status, stats=stats)

    # WebSocket: 推送"监控完成"
    _emit(emit_monitor_done(run_id, stats, overall_status))

    logger.info(f"{'=' * 60}")
    logger.info(
        f"监控轮次 {run_id} 完成: "
        f"扫描 {stats['total']}, 成功 {stats['crawled']}, "
        f"跳过 {stats['skipped']}, 失败 {stats['failed']}, "
        f"新视频 {stats['new_videos']}, 分析 {stats['analyzed']}, "
        f"消耗 {stats['total_tokens']} tokens"
    )

    return {
        "run_id": run_id,
        "status": overall_status,
        "stats": stats,
        "accounts": account_results,
    }


# ============================================================
# 辅助函数
# ============================================================
def _find_new_videos(account_id: str, videos: list[dict]) -> list[str]:
    """从爬取结果中找出数据库里不存在的新视频 ID

    Returns: 新视频的 platform_vid 列表
    """
    if not videos:
        return []

    sb = get_supabase()
    # 查询该账号已有的所有 platform_vid
    existing_res = (
        sb.table("videos")
        .select("platform_vid")
        .eq("account_id", account_id)
        .execute()
    )
    existing_vids = {v["platform_vid"] for v in existing_res.data}

    # 爬虫返回的 video_id 对应 DB 的 platform_vid
    new_ids = []
    for v in videos:
        vid = v.get("video_id") or v.get("id")
        if vid and vid not in existing_vids:
            new_ids.append(vid)

    return new_ids


def _analyze_new_videos(
    account_id: str,
    new_video_ids: list[str],
    videos: list[dict],
    model: str = "auto",
) -> dict:
    """对新增视频做 AI 爆款分析, 结果存入 ai_analysis 表

    Returns:
        dict: { analysis_id, analyzed, prompt_tokens, completion_tokens, status, error }
    """
    if not new_video_ids:
        return {"analyzed": 0, "status": "skipped"}

    from viral_service import analyze_viral
    from models_viral import VideoInput

    # 从爬取结果中筛出新增视频
    new_videos = []
    for v in videos:
        vid = v.get("video_id") or v.get("id")
        if vid in new_video_ids:
            new_videos.append(v)

    if not new_videos:
        return {"analyzed": 0, "status": "skipped"}

    # 转换为 VideoInput 格式
    video_inputs = []
    for v in new_videos[:20]:  # AI 上下文限制, 最多 20 条
        video_inputs.append(VideoInput(
            video_id=v.get("video_id") or v.get("id", ""),
            title=v.get("title", ""),
            like_count=v.get("likes", 0) or v.get("like_count", 0),
            comment_count=v.get("comments", 0) or v.get("comment_count", 0),
            share_count=v.get("shares", 0) or v.get("share_count", 0),
            view_count=v.get("views", 0) or v.get("view_count", 0),
            published_at=v.get("publish_time") or v.get("published_at"),
            video_url=v.get("video_url"),
            cover_url=v.get("cover_url"),
        ))

    # 调 AI 分析
    result = analyze_viral(videos=video_inputs, model=model)

    # 存入 ai_analysis 表
    sb = get_supabase()
    analysis_row = {
        "account_id": account_id,
        "video_id": None,  # 账号级分析, 不关联单条视频
        "analysis_type": "viral",
        "summary": result.overview,
        "result": {
            "overview": result.overview,
            "viral_reasons": [r.model_dump() for r in result.viral_reasons],
            "title_patterns": [p.model_dump() for p in result.title_patterns],
            "content_tactics": [t.model_dump() for t in result.content_tactics],
            "topic_suggestions": [t.model_dump() for t in result.topic_suggestions],
            "monitored_videos": [v.model_dump() for v in video_inputs],
        },
        "ai_provider": result.provider,
        "ai_model": result.model_used,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
    }
    res = sb.table("ai_analysis").insert(analysis_row).execute()
    analysis_id = res.data[0]["id"] if res.data else None

    return {
        "analysis_id": analysis_id,
        "analysis_type": "viral",
        "analyzed": len(video_inputs),
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "status": "success",
    }


# ============================================================
# 查询函数
# ============================================================
def list_monitor_runs(limit: int = 20) -> list[dict]:
    """查询监控轮次历史"""
    sb = get_supabase()
    res = (
        sb.table("monitor_runs")
        .select("*")
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


def get_monitor_run(run_id: str) -> Optional[dict]:
    """查询单轮监控详情 (含任务列表)"""
    sb = get_supabase()
    run_res = sb.table("monitor_runs").select("*").eq("id", run_id).execute()
    if not run_res.data:
        return None

    tasks_res = (
        sb.table("monitor_tasks")
        .select("*")
        .eq("run_id", run_id)
        .order("started_at", desc=False)
        .execute()
    )

    run_data = run_res.data[0]
    run_data["tasks"] = tasks_res.data
    return run_data


def get_account_monitor_history(account_id: str, limit: int = 20) -> list[dict]:
    """查询某账号的监控历史"""
    sb = get_supabase()
    res = (
        sb.table("monitor_tasks")
        .select("*")
        .eq("account_id", account_id)
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


def get_last_run_summary() -> Optional[dict]:
    """获取最近一次监控轮次摘要"""
    runs = list_monitor_runs(limit=1)
    return runs[0] if runs else None
