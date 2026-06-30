"use client";

// growth/page.tsx - 短视频 evidence-based 聚合分析
import { useState } from "react";

// ---- 类型 ----
interface Keyword {
  keyword: string;
  occurrence_count: number | null;
  confidence_score: number | null;
  evidence_fields: string[];
}

interface EngagementItem {
  rank: number;
  video_title: string;
  total_engagement: number | null;
  digg_count: number | null;
  comment_count: number | null;
  share_count: number | null;
  confidence_score: number | null;
  evidence_fields: string[];
}

interface TimePattern {
  peak_hours: string[] | null;
  weekday_distribution: Record<string, number> | null;
  confidence_score: number | null;
  evidence_fields: string[];
  status: string;
}

interface LikeCommentRatio {
  average_ratio: number | null;
  min_ratio: number | null;
  max_ratio: number | null;
  confidence_score: number | null;
  evidence_fields: string[];
  status: string;
}

interface ContentType {
  content_type: string;
  video_count: number | null;
  avg_engagement: number | null;
  confidence_score: number | null;
  evidence_fields: string[];
}

interface Insight {
  insight: string;
  confidence_score: number | null;
  evidence_fields: string[];
  supporting_data: string;
}

interface RawDataSummary {
  has_account_info: boolean;
  has_video_data: boolean;
  video_count: number;
  available_video_fields: string[];
  missing_video_fields: string[];
}

interface Analysis {
  data_completeness: string;
  raw_data_summary: RawDataSummary;
  aggregate_analysis: {
    high_frequency_keywords: Keyword[];
    engagement_ranking: EngagementItem[];
    posting_time_pattern: TimePattern;
    like_comment_ratio: LikeCommentRatio;
    top_content_types: ContentType[];
  };
  actionable_insights: Insight[];
}

interface GrowthResult {
  url: string;
  title: string;
  account_info: string;
  analysis: Analysis;
  ai_provider: string;
}

// ---- 置信度颜色 ----
function confidenceColor(score: number | null): string {
  if (score === null) return "bg-slate-200 text-slate-500";
  if (score >= 0.8) return "bg-emerald-100 text-emerald-700";
  if (score >= 0.5) return "bg-amber-100 text-amber-700";
  return "bg-rose-100 text-rose-700";
}

function confidenceLabel(score: number | null): string {
  if (score === null) return "无数据";
  if (score >= 0.8) return "高置信";
  if (score >= 0.5) return "中置信";
  return "低置信";
}

