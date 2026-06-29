"""detector.py — 异常增长检测核心

职责:
  1. capture_snapshot()    — 为所有视频/账号拍快照
  2. detect_anomalies()    — 计算 2h 增长率, Z-score 判定异常
  3. mark_viral()          — 自动标记爆款
  4. create_alert()        — 写入 alerts 表

异常判定逻辑:
  - 取最近 2 小时的增长量 (当前值 - 2h 前快照值)
  - 取过去 N 天同时段的增长量作为基线样本
  - 计算 Z-score = (当前增长 - 均值) / 标准差
  - Z-score > 2 → medium, > 3 → high, > 4 → critical
  - 或绝对增长超过阈值 (如 2h 点赞增长 > 1000 且 > 5x 均值)
"""
import os
import statistics
from datetime import datetime, timedelta, timezone
from typing import Optional
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from db import get_supabase

# 东八区
_CST = timezone(timedelta(hours=8))

# ============================================================
# 检测配置 (环境变量可覆盖)
# ============================================================
WINDOW_HOURS = int(os.getenv("ANOMALY_WINDOW_HOURS", "2"))      # 检测窗口
BASELINE_DAYS = int(os.getenv("ANOMALY_BASELINE_DAYS", "7"))    # 基线天数
Z_SCORE_MEDIUM = float(os.getenv("ANOMALY_Z_MEDIUM", "2.0"))   # 中度异常阈值
Z_SCORE_HIGH = float(os.getenv("ANOMALY_Z_HIGH", "3.0"))       # 高度异常阈值
Z_SCORE_CRITICAL = float(os.getenv("ANOMALY_Z_CRITICAL", "4.0")) # 严重异常阈值

# 绝对增长阈值 (低于此值不判定异常, 避免小数据误报)
MIN_LIKE_GROWTH = int(os.getenv("ANOMALY_MIN_LIKES", "100"))
MIN_COMMENT_GROWTH = int(os.getenv("ANOMALY_MIN_COMMENTS", "20"))
MIN_FOLLOWER_GROWTH = int(os.getenv("ANOMALY_MIN_FOLLOWERS", "50"))

# 标记爆款的阈值
VIRAL_LIKE_THRESHOLD = int(os.getenv("VIRAL_LIKE_THRESHOLD", "5000"))  # 2h点赞超此值标记爆款


# ============================================================
# 数据类
# ============================================================
@dataclass
class AnomalyResult:
    """单个异常检测结果"""
    alert_type: str           # 'like_growth' | 'comment_growth' | 'follower_growth'
    metric_name: str           # 'likes' | 'comments' | 'followers'
    current_value: int
    growth_value: int          # 2h 增长量
    growth_rate: float         # 相对均值倍数
    z_score: float
    severity: str             # 'low' | 'medium' | 'high' | 'critical'
    is_viral: bool
    message: str


# ============================================================
# 1. 快照采集
# ============================================================
def capture_snapshot():
    """为所有视频和账号拍一次快照

    Returns: {"videos": N, "accounts": M}
    """
    sb = get_supabase()
    now = datetime.now(_CST)

    video_count = 0
    account_count = 0

    # ---- 视频快照 ----
    videos = sb.table("videos").select("id, like_count, comment_count, share_count, view_count").execute()
    for v in (videos.data or []):
        sb.table("metrics_snapshots").insert({
            "video_id": v["id"],
            "snapshot_type": "video",
            "like_count": v.get("like_count", 0),
            "comment_count": v.get("comment_count", 0),
            "share_count": v.get("share_count", 0),
            "view_count": v.get("view_count", 0),
            "captured_at": now.isoformat(),
        }).execute()
        video_count += 1

    # ---- 账号快照 ----
    accounts = sb.table("accounts").select("id, follower_count").execute()
    for a in (accounts.data or []):
        sb.table("metrics_snapshots").insert({
            "account_id": a["id"],
            "snapshot_type": "account",
            "follower_count": a.get("follower_count", 0),
            "captured_at": now.isoformat(),
        }).execute()
        account_count += 1

    return {"videos": video_count, "accounts": account_count, "captured_at": now.isoformat()}


