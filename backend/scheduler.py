"""scheduler.py — 后台定时任务调度

使用 APScheduler 调度 3 个定时任务:
  1. 快照采集  — 每 30 分钟拍一次快照 (metrics_snapshots)
  2. 异常检测  — 每 1 小时执行一次检测 (detector.detect_anomalies)
  3. 通知发送  — 每次检测后自动触发 (notifier.process_pending_alerts)
  4. 清理旧数据 — 每天凌晨清理 7 天前快照

也可作为独立脚本运行: python scheduler.py
"""
import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta

# 添加 backend 目录到 path (当作为独立脚本运行时)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")

from detector import capture_snapshot, detect_anomalies, cleanup_old_snapshots
from notifier import process_pending_alerts

_CST = timezone(timedelta(hours=8))

# ============================================================
# 定时任务函数
# ============================================================
def job_capture_snapshot():
    """任务 1: 拍快照"""
    logger.info("▶ 开始采集快照...")
    try:
        result = capture_snapshot()
        logger.info(f"✓ 快照完成: {result['videos']} 条视频, {result['accounts']} 个账号")
        return result
    except Exception as e:
        logger.error(f"✗ 快照采集失败: {e}")
        return {"error": str(e)}


def job_detect_anomalies():
    """任务 2: 异常检测"""
    logger.info("▶ 开始异常检测...")
    try:
        result = detect_anomalies()
        logger.info(
            f"✓ 检测完成: {result['alerts']} 条告警, "
            f"{result['viral_marked']} 个标记爆款"
        )
        # 检测完立即触发通知
        if result["alerts"] > 0:
            notif_result = process_pending_alerts()
            logger.info(
                f"  → 通知发送: {notif_result['sent']} 成功, "
                f"{notif_result['failed']} 失败"
            )
        return result
    except Exception as e:
        logger.error(f"✗ 异常检测失败: {e}")
        return {"error": str(e)}


def job_cleanup():
    """任务 3: 清理旧快照"""
    logger.info("▶ 开始清理旧快照...")
    try:
        result = cleanup_old_snapshots()
        logger.info(f"✓ 清理完成: {result}")
        return result
    except Exception as e:
        logger.error(f"✗ 清理失败: {e}")
        return {"error": str(e)}


# ============================================================
# 完整流程 (手动触发时用)
# ============================================================
def run_full_cycle():
    """执行完整一轮: 快照 → 检测 → 通知"""
    logger.info("=" * 50)
    logger.info("开始完整检测周期")
    snap = job_capture_snapshot()
    detect = job_detect_anomalies()
    logger.info("=" * 50)
    return {"snapshot": snap, "detection": detect}


# ============================================================
# APScheduler 调度器
# ============================================================
def start_scheduler():
    """启动 APScheduler 定时调度"""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        logger.error("未安装 apscheduler, 请运行: pip install apscheduler")
        logger.info("回退到简单循环模式 (使用 time.sleep)")
        return _start_simple_loop()

    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")

    # 任务 1: 快照采集 — 每 30 分钟
    scheduler.add_job(
        job_capture_snapshot,
        trigger=IntervalTrigger(minutes=30),
        id="snapshot",
        name="指标快照采集",
        max_instances=1,
        coalesce=True,
    )

    # 任务 2: 异常检测 — 每 1 小时 (快照后 5 分钟执行, 确保有新数据)
    scheduler.add_job(
        job_detect_anomalies,
        trigger=IntervalTrigger(minutes=60),
        id="detect",
        name="异常增长检测",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(_CST) + timedelta(seconds=10),  # 启动 10s 后先跑一次
    )

    # 任务 3: 清理旧快照 — 每天凌晨 3 点
    scheduler.add_job(
        job_cleanup,
        trigger=CronTrigger(hour=3, minute=0),
        id="cleanup",
        name="清理旧快照",
    )

    scheduler.start()
    logger.info("✓ APScheduler 已启动, 任务列表:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.id}: {job.name} → 下次执行 {job.next_run_time}")

    return scheduler


def _start_simple_loop():
    """无 APScheduler 时的回退方案: 简单循环"""
    import threading

    def loop():
        SNAPSHOT_INTERVAL = 30 * 60   # 30 分钟
        DETECT_INTERVAL = 60 * 60    # 60 分钟
        last_snapshot = 0
        last_detect = 0

        logger.info("启动简单循环调度器 (无 APScheduler)")

        while True:
            now = time.time()
            if now - last_snapshot >= SNAPSHOT_INTERVAL:
                job_capture_snapshot()
                last_snapshot = now

            if now - last_detect >= DETECT_INTERVAL:
                job_detect_anomalies()
                last_detect = now

            time.sleep(60)  # 每分钟检查一次

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread


# ============================================================
# 独立运行入口
# ============================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="异常检测定时调度器")
    parser.add_argument("--run-once", action="store_true", help="立即执行一轮完整流程然后退出")
    parser.add_argument("--snapshot-only", action="store_true", help="仅拍快照")
    parser.add_argument("--detect-only", action="store_true", help="仅检测")
    args = parser.parse_args()

    if args.run_once:
        run_full_cycle()
    elif args.snapshot_only:
        job_capture_snapshot()
    elif args.detect_only:
        job_detect_anomalies()
    else:
        # 启动持续调度
        scheduler = start_scheduler()
        logger.info("调度器运行中, 按 Ctrl+C 停止...")
        try:
            while True:
                time.sleep(1)
        except (KeyboardInterrupt, SystemExit):
            logger.info("调度器停止")
            if hasattr(scheduler, "shutdown"):
                scheduler.shutdown()
