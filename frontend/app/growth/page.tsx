"use client";

// growth/page.tsx - 短视频增长策略分析 (4层框架)
import { useState } from "react";

// ---- 类型 ----
interface VideoAnalysis {
  index: number;
  hook: string;
  content_pattern: string;
  emotion_type: string;
  pacing: string;
  conversion: string;
}

interface ReplicableTopic {
  topic: string;
  angle: string;
  expected_hook: string;
}

interface GrowthResult {
  url: string;
  title: string;
  account_info: string;
  analysis: {
    layer1_content_structure: {
      videos: VideoAnalysis[];
    };
    layer2_viral_mechanism: {
      why_viral: string;
      spread_model: string;
      model_explanation: string;
      key_triggers: string[];
    };
    layer3_data_trends: {
      growing_content: string[];
      declining_content: string[];
      is_exploding: boolean;
      explosion_reason: string;
    };
    layer4_strategy: {
      replicable_topics: ReplicableTopic[];
      next_7_days_direction: string[];
      should_not_do: string[];
      growth_opportunities: string[];
    };
  };
  ai_provider: string;
}

const EMOTION_COLORS: Record<string, string> = {
  "好奇": "bg-amber-50 text-amber-700",
  "共鸣": "bg-blue-50 text-blue-700",
  "愤怒": "bg-rose-50 text-rose-700",
  "惊喜": "bg-violet-50 text-violet-700",
  "焦虑": "bg-orange-50 text-orange-700",
  "信任": "bg-emerald-50 text-emerald-700",
};