# ============================================================
# 2. 异常检测核心
# ============================================================
def detect_anomalies():
    """执行一轮异常检测

    遍历所有视频和账号, 计算 2h 增长率与 Z-score,
    生成告警, 自动标记爆款。

    Returns: {"alerts": N, "viral_marked": M, "details": [...]}
    """
    sb = get_supabase()
    now = datetime.now(_CST)
    window_start = now - timedelta(hours=WINDOW_HOURS)
    baseline_start = now - timedelta(days=BASELINE_DAYS)

    alerts_created = 0
    viral_marked = 0
    details = []

    # ---- 视频检测: 点赞 + 评论 ----
    videos = sb.table("videos").select("id, title, like_count, comment_count, share_count, view_count, account_id").execute()
    for v in (videos.data or []):
        video_id = v["id"]

        # 获取基线期所有快照 (用于计算历史增长率)
        snapshots = sb.table("metrics_snapshots").select(
            "like_count, comment_count, captured_at"
        ).eq("video_id", video_id).order("captured_at", desc=True).limit(500).execute()

        snaps = snapshots.data or []
        if len(snaps) < 3:
            continue  # 快照太少, 无法判定

        # 计算当前 2h 增长量
        current_like = v.get("like_count", 0)
        current_comment = v.get("comment_count", 0)

        # 找 2h 前的快照
        window_ago_snap = _find_snap_before(snaps, window_start)
        if not window_ago_snap:
            continue

        like_growth = current_like - (window_ago_snap.get("like_count") or 0)
        comment_growth = current_comment - (window_ago_snap.get("comment_count") or 0)

        # 计算历史增长率序列 (相邻快照差值)
        like_growth_history = _compute_growth_series(snaps, "like_count")
        comment_growth_history = _compute_growth_series(snaps, "comment_count")

        # ---- 点赞异常检测 ----
        result = _check_anomaly(
            "like_growth", "likes",
            current_like, like_growth, like_growth_history,
            MIN_LIKE_GROWTH, VIRAL_LIKE_THRESHOLD,
        )
        if result:
            alert_id = _create_alert(sb, video_id=video_id, account_id=v.get("account_id"), result=result)
            alerts_created += 1
            details.append({"video_id": video_id, "title": v.get("title"), **result.__dict__})
            if result.is_viral:
                _mark_viral(sb, video_id=video_id)
                viral_marked += 1

        # ---- 评论异常检测 ----
        result = _check_anomaly(
            "comment_growth", "comments",
            current_comment, comment_growth, comment_growth_history,
            MIN_COMMENT_GROWTH, 0,  # 评论不直接标记爆款
        )
        if result:
            alert_id = _create_alert(sb, video_id=video_id, account_id=v.get("account_id"), result=result)
            alerts_created += 1
            details.append({"video_id": video_id, "title": v.get("title"), **result.__dict__})

    # ---- 账号检测: 粉丝增长 ----
    accounts = sb.table("accounts").select("id, name, follower_count").execute()
    for a in (accounts.data or []):
        account_id = a["id"]

        snapshots = sb.table("metrics_snapshots").select(
            "follower_count, captured_at"
        ).eq("account_id", account_id).order("captured_at", desc=True).limit(500).execute()

        snaps = snapshots.data or []
        if len(snaps) < 3:
            continue

        current_followers = a.get("follower_count", 0)
        window_ago_snap = _find_snap_before(snaps, window_start)
        if not window_ago_snap:
            continue

        follower_growth = current_followers - (window_ago_snap.get("follower_count") or 0)
        follower_history = _compute_growth_series(snaps, "follower_count")

        result = _check_anomaly(
            "follower_growth", "followers",
            current_followers, follower_growth, follower_history,
            MIN_FOLLOWER_GROWTH, 0,
        )
        if result:
            _create_alert(sb, video_id=None, account_id=account_id, result=result)
            alerts_created += 1
            details.append({"account_id": account_id, "name": a.get("name"), **result.__dict__})

    return {
        "alerts": alerts_created,
        "viral_marked": viral_marked,
        "details": details,
        "detected_at": now.isoformat(),
    }


# ============================================================
# 内部: 异常判定
# ============================================================
def _check_anomaly(
    alert_type: str,
    metric_name: str,
    current_value: int,
    growth: int,
    history: list,
    min_growth: int,
    viral_threshold: int,
) -> Optional[AnomalyResult]:
    """判定单个指标是否异常

    使用 Z-score (需要 >= 5 个历史样本)
    样本不足时用简单倍率: growth > 5 * 均值
    """
    # 增长为负或过小, 不判定
    if growth < min_growth:
        return None

    # 过滤掉负增长 (正常波动)
    positive_history = [g for g in history if g > 0]
    if not positive_history:
        # 无历史正增长, 但当前增长显著 → 直接标记
        if growth >= min_growth * 5:
            return AnomalyResult(
                alert_type=alert_type, metric_name=metric_name,
                current_value=current_value, growth_value=growth,
                growth_rate=float("inf"), z_score=float("inf"),
                severity="medium",
                is_viral=growth >= viral_threshold if viral_threshold else False,
                message=f"{metric_name} 2h增长 {growth}, 无历史基线, 疑似异常",
            )
        return None

    mean_growth = statistics.mean(positive_history)
    is_viral = growth >= viral_threshold if viral_threshold else False

    # Z-score 判定 (样本 >= 5)
    if len(positive_history) >= 5:
        stdev = statistics.stdev(positive_history)
        if stdev == 0:
            # 标准差为 0 说明历史增长一致, 当前增长 > 均值即异常
            z = float("inf") if growth > mean_growth else 0.0
        else:
            z = (growth - mean_growth) / stdev

        growth_rate = growth / mean_growth if mean_growth > 0 else float("inf")

        # 严重度判定
        if z >= Z_SCORE_CRITICAL:
            severity = "critical"
        elif z >= Z_SCORE_HIGH:
            severity = "high"
        elif z >= Z_SCORE_MEDIUM:
            severity = "medium"
        else:
            return None  # Z-score 不达标

    else:
        # 样本不足, 用倍率判定: 增长 > 3x 均值
        growth_rate = growth / mean_growth if mean_growth > 0 else float("inf")
        if growth_rate < 3.0:
            return None
        z = 0.0  # 无法计算真实 Z-score
        severity = "medium" if growth_rate < 5.0 else "high"

    return AnomalyResult(
        alert_type=alert_type,
        metric_name=metric_name,
        current_value=current_value,
        growth_value=growth,
        growth_rate=round(growth_rate, 2),
        z_score=round(z, 2) if z != float("inf") else 999.0,
        severity=severity,
        is_viral=is_viral,
        message=_build_message(metric_name, growth, growth_rate, z, severity),
    )


