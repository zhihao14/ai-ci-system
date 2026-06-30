"""engines.py — Advanced Intelligence Engines

1. Competitor Score Engine      — multi-dimensional scoring (0-100)
2. Executive Summary Engine     — AI-generated concise briefing
3. Competitive Threat Detection — rule-based + AI threat analysis
4. Auto Counter Strategy Engine — AI-generated counter-strategy recommendations

All engines read from video_analyses + related tables.
Pure-Python scoring; AI used only for narrative generation (~10s each).
"""
import json
import httpx
from datetime import datetime
from collections import Counter

from db_intelligence import (
    get_video_analysis, get_content_pattern, get_trend_prediction,
    get_growth_strategy, list_video_analyses,
)
from intelligence_service import _compute_aggregate_analysis


# ============================================================
# 1. Competitor Score Engine
# ============================================================

def calculate_competitor_score(video_analysis_id: str) -> dict:
    """Calculate a composite competitor score (0-100) across 5 dimensions.

    Dimensions:
    - Reach:        follower count + video count
    - Engagement:   avg likes + comments + shares per video
    - Consistency:  posting frequency regularity
    - Virality:     share-to-like ratio + peak video performance
    - ContentDepth: content type diversity + keyword richness

    Returns: { overall_score, dimensions: {reach, engagement, consistency, virality, content_depth},
              grade, benchmarks, analysis_id, account_name }
    """
    va = get_video_analysis(video_analysis_id)
    if not va:
        raise ValueError(f"Analysis not found: {video_analysis_id}")

    videos = va.get("videos") or []
    account_fields = va.get("account_fields") or {}
    account_name = va.get("account_name") or "Unknown"

    if not videos:
        return _empty_score(video_analysis_id, account_name)

    # --- 1. Reach Score (0-100) ---
    follower_count = account_fields.get("follower_count") or 0
    video_count = len(videos)
    # Log scale: 10K followers = 40, 100K = 70, 1M = 90, 10M = 100
    import math
    if follower_count > 0:
        reach_score = min(100, 30 + 15 * math.log10(follower_count / 1000))
    else:
        reach_score = 20
    reach_score = max(10, reach_score)

    # --- 2. Engagement Score (0-100) ---
    total_likes = sum(v.get("digg_count") or 0 for v in videos)
    total_comments = sum(v.get("comment_count") or 0 for v in videos)
    total_shares = sum(v.get("share_count") or 0 for v in videos)
    total_engagement = total_likes + total_comments + total_shares
    avg_engagement = total_engagement / max(video_count, 1)
    # 100 avg = 40, 500 avg = 60, 2000 avg = 80, 10000+ = 100
    if avg_engagement > 0:
        engagement_score = min(100, 30 + 17 * math.log10(avg_engagement))
    else:
        engagement_score = 10
    engagement_score = max(10, engagement_score)

    # --- 3. Consistency Score (0-100) ---
    # Based on posting time regularity
    hour_counts = Counter()
    weekday_counts = Counter()
    for v in videos:
        ts = v.get("create_time_str") or v.get("create_time")
        if ts:
            try:
                if isinstance(ts, (int, float)):
                    dt = datetime.fromtimestamp(ts)
                else:
                    ts_str = str(ts).replace("Z", "+00:00")
                    dt = datetime.fromisoformat(ts_str)
                hour_counts[dt.hour] += 1
                weekday_counts[dt.weekday()] += 1
            except Exception:
                pass

    if hour_counts:
        # Lower variance = more consistent = higher score
        hours_with_posts = len(hour_counts)
        # If all videos posted in 1-2 hours: consistent but not diverse
        # If spread across many hours: less consistent
        consistency_raw = min(100, 100 - hours_with_posts * 8)
        consistency_score = max(20, consistency_raw)
    else:
        consistency_score = 40  # Default when no timestamps

    # --- 4. Virality Score (0-100) ---
    # Share-to-like ratio + peak video performance
    if total_likes > 0:
        share_ratio = total_shares / total_likes
    else:
        share_ratio = 0
    # ratio > 0.5 = high virality, > 1.0 = very viral
    virality_from_ratio = min(50, share_ratio * 100)

    # Peak video: how much above average is the top video?
    sorted_by_eng = sorted(
        videos,
        key=lambda v: (v.get("digg_count") or 0) + (v.get("comment_count") or 0) + (v.get("share_count") or 0),
        reverse=True,
    )
    if sorted_by_eng and avg_engagement > 0:
        top_engagement = (
            (sorted_by_eng[0].get("digg_count") or 0)
            + (sorted_by_eng[0].get("comment_count") or 0)
            + (sorted_by_eng[0].get("share_count") or 0)
        )
        peak_multiplier = top_engagement / avg_engagement
        virality_from_peak = min(50, peak_multiplier * 10)
    else:
        virality_from_peak = 20

    virality_score = min(100, virality_from_ratio + virality_from_peak)
    virality_score = max(10, virality_score)

    # --- 5. Content Depth Score (0-100) ---
    # Content type diversity + keyword richness
    stats = _compute_aggregate_analysis(videos, account_fields)
    content_types = stats.get("top_content_types", [])
    keywords = stats.get("high_frequency_keywords", [])
    type_diversity = min(40, len(content_types) * 10)
    keyword_richness = min(40, len(keywords) * 5)
    content_depth_score = min(100, 20 + type_diversity + keyword_richness)
    content_depth_score = max(10, content_depth_score)

    # --- Overall Score (weighted) ---
    overall = round(
        reach_score * 0.15
        + engagement_score * 0.25
        + consistency_score * 0.15
        + virality_score * 0.25
        + content_depth_score * 0.20
    )

    grade = _score_to_grade(overall)

    return {
        "analysis_id": video_analysis_id,
        "account_name": account_name,
        "overall_score": overall,
        "grade": grade,
        "dimensions": {
            "reach": round(reach_score),
            "engagement": round(engagement_score),
            "consistency": round(consistency_score),
            "virality": round(virality_score),
            "content_depth": round(content_depth_score),
        },
        "raw_metrics": {
            "follower_count": follower_count,
            "video_count": video_count,
            "total_likes": total_likes,
            "total_comments": total_comments,
            "total_shares": total_shares,
            "avg_engagement": round(avg_engagement, 1),
            "share_to_like_ratio": round(share_ratio, 3),
            "content_type_count": len(content_types),
            "keyword_count": len(keywords),
        },
        "benchmarks": {
            "engagement_vs_avg": round(avg_engagement / 500, 2),  # 500 = typical baseline
            "virality_vs_avg": round(share_ratio / 0.3, 2),  # 0.3 = typical share ratio
        },
    }


