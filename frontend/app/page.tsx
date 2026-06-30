"use client";

// page.tsx — Realtime Intelligence Dashboard
// Premium Enterprise SaaS UI with:
// - Competitor Score Engine (radar chart + gauge)
// - Executive Summary Engine
// - Competitive Threat Detection
// - Auto Counter Strategy Engine
// - Visual Analytics (less text, more signal)

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useI18n } from "@/lib/i18n";
import {
  RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  AreaChart, Area, Cell,
} from "recharts";

// ---- Types ----
interface ScoreData {
  analysis_id: string;
  account_name: string;
  overall_score: number;
  grade: string;
  dimensions: {
    reach: number;
    engagement: number;
    consistency: number;
    virality: number;
    content_depth: number;
  };
  raw_metrics: {
    follower_count: number;
    video_count: number;
    total_likes: number;
    total_comments: number;
    total_shares: number;
    avg_engagement: number;
    share_to_like_ratio: number;
    content_type_count: number;
    keyword_count: number;
  };
  benchmarks: {
    engagement_vs_avg: number;
    virality_vs_avg: number;
  };
}

interface ExecSummary {
  analysis_id: string;
  account_name: string;
  headline?: string;
  summary?: string;
  key_metrics?: string[];
  recommendation?: string;
  score: number;
  grade: string;
  dimensions?: ScoreData["dimensions"];
  ai_provider?: string;
}

interface Threat {
  type: string;
  severity: "high" | "medium" | "low";
  title: string;
  description: string;
  evidence: string;
  confidence_score: number;
  impact: string;
}

interface ThreatData {
  analysis_id: string;
  account_name: string;
  threat_level: "critical" | "high" | "moderate" | "low" | "minimal";
  threat_count: number;
  threats: Threat[];
  score: number;
  grade: string;
}

interface CounterStrategy {
  tactic: string;
  target_weakness: string;
  action_plan: string;
  timeline: string;
  expected_impact: string;
  priority: "high" | "medium" | "low";
  confidence_score: number;
}

interface CounterData {
  analysis_id: string;
  account_name: string;
  counter_strategies: CounterStrategy[];
  overall_approach?: string;
  competitor_score: number;
  threat_level: string;
  ai_provider: string;
}

interface AnalysisItem {
  id: string;
  account_name?: string;
  url?: string;
  video_count?: number;
  ai_provider?: string;
  created_at?: string;
}

// ---- Grade color mapping ----
const gradeColors: Record<string, string> = {
  S: "#10b981", A: "#3b82f6", B: "#8b5cf6", C: "#f59e0b", D: "#ef4444",
};
const severityColors: Record<string, string> = {
  high: "#ef4444", medium: "#f59e0b", low: "#3b82f6",
};
const threatLevelColors: Record<string, string> = {
  critical: "#dc2626", high: "#ef4444", moderate: "#f59e0b", low: "#3b82f6", minimal: "#10b981",
};

