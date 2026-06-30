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
  account_fields: Record<string, unknown> | null;
  videos: VideoData[] | null;
  video_count: number;
  analysis: Analysis;
  ai_provider: string;
}

interface VideoData {
  aweme_id: string;
  title: string;
  desc: string;
  digg_count: number | null;
  comment_count: number | null;
  share_count: number | null;
  play_count: number | null;
  create_time_str: string | null;
  video_url: string | null;
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
  const [stepMessage, setStepMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<GrowthResult | null>(null);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      // 第1步: 爬取账号信息+视频列表 (Playwright, ~30s)
      setStepMessage("正在爬取视频数据 (Playwright Network Intercept)...");
      const crawlRes = await fetch("/api/crawl", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      if (!crawlRes.ok) {
        const msg = await crawlRes.json().catch(() => ({}));
        throw new Error(msg.detail || `爬取失败 (${crawlRes.status})`);
      }
      const crawlData = await crawlRes.json();

      // 第2步: AI evidence-based 聚合分析 (~15s)
      setStepMessage("正在执行 AI evidence-based 聚合分析...");
      const analyzeRes = await fetch("/api/analyze-growth", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_info: crawlData.account_info,
          videos: crawlData.videos,
          account_fields: crawlData.account_fields,
        }),
      });
      if (!analyzeRes.ok) {
        const msg = await analyzeRes.json().catch(() => ({}));
        throw new Error(msg.detail || `分析失败 (${analyzeRes.status})`);
      }
      const analyzeData = await analyzeRes.json();

      const data: GrowthResult = {
        url: crawlData.url,
        title: crawlData.title,
        account_info: crawlData.account_info,
        account_fields: crawlData.account_fields,
        videos: crawlData.videos,
        video_count: crawlData.video_count,
        analysis: analyzeData.analysis,
        ai_provider: analyzeData.ai_provider,
      };
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "未知错误");
    } finally {
      setLoading(false);
      setStepMessage("");
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
            全面分析对手内容规律与数据亮点
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
          {stepMessage || "分析中..."}
          <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-indigo-200">
            <div className="h-full w-1/3 animate-pulse rounded-full bg-indigo-500" />
          </div>
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
                查看账号信息
              </summary>
              <div className="mt-2 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                {result.account_info}
              </div>
            </details>
          </div>

          {/* ===== 视频列表 ===== */}
          {result.videos && result.videos.length > 0 && (
            <section className="rounded-2xl border border-slate-200 bg-white p-6">
              <div className="mb-4 flex items-center justify-between">
                <h3 className="text-lg font-bold text-slate-900">爬取的视频数据</h3>
                <span className="rounded-full bg-indigo-100 px-3 py-1 text-xs font-medium text-indigo-700">
                  {result.video_count} 条视频
                </span>
              </div>
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
                    {result.videos.slice(0, 10).map((v, i) => (
                      <tr key={v.aweme_id || i} className="border-b border-slate-100">
                        <td className="py-2 pr-3 text-slate-400">{i + 1}</td>
                        <td className="py-2 pr-3 text-slate-600 max-w-xs truncate">
                          {v.title || v.desc || "—"}
                        </td>
                        <td className="py-2 pr-3 text-right text-slate-600">
                          {v.digg_count?.toLocaleString() ?? "—"}
                        </td>
                        <td className="py-2 pr-3 text-right text-slate-600">
                          {v.comment_count?.toLocaleString() ?? "—"}
                        </td>
                        <td className="py-2 pr-3 text-right text-slate-600">
                          {v.share_count?.toLocaleString() ?? "—"}
                        </td>
                        <td className="py-2 text-xs text-slate-500">
                          {v.create_time_str
                            ? new Date(v.create_time_str).toLocaleString("zh-CN")
                            : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {result.videos.length > 10 && (
                <p className="mt-2 text-xs text-slate-400">
                  仅显示前10条, 完整 {result.videos.length} 条数据已传给 AI 分析
                </p>
              )}
            </section>
          )}

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
                        <th className="pb-2 text-right font-medium">总量</th>
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
                  <div className="mb-3">
                    <span className="text-xs font-medium text-slate-400">高频时段</span>
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
                  <div className="mb-3">
                    <span className="text-xs font-medium text-slate-400">平均比值</span>
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
                      <div>
                        <span className="text-sm font-medium text-slate-800">{ct.content_type}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-4 text-xs text-slate-500">
                        <span>视频数: {ct.video_count ?? "—"}</span>
                        <span>平均互动: {ct.avg_engagement?.toLocaleString() ?? "—"}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </section>

          {/* ===== 可执行结论 ===== */}
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <h3 className="mb-4 text-lg font-bold text-slate-900">核心结论</h3>
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
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          {/* 原始数据已移除 - 不再显示 JSON */}
        </div>
      )}
    </main>
  );
}