def _score_to_grade(score: int) -> str:
    if score >= 85: return "S"
    if score >= 70: return "A"
    if score >= 55: return "B"
    if score >= 40: return "C"
    return "D"


def _empty_score(analysis_id: str, account_name: str) -> dict:
    return {
        "analysis_id": analysis_id,
        "account_name": account_name,
        "overall_score": 0,
        "grade": "N/A",
        "dimensions": {"reach": 0, "engagement": 0, "consistency": 0, "virality": 0, "content_depth": 0},
        "raw_metrics": {},
        "benchmarks": {},
    }


# ============================================================
# 2. Executive Summary Engine
# ============================================================

def generate_executive_summary(video_analysis_id: str) -> dict:
    """AI generates a concise executive summary (2-3 sentences) from all analysis data.

    Reads: patterns + analysis + trends + strategy
    AI: generates executive briefing with key metrics
    ~10s
    """
    va = get_video_analysis(video_analysis_id)
    if not va:
        raise ValueError(f"Analysis not found: {video_analysis_id}")

    # Gather all available data
    patterns = get_content_pattern(video_analysis_id)
    trends = get_trend_prediction(video_analysis_id)
    strategy = get_growth_strategy(video_analysis_id)
    analysis = va.get("analysis") or {}

    account_name = va.get("account_name") or "Unknown"
    account_fields = va.get("account_fields") or {}
    videos = va.get("videos") or []
    follower_count = account_fields.get("follower_count") or 0

    # Pre-compute stats for summary
    total_likes = sum(v.get("digg_count") or 0 for v in videos)
    total_comments = sum(v.get("comment_count") or 0 for v in videos)
    total_shares = sum(v.get("share_count") or 0 for v in videos)
    avg_engagement = (total_likes + total_comments + total_shares) / max(len(videos), 1)

    # Score
    score_data = calculate_competitor_score(video_analysis_id)

    # Build compact data brief
    brief = {
        "account": account_name,
        "followers": follower_count,
        "video_count": len(videos),
        "total_likes": total_likes,
        "total_shares": total_shares,
        "avg_engagement": round(avg_engagement, 1),
        "competitor_score": score_data["overall_score"],
        "grade": score_data["grade"],
        "top_dimensions": sorted(score_data["dimensions"].items(), key=lambda x: x[1], reverse=True)[:2],
        "analysis_keys": list(analysis.keys()) if analysis else [],
        "trend_direction": (trends.get("predictions") or {}).get("engagement_forecast", {}).get("trend_direction") if trends else None,
        "growth_momentum": (trends.get("predictions") or {}).get("growth_trajectory", {}).get("current_momentum") if trends else None,
        "strategy_actions": len((strategy.get("strategy") or {}).get("short_term_actions", [])) if strategy else 0,
    }

    # AI generates executive summary
    from ai_service import _get_configs, _parse_json

    configs = _get_configs()
    if not configs:
        return {
            "analysis_id": video_analysis_id,
            "account_name": account_name,
            "summary": _fallback_summary(brief),
            "score": score_data["overall_score"],
            "grade": score_data["grade"],
            "ai_provider": "none",
        }

    brief_json = json.dumps(brief, ensure_ascii=False, indent=2)

    prompt = f"""You are a competitive intelligence analyst. Write an executive summary for this competitor.

Data brief:
{brief_json}

Write a concise executive summary (3-4 sentences, max 200 words). Cover:
1. Who they are and their market position
2. Key strength (highest scoring dimension)
3. Key threat or weakness (lowest scoring dimension)
4. Strategic recommendation in one sentence

Also extract 3 key metrics as bullet points.

Output as JSON:
{{"headline": "one-line headline (max 80 chars)", "summary": "3-4 sentence executive summary", "key_metrics": ["metric 1", "metric 2", "metric 3"], "recommendation": "one sentence strategic recommendation"}}
"""

    for cfg in configs:
        provider = cfg["provider"]
        try:
            if provider == "claude":
                from anthropic import Anthropic
                ac = Anthropic(api_key=cfg["api_key"])
                msg = ac.messages.create(
                    model=cfg["model"], max_tokens=1000,
                    system="You are a competitive intelligence analyst. Output only JSON.",
                    messages=[{"role": "user", "content": prompt}],
                )
                text = msg.content[0].text
            else:
                base_url = cfg["base_url"]
                url = f"{base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": "You are a competitive intelligence analyst. Output only JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                }
                with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                text = data["choices"][0]["message"]["content"]

            result = _parse_json(text)
            result["score"] = score_data["overall_score"]
            result["grade"] = score_data["grade"]
            result["dimensions"] = score_data["dimensions"]
            result["analysis_id"] = video_analysis_id
            result["account_name"] = account_name
            result["ai_provider"] = provider
            return result
        except Exception as e:
            print(f"[ExecSummary] {cfg['label']} failed: {e}")
            continue

    return {
        "analysis_id": video_analysis_id,
        "account_name": account_name,
        "summary": _fallback_summary(brief),
        "score": score_data["overall_score"],
        "grade": score_data["grade"],
        "dimensions": score_data["dimensions"],
        "ai_provider": "none",
    }