function getEmotionColor(emotion: string): string {
  for (const [key, val] of Object.entries(EMOTION_COLORS)) {
    if (emotion.includes(key)) return val;
  }
  return "bg-slate-100 text-slate-600";
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

  return (
    <main className="mx-auto max-w-5xl px-4 py-8">
      {/* 头部 */}
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">短视频增长策略分析</h1>
          <p className="text-sm text-slate-500">
            4层深度拆解: 内容结构 / 爆款机制 / 数据趋势 / 竞争策略
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
          {loading ? "深度分析中..." : "开始增长分析"}
        </button>
      </form>

      {error && (
        <div className="mb-6 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {loading && (
        <div className="mb-6 rounded-lg bg-indigo-50 px-4 py-3 text-sm text-indigo-700">
          正在执行4层深度分析，包含爬虫抓取 + AI策略推理，预计需要 15-30 秒...
        </div>
      )}

      {/* ===== 结果展示 ===== */}
      {result && a && (
        <div className="space-y-6">
          {/* 账号概览 */}
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
            <pre className="mt-3 whitespace-pre-wrap rounded-lg bg-slate-50 p-3 text-xs text-slate-600 max-h-32 overflow-y-auto">
              {result.account_info}
            </pre>
          </div>

          {/* ===== Layer 1: 内容结构拆解 ===== */}
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
                1
              </span>
              <h3 className="text-lg font-bold text-slate-900">内容结构拆解</h3>
            </div>
            <div className="space-y-4">
              {(a.layer1_content_structure?.videos || []).map((v, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-slate-200 p-4 hover:border-indigo-300 transition"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm font-semibold text-slate-700">
                      视频 #{v.index || i + 1}
                    </span>
                    <span className={`rounded-lg px-2.5 py-0.5 text-xs font-medium ${getEmotionColor(v.emotion_type || "")}`}>
                      {v.emotion_type || "—"}
                    </span>
                  </div>
                  <div className="grid grid-cols-1 gap-3 text-sm sm:grid-cols-2">
                    <div>
                      <span className="text-xs font-medium text-slate-400">Hook结构 (前3秒)</span>
                      <p className="text-slate-700">{v.hook || "—"}</p>
                    </div>
                    <div>
                      <span className="text-xs font-medium text-slate-400">内容模式</span>
                      <p className="text-slate-700">{v.content_pattern || "—"}</p>
                    </div>
                    <div>
                      <span className="text-xs font-medium text-slate-400">节奏</span>
                      <p className="text-slate-700">{v.pacing || "—"}</p>
                    </div>
                    <div>
                      <span className="text-xs font-medium text-slate-400">转化方式</span>
                      <p className="text-slate-700">{v.conversion || "—"}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* ===== Layer 2: 爆款机制分析 ===== */}
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet-600 text-sm font-bold text-white">
                2
              </span>
              <h3 className="text-lg font-bold text-slate-900">爆款机制分析</h3>
            </div>
            <div className="space-y-4">
              <div className="rounded-xl bg-violet-50 p-4">
                <span className="text-xs font-medium text-violet-500">为什么它会火</span>
                <p className="mt-1 text-slate-800 font-medium">
                  {a.layer2_viral_mechanism?.why_viral || "—"}
                </p>
              </div>
              <div className="rounded-xl border border-violet-200 p-4">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium text-slate-400">传播机制模型</span>
                  <span className="rounded-lg bg-violet-100 px-2.5 py-0.5 text-sm font-semibold text-violet-700">
                    {a.layer2_viral_mechanism?.spread_model || "—"}
                  </span>
                </div>
                <p className="mt-2 text-sm text-slate-600">
                  {a.layer2_viral_mechanism?.model_explanation || "—"}
                </p>
              </div>
              <div>
                <span className="text-xs font-medium text-slate-400">关键触发要素</span>
                <div className="mt-2 flex flex-wrap gap-2">
                  {(a.layer2_viral_mechanism?.key_triggers || []).map((t, i) => (
                    <span
                      key={i}
                      className="rounded-lg bg-slate-100 px-3 py-1 text-sm text-slate-700"
                    >
                      {t}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </section>

          {/* ===== Layer 3: 数据趋势判断 ===== */}
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-sm font-bold text-white">
                3
              </span>
              <h3 className="text-lg font-bold text-slate-900">数据趋势判断</h3>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
                <h4 className="mb-2 text-sm font-semibold text-emerald-700">
                  ↑ 增长内容
                </h4>
                <ul className="space-y-1">
                  {(a.layer3_data_trends?.growing_content || []).map((c, i) => (
                    <li key={i} className="text-sm text-slate-700">
                      • {c}
                    </li>
                  ))}
                  {!a.layer3_data_trends?.growing_content?.length && (
                    <li className="text-sm text-slate-400">无数据</li>
                  )}
                </ul>
              </div>
              <div className="rounded-xl border border-rose-200 bg-rose-50 p-4">
                <h4 className="mb-2 text-sm font-semibold text-rose-700">
                  ↓ 下降内容
                </h4>
                <ul className="space-y-1">
                  {(a.layer3_data_trends?.declining_content || []).map((c, i) => (
                    <li key={i} className="text-sm text-slate-700">
                      • {c}
                    </li>
                  ))}
                  {!a.layer3_data_trends?.declining_content?.length && (
                    <li className="text-sm text-slate-400">无数据</li>
                  )}
                </ul>
              </div>
            </div>
            <div
              className={`mt-4 rounded-xl p-4 ${
                a.layer3_data_trends?.is_exploding
                  ? "bg-orange-50 border border-orange-300"
                  : "bg-slate-50 border border-slate-200"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`rounded-lg px-2.5 py-0.5 text-sm font-semibold ${
                    a.layer3_data_trends?.is_exploding
                      ? "bg-orange-200 text-orange-800"
                      : "bg-slate-200 text-slate-600"
                  }`}
                >
                  {a.layer3_data_trends?.is_exploding ? "🔥 已进入爆发期" : "未进入爆发期"}
                </span>
              </div>
              <p className="mt-2 text-sm text-slate-600">
                {a.layer3_data_trends?.explosion_reason || "—"}
              </p>
            </div>
          </section>

          {/* ===== Layer 4: 竞争策略建议 ===== */}
          <section className="rounded-2xl border border-slate-200 bg-white p-6">
            <div className="mb-4 flex items-center gap-3">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-emerald-600 text-sm font-bold text-white">
                4
              </span>
              <h3 className="text-lg font-bold text-slate-900">竞争策略建议</h3>
            </div>
            <div className="space-y-5">
              {/* 可复制选题 */}
              <div>
                <h4 className="mb-3 text-sm font-semibold text-slate-700">可复制选题</h4>
                <div className="space-y-3">
                  {(a.layer4_strategy?.replicable_topics || []).map((t, i) => (
                    <div
                      key={i}
                      className="rounded-xl border border-emerald-200 bg-emerald-50 p-4"
                    >
                      <div className="flex items-start gap-3">
                        <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-xs font-bold text-white">
                          {i + 1}
                        </span>
                        <div className="flex-1">
                          <p className="font-semibold text-slate-800">{t.topic}</p>
                          <p className="mt-1 text-sm text-slate-600">
                            <span className="font-medium text-emerald-700">切入角度: </span>
                            {t.angle}
                          </p>
                          <p className="mt-1 text-sm text-slate-600">
                            <span className="font-medium text-emerald-700">Hook设计: </span>
                            {t.expected_hook}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* 未来7天方向 */}
              <div>
                <h4 className="mb-3 text-sm font-semibold text-slate-700">未来7天内容方向</h4>
                <div className="flex flex-wrap gap-2">
                  {(a.layer4_strategy?.next_7_days_direction || []).map((d, i) => (
                    <span
                      key={i}
                      className="rounded-lg bg-indigo-50 px-3 py-1.5 text-sm text-indigo-700 border border-indigo-200"
                    >
                      {d}
                    </span>
                  ))}
                </div>
              </div>

              {/* 不应该做什么 */}
              <div>
                <h4 className="mb-3 text-sm font-semibold text-slate-700">不应该做什么</h4>
                <div className="space-y-2">
                  {(a.layer4_strategy?.should_not_do || []).map((d, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 rounded-lg bg-rose-50 px-3 py-2"
                    >
                      <span className="mt-0.5 text-rose-500 font-bold">✕</span>
                      <span className="text-sm text-slate-700">{d}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* 增长机会点 */}
              <div>
                <h4 className="mb-3 text-sm font-semibold text-slate-700">增长机会点</h4>
                <div className="space-y-2">
                  {(a.layer4_strategy?.growth_opportunities || []).map((o, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2 rounded-lg bg-amber-50 px-3 py-2"
                    >
                      <span className="mt-0.5 text-amber-500 font-bold">★</span>
                      <span className="text-sm text-slate-700">{o}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
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