export default function DashboardHomePage() {
  const { t } = useI18n();
  const [analyses, setAnalyses] = useState<AnalysisItem[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loadingList, setLoadingList] = useState(true);

  // Intelligence data
  const [score, setScore] = useState<ScoreData | null>(null);
  const [execSummary, setExecSummary] = useState<ExecSummary | null>(null);
  const [threats, setThreats] = useState<ThreatData | null>(null);
  const [counter, setCounter] = useState<CounterData | null>(null);

  // Loading states
  const [loadingScore, setLoadingScore] = useState(false);
  const [loadingExec, setLoadingExec] = useState(false);
  const [loadingThreats, setLoadingThreats] = useState(false);
  const [loadingCounter, setLoadingCounter] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load analysis list
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/intelligence/analyses");
        if (!res.ok) throw new Error(`Failed (${res.status})`);
        const data = (await res.json()) as AnalysisItem[];
        setAnalyses(data);
        if (data.length > 0) setSelectedId(data[0].id);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Load failed");
      } finally {
        setLoadingList(false);
      }
    })();
  }, []);

  // Fetch all intelligence data when analysis is selected
  const fetchIntelligence = useCallback(async (id: string) => {
    setError(null);
    setScore(null);
    setExecSummary(null);
    setThreats(null);
    setCounter(null);

    // 1. Score (instant, pure Python)
    setLoadingScore(true);
    try {
      const res = await fetch(`/api/intelligence/score/${id}`);
      if (res.ok) setScore(await res.json());
    } catch (e) { /* ignore */ }
    setLoadingScore(false);

    // 2. Threats (instant, pure Python)
    setLoadingThreats(true);
    try {
      const res = await fetch(`/api/intelligence/threats/${id}`);
      if (res.ok) setThreats(await res.json());
    } catch (e) { /* ignore */ }
    setLoadingThreats(false);

    // 3. Executive Summary (AI, ~10s) — run in background
    setLoadingExec(true);
    try {
      const res = await fetch(`/api/intelligence/executive-summary/${id}`);
      if (res.ok) setExecSummary(await res.json());
    } catch (e) { /* ignore */ }
    setLoadingExec(false);

    // 4. Counter Strategy (AI, ~10s) — run after exec summary
    setLoadingCounter(true);
    try {
      const res = await fetch(`/api/intelligence/counter-strategy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_analysis_id: id }),
      });
      if (res.ok) setCounter(await res.json());
    } catch (e) { /* ignore */ }
    setLoadingCounter(false);
  }, []);

  useEffect(() => {
    if (selectedId) fetchIntelligence(selectedId);
  }, [selectedId, fetchIntelligence]);

  // ---- Radar chart data ----
  const radarData = score
    ? [
        { dimension: t("dashboard.dim_reach"), value: score.dimensions.reach, fullMark: 100 },
        { dimension: t("dashboard.dim_engagement"), value: score.dimensions.engagement, fullMark: 100 },
        { dimension: t("dashboard.dim_consistency"), value: score.dimensions.consistency, fullMark: 100 },
        { dimension: t("dashboard.dim_virality"), value: score.dimensions.virality, fullMark: 100 },
        { dimension: t("dashboard.dim_content_depth"), value: score.dimensions.content_depth, fullMark: 100 },
      ]
    : [];

  // ---- Engagement bar chart data ----
  const engagementBars = score?.raw_metrics
    ? [
        { name: t("dashboard.bar_likes"), value: score.raw_metrics.total_likes, fill: "#3b82f6" },
        { name: t("dashboard.bar_comments"), value: score.raw_metrics.total_comments, fill: "#8b5cf6" },
        { name: t("dashboard.bar_shares"), value: score.raw_metrics.total_shares, fill: "#10b981" },
      ]
    : [];

  // ---- Score gauge ----
  const scoreGauge = (value: number, label: string, grade: string) => {
    const circumference = 2 * Math.PI * 52;
    const offset = circumference - (value / 100) * circumference;
    return (
      <div className="relative flex h-32 w-32 items-center justify-center">
        <svg className="h-32 w-32 -rotate-90" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="52" fill="none" stroke="#e2e8f0" strokeWidth="8" />
          <circle
            cx="60" cy="60" r="52" fill="none" stroke={gradeColors[grade] || "#3b82f6"}
            strokeWidth="8" strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className="transition-all duration-700 ease-out"
          />
        </svg>
        <div className="absolute flex flex-col items-center">
          <span className="text-2xl font-bold text-slate-900">{value}</span>
          <span className="text-xs font-medium text-slate-400">/ 100</span>
          <span
            className="mt-0.5 rounded px-1.5 py-0.5 text-[10px] font-bold text-white"
            style={{ backgroundColor: gradeColors[grade] || "#3b82f6" }}
          >
            {grade}
          </span>
        </div>
      </div>
    );
  };

  // ---- Dimension bar ----
  const dimBar = (label: string, value: number) => (
    <div key={label} className="flex items-center gap-3">
      <span className="w-24 shrink-0 text-xs font-medium text-slate-500">{label}</span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${value}%`,
            backgroundColor: value >= 70 ? "#10b981" : value >= 50 ? "#f59e0b" : "#ef4444",
          }}
        />
      </div>
      <span className="w-8 shrink-0 text-right text-xs font-semibold text-slate-700">{value}</span>
    </div>
  );

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{t("dashboard.title")}</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            {t("dashboard.subtitle")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selectedId ?? ""}
            onChange={(e) => setSelectedId(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 outline-none focus:border-indigo-500"
          >
            {analyses.map((a) => (
              <option key={a.id} value={a.id}>
                {a.account_name || "Unknown"} · {a.video_count ?? 0} {t("common.videos")}
              </option>
            ))}
          </select>
          <Link
            href="/intelligence"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700"
          >
            {t("dashboard.newAnalysis")}
          </Link>
        </div>
      </header>

      {/* Analysis list loading */}
      {loadingList && (
        <div className="flex h-64 items-center justify-center">
          <div className="animate-pulse text-sm text-slate-400">{t("dashboard.loadingAnalyses")}</div>
        </div>
      )}

      {/* No analyses */}
      {!loadingList && analyses.length === 0 && (
        <div className="flex h-64 items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white">
          <div className="text-center">
            <p className="text-sm text-slate-400">{t("dashboard.noAnalyses")}</p>
            <Link href="/intelligence" className="mt-2 inline-block text-sm font-semibold text-indigo-600 hover:text-indigo-700">
              {t("dashboard.startFirst")}
            </Link>
          </div>
        </div>
      )}

      {/* Dashboard content */}
      {selectedId && !loadingList && (
        <div className="space-y-5">
          {/* Row 1: Executive Summary + Score Gauge */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1fr_280px]">
            {/* Executive Summary */}
            <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-900 to-slate-800 p-6 text-white shadow-lg">
              <div className="mb-2 flex items-center gap-2">
                <span className="rounded bg-white/10 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-indigo-300">
                  {t("dashboard.executiveSummary")}
                </span>
                {execSummary?.ai_provider && execSummary.ai_provider !== "无" && (
                  <span className="rounded bg-emerald-500/20 px-2 py-0.5 text-[10px] font-medium text-emerald-300">
                    {execSummary.ai_provider}
                  </span>
                )}
              </div>
              {loadingExec ? (
                <div className="space-y-2">
                  <div className="h-5 w-3/4 animate-pulse rounded bg-white/10" />
                  <div className="h-5 w-full animate-pulse rounded bg-white/10" />
                  <div className="h-5 w-5/6 animate-pulse rounded bg-white/10" />
                </div>
              ) : execSummary ? (
                <>
                  {execSummary.headline && (
                    <h2 className="mb-3 text-lg font-bold leading-tight">{execSummary.headline}</h2>
                  )}
                  <p className="text-sm leading-relaxed text-slate-300">
                    {execSummary.summary}
                  </p>
                  {execSummary.key_metrics && execSummary.key_metrics.length > 0 && (
                    <div className="mt-4 flex flex-wrap gap-2">
                      {execSummary.key_metrics.map((m, i) => (
                        <span key={i} className="rounded-lg bg-white/5 px-3 py-1 text-xs text-slate-300">
                          {m}
                        </span>
                      ))}
                    </div>
                  )}
                  {execSummary.recommendation && (
                    <div className="mt-4 border-l-2 border-indigo-400 pl-3">
                      <p className="text-xs text-slate-400">{t("dashboard.strategicRecommendation")}</p>
                      <p className="mt-1 text-sm font-medium text-indigo-200">{execSummary.recommendation}</p>
                    </div>
                  )}
                </>
              ) : (
                <p className="text-sm text-slate-400">摘要生成失败</p>
              )}
            </div>

            {/* Score Gauge */}
            <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <span className="mb-3 text-xs font-bold uppercase tracking-wider text-slate-400">
                {t("dashboard.competitorScore")}
              </span>
              {loadingScore ? (
                <div className="flex h-32 w-32 items-center justify-center">
                  <div className="h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-indigo-600" />
                </div>
              ) : score ? (
                <>
                  {scoreGauge(score.overall_score, "Overall", score.grade)}
                  <p className="mt-3 text-center text-sm font-medium text-slate-600">
                    {score.account_name}
                  </p>
                </>
              ) : (
                <p className="text-sm text-slate-400">暂无评分数据</p>
              )}
            </div>
          </div>

          {/* Row 2: Radar Chart + Dimension Bars */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            {/* Radar Chart */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-sm font-bold text-slate-900">{t("dashboard.radarAnalytics")}</h3>
              {score ? (
                <ResponsiveContainer width="100%" height={260}>
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="#e2e8f0" />
                    <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 11, fill: "#64748b" }} />
                    <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9, fill: "#94a3b8" }} />
                    <Radar
                      dataKey="value"
                      stroke="#6366f1"
                      fill="#6366f1"
                      fillOpacity={0.3}
                      strokeWidth={2}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-52 items-center justify-center text-sm text-slate-400">
                  {loadingScore ? t("dashboard.loadingAnalyses") : t("common.noData")}
                </div>
              )}
            </div>

            {/* Dimension Bars */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-sm font-bold text-slate-900">{t("dashboard.dimensionBreakdown")}</h3>
              {score ? (
                <div className="space-y-3">
                  {Object.entries(score.dimensions).map(([key, val]) =>
                    dimBar(t(`dashboard.dim_${key}`), val)
                  )}
                </div>
              ) : (
                <p className="py-8 text-center text-sm text-slate-400">{t("common.noData")}</p>
              )}
            </div>
          </div>

          {/* Row 3: Engagement Bar Chart + Raw Metrics */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-[1.5fr_1fr]">
            {/* Engagement Bar Chart */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-sm font-bold text-slate-900">{t("dashboard.engagementDistribution")}</h3>
              {score ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={engagementBars}>
                    <XAxis dataKey="name" tick={{ fontSize: 12, fill: "#64748b" }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                    <Tooltip
                      contentStyle={{
                        borderRadius: 8, border: "1px solid #e2e8f0",
                        fontSize: 12, padding: "8px 12px",
                      }}
                    />
                    <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                      {engagementBars.map((entry, i) => (
                        <Cell key={i} fill={entry.fill} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-40 items-center justify-center text-sm text-slate-400">{t("common.noData")}</div>
              )}
            </div>

            {/* Raw Metrics */}
            <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
              <h3 className="mb-4 text-sm font-bold text-slate-900">{t("dashboard.keyMetrics")}</h3>
              {score ? (
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: t("dashboard.followers"), value: score.raw_metrics.follower_count, suffix: "" },
                    { label: t("dashboard.videosCount"), value: score.raw_metrics.video_count, suffix: "" },
                    { label: t("dashboard.totalLikes"), value: score.raw_metrics.total_likes, suffix: "" },
                    { label: t("dashboard.totalShares"), value: score.raw_metrics.total_shares, suffix: "" },
                    { label: t("dashboard.avgEngagement"), value: score.raw_metrics.avg_engagement, suffix: "" },
                    { label: t("dashboard.shareRatio"), value: score.raw_metrics.share_to_like_ratio, suffix: "" },
                  ].map((m) => (
                    <div key={m.label} className="rounded-lg bg-slate-50 p-3">
                      <p className="text-[10px] font-medium uppercase tracking-wide text-slate-400">{m.label}</p>
                      <p className="mt-1 text-lg font-bold text-slate-900">
                        {typeof m.value === "number" ? m.value.toLocaleString() : "—"}{m.suffix}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-8 text-center text-sm text-slate-400">{t("common.noData")}</p>
              )}
            </div>
          </div>

          {/* Row 4: Threat Detection */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900">{t("dashboard.threatDetection")}</h3>
              {threats && (
                <span
                  className="rounded-full px-3 py-1 text-xs font-bold text-white"
                  style={{ backgroundColor: threatLevelColors[threats.threat_level] || "#64748b" }}
                >
                  {t(`common.threatLevel_${threats.threat_level}`)}
                </span>
              )}
            </div>
            {loadingThreats ? (
              <div className="flex h-24 items-center justify-center text-sm text-slate-400">{t("dashboard.analyzingThreats")}</div>
            ) : threats ? (
              threats.threats.length > 0 ? (
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  {threats.threats.map((th, i) => (
                    <div
                      key={i}
                      className="rounded-xl border-l-4 bg-slate-50 p-4"
                      style={{ borderLeftColor: severityColors[th.severity] || "#64748b" }}
                    >
                      <div className="flex items-start justify-between gap-2">
                        <h4 className="text-sm font-semibold text-slate-900">{th.title}</h4>
                        <span
                          className="shrink-0 rounded px-2 py-0.5 text-[10px] font-bold text-white"
                          style={{ backgroundColor: severityColors[th.severity] || "#64748b" }}
                        >
                          {t(`common.severity_${th.severity}`)}
                        </span>
                      </div>
                      <p className="mt-1.5 text-xs leading-relaxed text-slate-600">{th.description}</p>
                      <div className="mt-2 flex items-center gap-3 text-[10px] text-slate-400">
                        <span>{t("dashboard.impact")}: {th.impact}</span>
                        <span>{t("dashboard.confidence")}: {(th.confidence_score * 100).toFixed(0)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-6 text-center text-sm text-slate-400">{t("dashboard.noThreats")}</p>
              )
            ) : (
              <p className="py-6 text-center text-sm text-slate-400">{t("dashboard.noThreatData")}</p>
            )}
          </div>

          {/* Row 5: Counter Strategy */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-sm font-bold text-slate-900">{t("dashboard.attackStrategy")}</h3>
              {counter?.ai_provider && counter.ai_provider !== "无" && (
                <span className="rounded bg-indigo-50 px-2 py-0.5 text-[10px] font-medium text-indigo-600">
                  {counter.ai_provider}
                </span>
              )}
            </div>
            {loadingCounter ? (
              <div className="flex h-24 items-center justify-center text-sm text-slate-400">
                <div className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-600" />
                {t("dashboard.generatingCounter")}
              </div>
            ) : counter && counter.counter_strategies?.length > 0 ? (
              <>
                {counter.overall_approach && (
                  <div className="mb-4 rounded-lg bg-indigo-50 px-4 py-2.5 text-sm font-medium text-indigo-700">
                    {counter.overall_approach}
                  </div>
                )}
                <div className="space-y-3">
                  {counter.counter_strategies.map((s, i) => (
                    <div
                      key={i}
                      className="rounded-xl border border-slate-200 p-4 transition hover:border-indigo-300 hover:shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2">
                            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
                              {i + 1}
                            </span>
                            <h4 className="text-sm font-semibold text-slate-900">{s.tactic}</h4>
                          </div>
                          <p className="mt-2 text-xs leading-relaxed text-slate-600">{s.action_plan}</p>
                          <div className="mt-2 flex flex-wrap items-center gap-2 text-[10px]">
                            <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-500">
                              {t("dashboard.target")}: {s.target_weakness}
                            </span>
                            <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-500">
                              {t("dashboard.timeline")}: {t(`dashboard.timeline_${s.timeline}`, ) || s.timeline}
                            </span>
                            <span className="rounded bg-slate-100 px-2 py-0.5 text-slate-500">
                              {t("dashboard.impactLabel")}: {s.expected_impact}
                            </span>
                          </div>
                        </div>
                        <span
                          className="shrink-0 rounded px-2 py-1 text-[10px] font-bold text-white"
                          style={{
                            backgroundColor:
                              s.priority === "high" ? "#ef4444" : s.priority === "medium" ? "#f59e0b" : "#3b82f6",
                          }}
                        >
                          {t(`dashboard.priority_${s.priority}`)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="py-6 text-center text-sm text-slate-400">
                {counter ? t("dashboard.noCounterStrategies") : t("dashboard.counterFailed")}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