def _fallback_summary(brief: dict) -> str:
    return (
        f"{brief['account']} has {brief['followers']} followers across {brief['video_count']} videos. "
        f"Average engagement: {brief['avg_engagement']}. "
        f"Competitor score: {brief['competitor_score']}/100 (Grade: {brief['grade']})."
    )


# ============================================================
# 3. Competitive Threat Detection
# ============================================================

def detect_threats(video_analysis_id: str) -> dict:
    """Detect competitive threats from analysis data.

    Rule-based detection:
    - Content gap: competitor posts content types we don't
    - Engagement spike: unusually high engagement on specific videos
    - Growth acceleration: high follower-to-video ratio
    - Share dominance: high share-to-like ratio (viral threat)
    - Content frequency: high posting frequency

    Returns: { threats: [...], threat_level, analysis_id, account_name }
    """
    va = get_video_analysis(video_analysis_id)
    if not va:
        raise ValueError(f"Analysis not found: {video_analysis_id}")

    videos = va.get("videos") or []
    account_fields = va.get("account_fields") or {}
    account_name = va.get("account_name") or "Unknown"

    threats = []
    score_data = calculate_competitor_score(video_analysis_id)

    total_likes = sum(v.get("digg_count") or 0 for v in videos)
    total_shares = sum(v.get("share_count") or 0 for v in videos)
    total_comments = sum(v.get("comment_count") or 0 for v in videos)
    avg_engagement = (total_likes + total_comments + total_shares) / max(len(videos), 1)

    # Threat 1: Viral Content (share-to-like ratio > 0.5)
    if total_likes > 0:
        share_ratio = total_shares / total_likes
        if share_ratio > 0.5:
            threats.append({
                "type": "viral_content",
                "severity": "high" if share_ratio > 1.0 else "medium",
                "title": f"Viral Share Dominance",
                "description": f"Share-to-like ratio of {share_ratio:.2f} indicates content is being heavily shared, creating viral reach beyond their follower base.",
                "evidence": f"total_shares={total_shares}, total_likes={total_likes}",
                "confidence_score": 0.9,
                "impact": "high",
            })

    # Threat 2: Engagement Spike (top video > 3x average)
    sorted_videos = sorted(
        videos,
        key=lambda v: (v.get("digg_count") or 0) + (v.get("comment_count") or 0) + (v.get("share_count") or 0),
        reverse=True,
    )
    if sorted_videos and avg_engagement > 0:
        top_engagement = (
            (sorted_videos[0].get("digg_count") or 0)
            + (sorted_videos[0].get("comment_count") or 0)
            + (sorted_videos[0].get("share_count") or 0)
        )
        spike_ratio = top_engagement / avg_engagement
        if spike_ratio > 3:
            threats.append({
                "type": "engagement_spike",
                "severity": "high" if spike_ratio > 5 else "medium",
                "title": f"Engagement Spike ({spike_ratio:.1f}x average)",
                "description": f"Top video has {top_engagement} total engagement, {spike_ratio:.1f}x the account average. This content type may be replicable.",
                "evidence": f"top_video_engagement={top_engagement}, avg={avg_engagement:.0f}",
                "confidence_score": 0.85,
                "impact": "high",
            })

    # Threat 3: High Posting Frequency (> 10 videos in dataset)
    if len(videos) >= 20:
        threats.append({
            "type": "content_velocity",
            "severity": "medium",
            "title": f"High Content Velocity ({len(videos)} videos)",
            "description": f"Account maintains high posting frequency with {len(videos)} recent videos, indicating aggressive content production pipeline.",
            "evidence": f"video_count={len(videos)}",
            "confidence_score": 0.8,
            "impact": "medium",
        })

    # Threat 4: Follower-to-Video Ratio (high engagement efficiency)
    follower_count = account_fields.get("follower_count") or 0
    if follower_count > 0 and len(videos) > 0:
        efficiency = avg_engagement / (follower_count / 10000)  # engagement per 10K followers
        if efficiency > 500:
            threats.append({
                "type": "engagement_efficiency",
                "severity": "high" if efficiency > 1000 else "medium",
                "title": f"High Engagement Efficiency ({efficiency:.0f}/10K followers)",
                "description": f"Average engagement of {avg_engagement:.0f} with {follower_count} followers shows exceptionally efficient content.",
                "evidence": f"avg_engagement={avg_engagement:.0f}, followers={follower_count}",
                "confidence_score": 0.75,
                "impact": "high",
            })

    # Threat 5: Low consistency (opportunistic content)
    consistency = score_data["dimensions"]["consistency"]
    if consistency > 70:
        threats.append({
            "type": "consistent_threat",
            "severity": "medium",
            "title": f"Consistent Posting Strategy",
            "description": f"Posting at consistent times (score: {consistency}/100) indicates disciplined content calendar that competitors may struggle to match.",
            "evidence": f"consistency_score={consistency}",
            "confidence_score": 0.7,
            "impact": "medium",
        })

    # Determine overall threat level
    high_count = sum(1 for t in threats if t["severity"] == "high")
    medium_count = sum(1 for t in threats if t["severity"] == "medium")
    if high_count >= 2:
        threat_level = "critical"
    elif high_count >= 1:
        threat_level = "high"
    elif medium_count >= 2:
        threat_level = "moderate"
    elif medium_count >= 1:
        threat_level = "low"
    else:
        threat_level = "minimal"

    return {
        "analysis_id": video_analysis_id,
        "account_name": account_name,
        "threat_level": threat_level,
        "threat_count": len(threats),
        "threats": threats,
        "score": score_data["overall_score"],
        "grade": score_data["grade"],
    }


