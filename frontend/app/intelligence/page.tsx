"use client";

// intelligence/page.tsx — 核心智能分析: Crawl → Analyze → Strategy 三步流程
import { useState } from "react";
import { Items, ObjectView, SectionCard } from "@/components/result-display";
import { useI18n } from "@/lib/i18n";

// ---- 类型 ----
interface VideoItem {
  aweme_id?: string;
  title?: string;
  desc?: string;
  digg_count?: number | null;
  comment_count?: number | null;
  share_count?: number | null;
  create_time_str?: string | null;
  [k: string]: unknown;
}

interface CrawlResult {
  video_analysis_id: string;
  account_name?: string;
  url?: string;
  videos?: VideoItem[];
  video_count?: number;
  [k: string]: unknown;
}

interface AnalyzeResult {
  patterns?: {
    topic_clusters?: unknown[];
    content_format_analysis?: unknown[];
    posting_cadence?: Record<string, unknown>;
    engagement_patterns?: Record<string, unknown>;
  };
  analysis?: {
    aggregate_analysis?: {
      high_frequency_keywords?: unknown[];
      engagement_ranking?: unknown[];
      like_comment_ratio?: Record<string, unknown>;
      posting_time_pattern?: Record<string, unknown>;
      top_content_types?: unknown[];
    };
    actionable_insights?: unknown[];
  };
  trends?: {
    content_trends?: Array<{ trend?: string; direction?: string; [k: string]: unknown }> | { rising?: unknown[]; falling?: unknown[]; stable?: unknown[] };
    engagement_forecast?: Record<string, unknown>;
    growth_trajectory?: Record<string, unknown>;
  };
  ai_provider?: string;
}

interface StrategyResult {
  strategy?: {
    short_term_actions?: unknown[];
    mid_term_strategy?: unknown[];
    content_calendar?: unknown[];
    kpi_targets?: unknown[];
  };
  ai_provider?: string;
}

const STEPS = ["爬取", "分析", "策略"];

const ANALYZE_SUB_STEPS = [
  { key: "pattern", label: "总结内容规律" },
  { key: "growth", label: "挖掘数据亮点" },
  { key: "trend", label: "预判未来走势" },
] as const;

