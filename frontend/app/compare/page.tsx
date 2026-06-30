"use client";

// compare/page.tsx — 多竞争对手对比: 选择已有分析 → 对比矩阵 / 竞争格局 / SWOT / 建议
import { useEffect, useState } from "react";
import { ConfidenceBadge, Items, SectionCard } from "@/components/result-display";
import { useI18n } from "@/lib/i18n";

// ---- 类型 ----
interface AnalysisItem {
  id: string;
  account_name?: string;
  url?: string;
  video_count?: number;
  ai_provider?: string;
  created_at?: string;
  [k: string]: unknown;
}

interface MatrixRow {
  metric?: string;
  values?: unknown[];
  [k: string]: unknown;
}

interface CompareResult {
  comparison_matrix?: {
    columns?: string[];
    rows?: MatrixRow[];
  };
  competitive_landscape?: Record<string, unknown>[];
  swot_analysis?: {
    strengths?: string[];
    weaknesses?: string[];
    opportunities?: string[];
    threats?: string[];
  };
  strategic_recommendations?: unknown[];
  [k: string]: unknown;
}

const SWOT_CELLS = [
  { key: "strengths", label: "compare.strengths", color: "border-emerald-200 bg-emerald-50" },
  { key: "weaknesses", label: "compare.weaknesses", color: "border-rose-200 bg-rose-50" },
  { key: "opportunities", label: "compare.opportunities", color: "border-indigo-200 bg-indigo-50" },
  { key: "threats", label: "compare.threats", color: "border-amber-200 bg-amber-50" },
] as const;

export default function ComparePage() {
  const { t } = useI18n();
  const [list, setList] = useState<AnalysisItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CompareResult | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/intelligence/analyses");
        if (!res.ok) throw new Error(`${t("common.requestFailed")} (${res.status})`);
        const data = (await res.json()) as AnalysisItem[];
        setList(Array.isArray(data) ? data : []);
      } catch (e) {
        setError(e instanceof Error ? e.message : t("common.unknownError"));
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else if (next.size < 5) next.add(id);
      return next;
    });
  };

  const handleCompare = async () => {
    if (selected.size < 2) return;
    setComparing(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/intelligence/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ analysis_ids: Array.from(selected) }),
      });
      if (!res.ok) {
        const msg = await res.json().catch(() => ({}));
        throw new Error(msg.detail || `${t("common.requestFailed")} (${res.status})`);
      }
      setResult((await res.json()) as CompareResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.unknownError"));
    } finally {
      setComparing(false);
    }
  };

  const matrix = result?.comparison_matrix;
  const swot = result?.swot_analysis;

  return (
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">{t("compare.title")}</h1>
        <p className="mt-1 text-sm text-slate-500">
          {t("compare.subtitle")}
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      )}

      {/* 分析选择列表 */}
      <section className="mb-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-semibold text-slate-900">
            已有分析 ({list.length})
          </h2>
          <div className="flex items-center gap-3">
            <span className="text-xs text-slate-500">{t("compare.selected")} {selected.size}/5</span>
            <button
              onClick={handleCompare}
              disabled={selected.size < 2 || comparing}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50"
            >
              {comparing ? t("compare.comparing") : t("compare.compareBtn")}
            </button>
          </div>
        </div>

        {loading ? (
          <p className="py-8 text-center text-sm text-slate-400">{t("common.loading")}</p>
        ) : list.length === 0 ? (
          <p className="py-8 text-center text-sm text-slate-400">{t("compare.noData")}</p>
        ) : (
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((a) => {
              const checked = selected.has(a.id);
              return (
                <label
                  key={a.id}
                  className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition ${
                    checked
                      ? "border-indigo-500 bg-indigo-50"
                      : "border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggle(a.id)}
                    className="mt-0.5 h-4 w-4 rounded border-slate-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {a.account_name || a.url || "未命名"}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-slate-500">{a.url || "—"}</p>
                    <div className="mt-1 flex items-center gap-2 text-xs text-slate-400">
                      {a.video_count != null && <span>{a.video_count} {t("common.videos")}</span>}
                      {a.ai_provider && <span>· {a.ai_provider}</span>}
                    </div>
                  </div>
                </label>
              );
            })}
          </div>
        )}
      </section>

      {/* 对比结果 */}
      {result && (
        <div className="space-y-6">
          {/* 对比矩阵 */}
          {matrix?.rows?.length ? (
            <SectionCard title={t("compare.comparisonMatrix")}>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs text-slate-400">
                      <th className="pb-2 pr-3 text-left font-medium">指标</th>
                      {(matrix.columns || []).map((c, i) => (
                        <th key={i} className="pb-2 px-3 text-left font-medium">
                          {String(c)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {matrix.rows.map((row, i) => (
                      <tr key={i} className="border-b border-slate-100 hover:bg-slate-50">
                        <td className="py-2 pr-3 font-medium text-slate-700">
                          {row.metric || "—"}
                        </td>
                        {(row.values || []).map((v, j) => (
                          <td key={j} className="py-2 px-3 text-slate-600">
                            {Array.isArray(v) ? v.join(", ") : String(v ?? "—")}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </SectionCard>
          ) : null}

          {/* 竞争格局 */}
          {result.competitive_landscape?.length ? (
            <SectionCard title={t("compare.competitiveLandscape")}>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {result.competitive_landscape.map((c, i) => {
                  const o = c as Record<string, unknown>;
                  return (
                    <div key={i} className="rounded-xl border border-slate-200 p-4">
                      <div className="mb-2 flex items-center justify-between">
                        <span className="text-sm font-semibold text-slate-900">
                          {String(o.competitor ?? o.name ?? "—")}
                        </span>
                        <ConfidenceBadge score={(o.confidence_score as number) ?? null} />
                      </div>
                      <dl className="space-y-1">
                        {Object.entries(o)
                          .filter(
                            ([k]) => k !== "competitor" && k !== "confidence_score" && k !== "evidence_fields"
                          )
                          .map(([k, v]) => (
                            <div key={k} className="flex gap-2 text-xs">
                              <dt className="min-w-[80px] shrink-0 text-slate-400">{k}:</dt>
                              <dd className="text-slate-600">
                                {Array.isArray(v) ? v.join(", ") : String(v ?? "—")}
                              </dd>
                            </div>
                          ))}
                      </dl>
                    </div>
                  );
                })}
              </div>
            </SectionCard>
          ) : null}

          {/* SWOT 分析 */}
          {swot ? (
            <SectionCard title={t("compare.swotAnalysis")}>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {SWOT_CELLS.map((cell) => {
                  const items = (swot as Record<string, string[] | undefined>)[cell.key];
                  return (
                    <div key={cell.key} className={`rounded-xl border p-4 ${cell.color}`}>
                      <h3 className="mb-2 text-sm font-semibold text-slate-800">{t(cell.label)}</h3>
                      {items && items.length ? (
                        <ul className="space-y-1.5">
                          {items.map((s, i) => (
                            <li key={i} className="flex gap-2 text-sm text-slate-700">
                              <span className="text-slate-400">·</span>
                              <span>{s}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-sm text-slate-400">{t("common.noData")}</p>
                      )}
                    </div>
                  );
                })}
              </div>
            </SectionCard>
          ) : null}

          {/* 战略建议 */}
          <SectionCard title={t("compare.strategicRecommendations")}>
            <Items items={result.strategic_recommendations} />
          </SectionCard>
        </div>
      )}
    </div>
  );
}