# ============================================================
# 4. Auto Counter Strategy Engine
# ============================================================

def generate_counter_strategy(video_analysis_id: str) -> dict:
    """AI generates counter-strategy recommendations based on detected threats.

    Reads: competitor score + threats + analysis data
    AI: generates attack strategies to counter specific threats
    ~10s
    """
    va = get_video_analysis(video_analysis_id)
    if not va:
        raise ValueError(f"Analysis not found: {video_analysis_id}")

    account_name = va.get("account_name") or "Unknown"

    # Get score and threats
    score_data = calculate_competitor_score(video_analysis_id)
    threat_data = detect_threats(video_analysis_id)

    # Get existing strategy if any
    existing_strategy = get_growth_strategy(video_analysis_id)
    existing = (existing_strategy.get("strategy") or {}) if existing_strategy else {}

    # Build compact brief for AI
    brief = {
        "competitor": account_name,
        "score": score_data["overall_score"],
        "grade": score_data["grade"],
        "dimensions": score_data["dimensions"],
        "weak_dimensions": sorted(score_data["dimensions"].items(), key=lambda x: x[1])[:2],
        "threats": [
            {"type": t["type"], "title": t["title"], "severity": t["severity"], "description": t["description"]}
            for t in threat_data["threats"]
        ],
        "threat_level": threat_data["threat_level"],
        "existing_strategy": {
            "short_term_actions": existing.get("short_term_actions", [])[:2],
            "mid_term_strategy": existing.get("mid_term_strategy", [])[:2],
        } if existing else None,
    }

    from ai_service import _get_configs, _parse_json

    configs = _get_configs()
    if not configs:
        return {
            "analysis_id": video_analysis_id,
            "account_name": account_name,
            "counter_strategies": [],
            "ai_provider": "none",
        }

    brief_json = json.dumps(brief, ensure_ascii=False, indent=2)

    prompt = f"""You are a competitive strategy advisor. Generate counter-strategies to beat this competitor.

Competitor intelligence brief:
{brief_json}

Generate 3-4 counter-strategies that attack their weak dimensions and neutralize their threats.
Each strategy must include specific, actionable tactics.

Output as JSON:
{{
  "counter_strategies": [
    {{
      "tactic": "short tactic name",
      "target_weakness": "which dimension/threat to exploit",
      "action_plan": "2-3 sentence action plan",
      "timeline": "immediate|1_month|3_months",
      "expected_impact": "what outcome to expect",
      "priority": "high|medium|low",
      "confidence_score": 0.8
    }}
  ],
  "overall_approach": "1 sentence summary of the counter-strategy approach"
}}
"""

    for cfg in configs:
        provider = cfg["provider"]
        try:
            if provider == "claude":
                from anthropic import Anthropic
                ac = Anthropic(api_key=cfg["api_key"])
                msg = ac.messages.create(
                    model=cfg["model"], max_tokens=2000,
                    system="You are a competitive strategy advisor. Output only JSON.",
                    messages=[{"role": "user", "content": prompt}],
                )
                text = msg.content[0].text
            else:
                base_url = cfg["base_url"]
                url = f"{base_url}/chat/completions"
                headers = {"Authorization": f"Bearer {cfg['api_key']}", "Content-Type": "application/json"}
                payload = {
                    "model": cfg["model"],
                    "messages": [
                        {"role": "system", "content": "You are a competitive strategy advisor. Output only JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                }
                with httpx.Client(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                    resp = client.post(url, headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                text = data["choices"][0]["message"]["content"]

            result = _parse_json(text)
            result["analysis_id"] = video_analysis_id
            result["account_name"] = account_name
            result["competitor_score"] = score_data["overall_score"]
            result["threat_level"] = threat_data["threat_level"]
            result["ai_provider"] = provider
            return result
        except Exception as e:
            print(f"[CounterStrategy] {cfg['label']} failed: {e}")
            continue

    return {
        "analysis_id": video_analysis_id,
        "account_name": account_name,
        "counter_strategies": [],
        "overall_approach": "AI analysis unavailable",
        "ai_provider": "none",
    }