export default function IntelligencePage() {
  const { t } = useI18n();
  const [url, setUrl] = useState("");
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState<1 | 2 | 3 | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [crawl, setCrawl] = useState<CrawlResult | null>(null);
  const [analyze, setAnalyze] = useState<AnalyzeResult | null>(null);
  const [strategy, setStrategy] = useState<StrategyResult | null>(null);
  // 分析子步骤: "" | "pattern" | "growth" | "trend"
  const [analyzeStep, setAnalyzeStep] = useState<string>("");

  const api = async (path: string, body: unknown) => {
    const res = await fetch(`/api/intelligence/${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const msg = await res.json().catch(() => ({}));
      throw new Error(msg.detail || `${t("common.requestFailed")} (${res.status})`);
    }
    return res.json();
  };

  const runStep = async (
    n: 1 | 2 | 3,
    path: string,
    body: unknown,
    onOk: (d: unknown) => void
  ) => {
    setLoading(n);
    setError(null);
    try {
      onOk(await api(path, body));
      setStep(n);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.unknownError"));
    } finally {
      setLoading(null);
    }
  };

  const handleCrawl = (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    setCrawl(null);
    setAnalyze(null);
    setStrategy(null);
    setStep(0);
    runStep(1, "crawl", { url }, (d) => setCrawl(d as CrawlResult));
  };

  const handleAnalyze = async () => {
    if (!crawl?.video_analysis_id) return;
    setLoading(2);
    setError(null);
    setAnalyze(null);

    const id = crawl.video_analysis_id;
    const acc: AnalyzeResult = {};

    try {
      // Step 2a: Pattern
      setAnalyzeStep("pattern");
      const pr = await api("analyze", { video_analysis_id: id, step: "pattern" });
      acc.patterns = pr.patterns;
      acc.ai_provider = pr.ai_provider;
      setAnalyze({ ...acc });

      // Step 2b: Growth (Evidence-based)
      setAnalyzeStep("growth");
      const gr = await api("analyze", { video_analysis_id: id, step: "growth" });
      acc.analysis = gr.analysis;
      if (gr.ai_provider && gr.ai_provider !== "无") acc.ai_provider = gr.ai_provider;
      setAnalyze({ ...acc });

      // Step 2c: Trend
      setAnalyzeStep("trend");
      const tr = await api("analyze", { video_analysis_id: id, step: "trend" });
      acc.trends = tr.trends;
      if (tr.ai_provider && tr.ai_provider !== "无") acc.ai_provider = tr.ai_provider;
      setAnalyze({ ...acc });

      setStep(2);
      setAnalyzeStep("");
    } catch (err) {
      setError(err instanceof Error ? err.message : t("common.unknownError"));
      setAnalyzeStep("");
    } finally {
      setLoading(null);
    }
  };

  const handleStrategy = () => {
    if (!crawl?.video_analysis_id) return;
    runStep(3, "strategy", { video_analysis_id: crawl.video_analysis_id }, (d) =>
      setStrategy(d as StrategyResult)
    );
  };

  // 兼容 content_trends 的两种格式: 数组 [{direction: "rising"...}] 或对象 {rising: [...]}
  const rawTrends = analyze?.trends?.content_trends;
  const trends = Array.isArray(rawTrends)
    ? {
        rising: (rawTrends as Array<{ direction?: string }>).filter((t) => t.direction === "rising"),
        falling: (rawTrends as Array<{ direction?: string }>).filter((t) => t.direction === "falling"),
        stable: (rawTrends as Array<{ direction?: string }>).filter((t) => t.direction === "stable"),
      }
    : (rawTrends as { rising?: unknown[]; falling?: unknown[]; stable?: unknown[] });
  const trendGroup = (label: string, items: unknown[] | undefined, color: string) =>
    items && items.length > 0 ? (
      <div>
        <p className={`mb-2 text-xs font-semibold ${color}`}>{label}</p>
        <Items items={items} />
      </div>
    ) : null;

  const providerBadge = (p?: string) => (
    <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700">
      {p || "AI"}
    </span>
  );
  const primaryBtn = (
    label: string,
    loadingLabel: string,
    n: 1 | 2 | 3,
    onClick: () => void
  ) => (
    <button
      onClick={onClick}
      disabled={loading === n}
      className="mt-5 rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50"
    >
      {loading === n ? loadingLabel : label}
    </button>
  );

  return (
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">{t("intelligence.title")}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {t("intelligence.subtitle")}
        </p>
      </header>

      {/* 步骤进度条 */}
      <div className="mb-6 flex items-center gap-2">
        {STEPS.map((s, i) => {
          const idx = i + 1;
          const done = step >= idx;
          const active = loading === idx;
          return (
            <div key={s} className="flex flex-1 items-center gap-2">
              <div
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                  done
                    ? "bg-indigo-600 text-white"
                    : active
                    ? "animate-pulse bg-indigo-200 text-indigo-700"
                    : "bg-slate-200 text-slate-500"
                }`}
              >
                {idx}
              </div>
              <p className={`text-sm font-medium ${done || active ? "text-slate-900" : "text-slate-400"}`}>
                {s}
              </p>
              {i < STEPS.length - 1 && (
                <div className={`mx-1 h-0.5 flex-1 ${step > idx ? "bg-indigo-600" : "bg-slate-200"}`} />
              )}
            </div>
          );
        })}
      </div>

      {/* 输入表单 (Step 1: Crawl) */}
      <form
        onSubmit={handleCrawl}
        className="mb-6 grid grid-cols-1 gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-[1fr_auto]"
      >
        <input
          type="text"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder={t("intelligence.urlPlaceholder")}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <button
          type="submit"
          disabled={loading === 1}
          className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading === 1 ? t("intelligence.crawling") : t("intelligence.crawlBtn")}
        </button>
      </form>

      {error && (
        <div className="mb-6 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      )}

      {/* Step 1 结果: 爬取数据 */}
      {crawl && (
        <div className="mb-6 space-y-6">
          <SectionCard
            title="爬取结果"
            right={
              <span className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700">
                {crawl.video_count ?? 0} {t("common.videos")}
              </span>
            }
          >
            <p className="mb-4 text-sm text-slate-600">
              {t("intelligence.account")}: <span className="font-medium text-slate-900">{crawl.account_name || "—"}</span>
              {crawl.url && (
                <>
                  {" · "}
                  <a href={crawl.url} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">
                    {t("intelligence.originalLink")}
                  </a>
                </>
              )}
            </p>
            {crawl.videos && crawl.videos.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs text-slate-400">
                      <th className="pb-2 pr-3 text-left font-medium">#</th>
                      <th className="pb-2 pr-3 text-left font-medium">标题</th>
                      <th className="pb-2 pr-3 text-right font-medium">点赞</th>
                      <th className="pb-2 pr-3 text-right font-medium">评论</th>
                      <th className="pb-2 pr-3 text-right font-medium">转发</th>
                      <th className="pb-2 text-left font-medium">发布时间</th>
                    </tr>
                  </thead>
                  <tbody>
                    {crawl.videos.slice(0, 10).map((v, i) => (
                      <tr key={v.aweme_id || i} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="py-2 pr-3 text-slate-400">{i + 1}</td>
                        <td className="max-w-xs truncate py-2 pr-3 text-slate-600">
                          {v.title || v.desc || "—"}
                        </td>
                        <td className="py-2 pr-3 text-right text-slate-600">{v.digg_count?.toLocaleString() ?? "—"}</td>
                        <td className="py-2 pr-3 text-right text-slate-600">{v.comment_count?.toLocaleString() ?? "—"}</td>
                        <td className="py-2 pr-3 text-right text-slate-600">{v.share_count?.toLocaleString() ?? "—"}</td>
                        <td className="py-2 text-xs text-slate-500">
                          {v.create_time_str ? new Date(v.create_time_str).toLocaleString("zh-CN") : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-400">{t("common.noData")}</p>
            )}
            {primaryBtn(
              t("intelligence.analyzeBtn"),
              loading === 2 && analyzeStep
                ? analyzeStep === "pattern"
                  ? t("intelligence.analyzingPattern")
                  : analyzeStep === "growth"
                  ? t("intelligence.analyzingGrowth")
                  : t("intelligence.analyzingTrend")
                : "...",
              2,
              handleAnalyze
            )}
            {/* 子步骤进度 */}
            {loading === 2 && (
              <div className="mt-3 flex items-center gap-2">
                {ANALYZE_SUB_STEPS.map((ss, si) => {
                  const ssDone = analyzeStep && ANALYZE_SUB_STEPS.findIndex((x) => x.key === analyzeStep) > si;
                  const ssActive = analyzeStep === ss.key;
                  return (
                    <div key={ss.key} className="flex items-center gap-2">
                      <div
                        className={`flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold ${
                          ssDone
                            ? "bg-emerald-500 text-white"
                            : ssActive
                            ? "animate-pulse bg-indigo-500 text-white"
                            : "bg-slate-200 text-slate-400"
                        }`}
                      >
                        {ssDone ? "✓" : si + 1}
                      </div>
                      <span className={`text-xs ${ssActive ? "font-semibold text-indigo-700" : "text-slate-400"}`}>
                        {ss.key === "pattern"
                          ? t("intelligence.stepPattern")
                          : ss.key === "growth"
                          ? t("intelligence.stepGrowth")
                          : t("intelligence.stepTrend")}
                      </span>
                      {si < ANALYZE_SUB_STEPS.length - 1 && <span className="text-slate-300">→</span>}
                    </div>
                  );
                })}
              </div>
            )}
          </SectionCard>
        </div>
      )}

      {/* Step 2 结果: patterns + analysis + trends */}
      {analyze && (
        <div className="mb-6 space-y-6">
          <SectionCard title={t("intelligence.patterns")} right={providerBadge(analyze.ai_provider)}>
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.topicClusters")}</h3>
                <Items items={analyze.patterns?.topic_clusters} />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.contentFormat")}</h3>
                <Items items={analyze.patterns?.content_format_analysis} />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.postingCadence")}</h3>
                <ObjectView obj={analyze.patterns?.posting_cadence} />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.engagementPatterns")}</h3>
                <ObjectView obj={analyze.patterns?.engagement_patterns} />
              </div>
            </div>
          </SectionCard>

          <SectionCard title={t("intelligence.analysis")}>
            <div className="space-y-5">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.highFrequencyKeywords")}</h3>
                <Items items={analyze.analysis?.aggregate_analysis?.high_frequency_keywords} />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.engagementRanking")}</h3>
                <Items items={analyze.analysis?.aggregate_analysis?.engagement_ranking} />
              </div>
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.likeCommentRatio")}</h3>
                  <ObjectView obj={analyze.analysis?.aggregate_analysis?.like_comment_ratio} />
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.postingTimePattern")}</h3>
                  <ObjectView obj={analyze.analysis?.aggregate_analysis?.posting_time_pattern} />
                </div>
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.topContentTypes")}</h3>
                <Items items={analyze.analysis?.aggregate_analysis?.top_content_types} />
              </div>
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.dataDrivenConclusions")}</h3>
                <Items items={analyze.analysis?.actionable_insights} />
              </div>
            </div>
          </SectionCard>

          <SectionCard title={t("intelligence.trends")}>
            <div className="space-y-5">
              <div>
                <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.contentTrends")}</h3>
                {trends && (trends.rising || trends.falling || trends.stable) ? (
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    {trendGroup("上升 ↑", trends.rising, "text-emerald-600")}
                    {trendGroup("下降 ↓", trends.falling, "text-rose-600")}
                    {trendGroup("稳定 →", trends.stable, "text-slate-500")}
                  </div>
                ) : (
                  <p className="text-sm text-slate-400">{t("common.noData")}</p>
                )}
              </div>
              <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.engagementForecast")}</h3>
                  <ObjectView obj={analyze.trends?.engagement_forecast} />
                </div>
                <div>
                  <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.growthTrajectory")}</h3>
                  <ObjectView obj={analyze.trends?.growth_trajectory} />
                </div>
              </div>
            </div>
            {primaryBtn(t("intelligence.strategyBtn"), t("intelligence.generatingStrategy"), 3, handleStrategy)}
          </SectionCard>
        </div>
      )}

      {/* Step 3 结果: strategy */}
      {strategy && (
        <SectionCard title={t("intelligence.strategy")} right={providerBadge(strategy.ai_provider)}>
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.shortTermActions")}</h3>
              <Items items={strategy.strategy?.short_term_actions} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.midTermStrategy")}</h3>
              <Items items={strategy.strategy?.mid_term_strategy} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.contentCalendar")}</h3>
              <Items items={strategy.strategy?.content_calendar} />
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("intelligence.kpiTargets")}</h3>
              <Items items={strategy.strategy?.kpi_targets} />
            </div>
          </div>
        </SectionCard>
      )}
    </div>
  );
}