function ConfidenceBadge({ score }: { score: number | null }) {
  return (
    <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${confidenceColor(score)}`}>
      {score !== null ? `${(score * 100).toFixed(0)}%` : "N/A"} · {confidenceLabel(score)}
    </span>
  );
}

function EvidenceTags({ fields }: { fields: string[] }) {
  if (!fields || fields.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {fields.map((f, i) => (
        <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500 font-mono">
          {f}
        </span>
      ))}
    </div>
  );
}

function InsufficientBanner() {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3">
      <p className="text-sm font-medium text-rose-700">数据不足，无法判断</p>
      <p className="mt-1 text-xs text-rose-500">
        该指标所需的视频数据字段不存在，无法进行计算分析
      </p>
    </div>
  );
}

export default function GrowthPage() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GrowthResult | null>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/growth-analysis", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      if (!res.ok) {
        const msg = await res.json().catch(() => ({}));
        throw new Error(msg.detail || `请求失败 (${res.status})`);
      }
      const data: GrowthResult = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "未知错误");
    } finally {
      setLoading(false);
    }
  };

  const a = result?.analysis;
  const isInsufficient = a?.data_completeness === "insufficient";
  const hasVideoData = a?.raw_data_summary?.has_video_data;

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      {/* 头部 */}
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">短视频数据分析</h1>
          <p className="text-sm text-slate-500">
            Evidence-based 聚合分析 · 基于数据证据 · 每条结论附置信度
          </p>
        </div>
        <a
          href="/"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50"
        >
          返回首页
        </a>
      </header>

      {/* 输入表单 */}
      <form
        onSubmit={handleAnalyze}
        className="mb-8 grid grid-cols-1 gap-3 rounded-2xl border border-slate-200 bg-white p-5 sm:grid-cols-[1fr_auto]"
      >
        <input
          type="text"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="粘贴抖音/TikTok 账号分享链接"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-brand px-5 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "分析中..." : "开始数据分析"}
        </button>
      </form>

      {error && (
        <div className="mb-6 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="mb-6 rounded-lg bg-indigo-50 px-4 py-3 text-sm text-indigo-700">
          正在执行 evidence-based 聚合分析，包含爬虫抓取 + AI 数据统计，预计需要 10-20 秒...
        </div>
      )}

      {/* ===== 结果展示 ===== */}
      {result && a && (
        <div className="space-y-6">
          {/* 账号概览 + 数据完整性 */}
          <div className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-lg font-bold text-slate-900">{result.title}</h2>
                <a
                  href={result.url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-sm text-brand hover:underline"
                >
                  {result.url}
                </a>
              </div>
              <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-medium text-indigo-700">
                {result.ai_provider}
              </span>
            </div>

            {/* 数据完整性 banner */}
            <div className={`mt-4 rounded-xl p-4 ${
              isInsufficient
                ? "border border-rose-200 bg-rose-50"
                : hasVideoData
                ? "border border-emerald-200 bg-emerald-50"
                : "border border-amber-200 bg-amber-50"
            }`}>
              <div className="flex items-center gap-2">
                <span className={`rounded-lg px-2.5 py-0.5 text-sm font-semibold ${
                  isInsufficient
                    ? "bg-rose-200 text-rose-800"
                    : hasVideoData
                    ? "bg-emerald-200 text-emerald-800"
                    : "bg-amber-200 text-amber-800"
                }`}>
                  {isInsufficient ? "数据不足" : hasVideoData ? "数据充足" : "部分数据"}
                </span>
                <span className="text-xs text-slate-500">
                  {a.raw_data_summary?.video_count || 0} 条视频 ·{" "}
                  {a.raw_data_summary?.has_account_info ? "账号信息: 有" : "账号信息: 无"}
                </span>
              </div>

              {/* 可用/缺失字段 */}
              <div className="mt-3 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
                <div>
                  <span className="font-medium text-slate-500">可用字段: </span>
                  <span className="text-emerald-600">
                    {a.raw_data_summary?.available_video_fields?.join(", ") || "无"}
                  </span>
                </div>
                <div>
                  <span className="font-medium text-slate-500">缺失字段: </span>
                  <span className="text-rose-500">
                    {a.raw_data_summary?.missing_video_fields?.join(", ") || "无"}
                  </span>
                </div>
              </div>
            </div>

            {isInsufficient && (
              <div className="mt-3 rounded-lg bg-slate-100 px-4 py-2 text-sm text-slate-600">
                当前仅获取到账号信息，未获取到视频列表数据。视频级指标将显示「数据不足，无法判断」。
                如需完整分析，请提供视频数据。
              </div>
            )}

            <details className="mt-3">
              <summary className="cursor-pointer text-xs font-medium text-slate-400">
                查看账号原始信息
              </summary>
              <pre className="mt-2 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-600 max-h-32 overflow-y-auto">
                {result.account_info}
              </pre>
            </details>
          </div>

          {/* ===== 聚合分析 ===== */}
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <h3 className="mb-4 text-lg font-bold text-slate-900">聚合分析</h3>

            {/* 1. 高频关键词 */}
            <div className="mb-6">
              <div className="mb-3 flex items-center justify-between">
                <h4 className="text-sm font-semibold text-slate-700">高频关键词</h4>
                <span className="text-xs text-slate-400">从视频标题/描述提取</span>
              </div>
              {!hasVideoData || !a.aggregate_analysis?.high_frequency_keywords?.length ? (
                <InsufficientBanner />
              ) : (
                <div className="flex flex-wrap gap-2">
                  {a.aggregate_analysis.high_frequency_keywords.map((kw, i) => (
                    <div key={i} className="rounded-lg border border-slate-200 px-3 py-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-slate-800">{kw.keyword}</span>
                        <span className="rounded bg-indigo-50 px-1.5 py-0.5 text-xs text-indigo-600">
                          ×{kw.occurrence_count}
                        </span>
                      </div>
                      <div className="mt-1 flex items-center gap-2">
                        <ConfidenceBadge score={kw.confidence_score} />
                        <EvidenceTags fields={kw.evidence_fields} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 2. 互动量排序 */}
            <div className="mb-6">
              <div className="mb-3 flex items-center justify-between">
                <h4 className="text-sm font-semibold text-slate-700">互动量排序</h4>
                <span className="text-xs text-slate-400">按 点赞+评论+转发 降序</span>
              </div>
              {!hasVideoData || !a.aggregate_analysis?.engagement_ranking?.length ? (
                <InsufficientBanner />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 text-xs text-slate-400">
                        <th className="pb-2 pr-3 text-left font-medium">#</th>
                        <th className="pb-2 pr-3 text-left font-medium">标题</th>
                        <th className="pb-2 pr-3 text-right font-medium">点赞</th>
                        <th className="pb-2 pr-3 text-right font-medium">评论</th>
                        <th className="pb-2 pr-3 text-right font-medium">转发</th>
                        <th className="pb-2 pr-3 text-right font-medium">总量</th>
                        <th className="pb-2 text-right font-medium">置信度</th>
                      </tr>
                    </thead>
                    <tbody>
                      {a.aggregate_analysis.engagement_ranking.map((item, i) => (
                        <tr key={i} className="border-b border-slate-100">
                          <td className="py-2 pr-3 font-semibold text-slate-700">{item.rank}</td>
                          <td className="py-2 pr-3 text-slate-600 max-w-xs truncate">
                            {item.video_title}
                          </td>
                          <td className="py-2 pr-3 text-right text-slate-600">
                            {item.digg_count?.toLocaleString() ?? "—"}
                          </td>
                          <td className="py-2 pr-3 text-right text-slate-600">
                            {item.comment_count?.toLocaleString() ?? "—"}
                          </td>
                          <td className="py-2 pr-3 text-right text-slate-600">
                            {item.share_count?.toLocaleString() ?? "—"}
                          </td>
                          <td className="py-2 pr-3 text-right font-semibold text-slate-800">
                            {item.total_engagement?.toLocaleString() ?? "—"}
                          </td>
                          <td className="py-2 text-right">
                            <ConfidenceBadge score={item.confidence_score} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* 3. 发布时间规律 */}
            <div className="mb-6">
              <h4 className="mb-3 text-sm font-semibold text-slate-700">发布时间规律</h4>
              {a.aggregate_analysis?.posting_time_pattern?.status?.includes("数据不足") ? (
                <InsufficientBanner />
              ) : (
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-400">高频时段</span>
                    <ConfidenceBadge score={a.aggregate_analysis?.posting_time_pattern?.confidence_score ?? null} />
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(a.aggregate_analysis?.posting_time_pattern?.peak_hours || []).map((h, i) => (
                      <span key={i} className="rounded-lg bg-blue-50 px-3 py-1 text-sm text-blue-700 border border-blue-200">
                        {h}
                      </span>
                    ))}
                  </div>
                  {a.aggregate_analysis?.posting_time_pattern?.weekday_distribution && (
                    <div className="mt-3">
                      <span className="text-xs font-medium text-slate-400">周发布分布</span>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {Object.entries(a.aggregate_analysis.posting_time_pattern.weekday_distribution).map(([day, count]) => (
                          <span key={day} className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                            {day}: {count}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="mt-2">
                    <EvidenceTags fields={a.aggregate_analysis?.posting_time_pattern?.evidence_fields || []} />
                  </div>
                </div>
              )}
            </div>

            {/* 4. 点赞评论比 */}
            <div className="mb-6">
              <h4 className="mb-3 text-sm font-semibold text-slate-700">点赞评论比</h4>
              {a.aggregate_analysis?.like_comment_ratio?.status?.includes("数据不足") ? (
                <InsufficientBanner />
              ) : (
                <div className="rounded-xl border border-slate-200 p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-xs font-medium text-slate-400">平均比值</span>
                    <ConfidenceBadge score={a.aggregate_analysis?.like_comment_ratio?.confidence_score ?? null} />
                  </div>
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <p className="text-xs text-slate-400">最低</p>
                      <p className="text-lg font-bold text-slate-700">
                        {a.aggregate_analysis?.like_comment_ratio?.min_ratio?.toFixed(1) ?? "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">平均</p>
                      <p className="text-lg font-bold text-indigo-600">
                        {a.aggregate_analysis?.like_comment_ratio?.average_ratio?.toFixed(1) ?? "—"}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400">最高</p>
                      <p className="text-lg font-bold text-slate-700">
                        {a.aggregate_analysis?.like_comment_ratio?.max_ratio?.toFixed(1) ?? "—"}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3">
                    <EvidenceTags fields={a.aggregate_analysis?.like_comment_ratio?.evidence_fields || []} />
                  </div>
                </div>
              )}
            </div>

            {/* 5. 高表现内容类型 */}
            <div>
              <h4 className="mb-3 text-sm font-semibold text-slate-700">高表现内容类型</h4>
              {!hasVideoData || !a.aggregate_analysis?.top_content_types?.length ? (
                <InsufficientBanner />
              ) : (
                <div className="space-y-2">
                  {a.aggregate_analysis.top_content_types.map((ct, i) => (
                    <div key={i} className="rounded-xl border border-slate-200 p-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm font-medium text-slate-800">{ct.content_type}</span>
                        <ConfidenceBadge score={ct.confidence_score} />
                      </div>
                      <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">
                        <span>视频数: {ct.video_count ?? "—"}</span>
                        <span>平均互动: {ct.avg_engagement?.toLocaleString() ?? "—"}</span>
                      </div>
                      <div className="mt-1">
                        <EvidenceTags fields={ct.evidence_fields} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* ===== 可执行结论 ===== */}
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <h3 className="mb-4 text-lg font-bold text-slate-900">数据驱动结论</h3>
            {!a.actionable_insights?.length ? (
              <p className="text-sm text-slate-400">无可用数据结论</p>
            ) : (
              <div className="space-y-3">
                {a.actionable_insights.map((insight, i) => (
                  <div key={i} className="rounded-xl border border-indigo-200 bg-indigo-50 p-4">
                    <div className="flex items-start gap-3">
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-600 text-xs font-bold text-white">
                        {i + 1}
                      </span>
                      <div className="flex-1">
                        <p className="text-sm text-slate-800">{insight.insight}</p>
                        {insight.supporting_data && (
                          <p className="mt-2 rounded-lg bg-white/60 px-3 py-1.5 text-xs text-slate-600">
                            <span className="font-medium text-indigo-600">数据支撑: </span>
                            {insight.supporting_data}
                          </p>
                        )}
                        <div className="mt-2 flex items-center gap-3">
                          <ConfidenceBadge score={insight.confidence_score} />
                          <EvidenceTags fields={insight.evidence_fields} />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* JSON 原始数据 (折叠) */}
          <details className="rounded-2xl border border-slate-200 bg-white p-4">
            <summary className="cursor-pointer text-sm font-medium text-slate-500">
              查看完整 JSON 数据
            </summary>
            <pre className="mt-3 overflow-x-auto rounded-lg bg-slate-900 p-4 text-xs text-slate-300">
              {JSON.stringify(a, null, 2)}
            </pre>
          </details>
        </div>
      )}
    </main>
  );
}