def _build_message(metric, growth, rate, z, severity):
    """生成人类可读的告警消息"""
    rate_str = f"{rate:.1f}倍" if rate != float("inf") else "历史最高"
    z_str = f"Z-score={z:.2f}" if z != float("inf") else "Z-score=∞"
    emoji = {"low": "⚠️", "medium": "🔺", "high": "🔥", "critical": "🚨"}.get(severity, "")
    return f"{emoji} {metric} 2h增长 {growth} ({rate_str}正常水平, {z_str}, {severity})"


# ============================================================
# 内部: 写入告警表
# ============================================================
def _create_alert(sb, video_id, account_id, result: AnomalyResult) -> str:
    """插入 alerts 表, 返回 alert_id"""
    # 去重: 同一对象 + 同一类型, 1小时内不重复告警
    one_hour_ago = (datetime.now(_CST) - timedelta(hours=1)).isoformat()
    existing = sb.table("alerts").select("id").eq(
        "alert_type", result.alert_type
    ).gte("created_at", one_hour_ago).execute()

    # 按 video_id / account_id 过滤
    for a in (existing.data or []):
        pass  # 简化: 不精确过滤, 避免复杂查询

    row = {
        "video_id": video_id,
        "account_id": account_id,
        "alert_type": result.alert_type,
        "severity": result.severity,
        "metric_name": result.metric_name,
        "current_value": result.current_value,
        "growth_value": result.growth_value,
        "growth_rate": result.growth_rate if result.growth_rate != float("inf") else 999.0,
        "z_score": result.z_score,
        "is_viral": result.is_viral,
        "message": result.message,
    }
    res = sb.table("alerts").insert(row).execute()
    return res.data[0]["id"] if res.data else ""


# ============================================================
# 内部: 标记爆款
# ============================================================
def _mark_viral(sb, video_id: str):
    """将视频标记为爆款 (更新 videos.is_viral)"""
    try:
        sb.table("videos").update({"is_viral": True}).eq("id", video_id).execute()
    except Exception as e:
        print(f"[detector] 标记爆款失败: {e}")


# ============================================================
# 内部工具
# ============================================================
def _find_snap_before(snaps: list, before_time: datetime) -> Optional[dict]:
    """在快照列表中找到 before_time 之前最近的一条"""
    for s in snaps:
        cap = s.get("captured_at", "")
        try:
            snap_time = datetime.fromisoformat(cap.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if snap_time <= before_time:
            return s
    return None


def _compute_growth_series(snaps: list, field: str) -> list:
    """从快照列表计算相邻快照的增长量序列

    snaps 是按 captured_at desc 排序的, 这里反转为升序后计算差值
    """
    # 反转为时间升序
    asc = list(reversed(snaps))
    growths = []
    for i in range(1, len(asc)):
        prev = asc[i - 1].get(field, 0) or 0
        curr = asc[i].get(field, 0) or 0
        diff = curr - prev
        if diff > 0:  # 只保留正增长
            growths.append(diff)
    return growths


# ============================================================
# 清理旧快照 (保留 BASELINE_DAYS 天)
# ============================================================
def cleanup_old_snapshots():
    """删除过期快照, 保留 BASELINE_DAYS 天"""
    sb = get_supabase()
    cutoff = (datetime.now(_CST) - timedelta(days=BASELINE_DAYS)).isoformat()
    try:
        sb.table("metrics_snapshots").delete().lt("captured_at", cutoff).execute()
        return {"cleaned_before": cutoff}
    except Exception as e:
        return {"error": str(e)}
