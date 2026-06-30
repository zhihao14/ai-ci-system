"use client";

// knowledge/page.tsx — RAG 知识库搜索
import { useState } from "react";

// ---- 类型 ----
interface KnowledgeResult {
  id?: string;
  title?: string;
  content_type?: string;
  type?: string;
  content?: string;
  created_at?: string;
  score?: number | null;
  [k: string]: unknown;
}

// 内容类型 → 颜色标签
const TYPE_COLORS: Record<string, string> = {
  analysis: "bg-indigo-50 text-indigo-700",
  report: "bg-blue-50 text-blue-700",
  strategy: "bg-purple-50 text-purple-700",
  trend: "bg-emerald-50 text-emerald-700",
  insight: "bg-amber-50 text-amber-700",
  video: "bg-rose-50 text-rose-700",
};

function typeClass(t?: string) {
  if (!t) return "bg-slate-100 text-slate-600";
  const key = t.toLowerCase();
  return TYPE_COLORS[key] ?? "bg-slate-100 text-slate-600";
}

export default function KnowledgePage() {
  const [query, setQuery] = useState("");
  const [limit, setLimit] = useState(10);
  const [results, setResults] = useState<KnowledgeResult[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      const res = await fetch("/api/intelligence/knowledge/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query, limit }),
      });
      if (!res.ok) {
        const msg = await res.json().catch(() => ({}));
        throw new Error(msg.detail || `请求失败 (${res.status})`);
      }
      const data = (await res.json()) as KnowledgeResult[] | { results?: KnowledgeResult[] };
      const arr = Array.isArray(data)
        ? data
        : Array.isArray((data as { results?: KnowledgeResult[] }).results)
        ? (data as { results: KnowledgeResult[] }).results
        : [];
      setResults(arr);
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : "未知错误");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">知识库搜索</h1>
        <p className="mt-1 text-sm text-slate-500">
          基于 RAG 的语义检索 · 搜索已沉淀的情报、分析、策略与趋势
        </p>
      </header>

      {/* 搜索表单 */}
      <form
        onSubmit={handleSearch}
        className="mb-6 grid grid-cols-1 gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:grid-cols-[1fr_auto_auto]"
      >
        <input
          type="text"
          required
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="输入关键词, 如: 美妆账号增长策略"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <select
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
        >
          <option value={5}>5 条</option>
          <option value={10}>10 条</option>
          <option value={20}>20 条</option>
        </select>
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "搜索中..." : "搜索"}
        </button>
      </form>

      {error && (
        <div className="mb-6 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      )}

      {/* 搜索结果 */}
      {results !== null && (
        <div className="mb-4 text-sm text-slate-500">
          找到 <span className="font-semibold text-slate-900">{results.length}</span> 条结果
        </div>
      )}

      {results && results.length === 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-sm">
          <p className="text-sm text-slate-400">未找到匹配的知识条目</p>
        </div>
      )}

      {results && results.length > 0 && (
        <div className="space-y-3">
          {results.map((r, i) => {
            const type = r.content_type || r.type;
            return (
              <article
                key={r.id ?? i}
                className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:shadow-md"
              >
                <div className="mb-2 flex items-center justify-between gap-3">
                  <h3 className="text-base font-semibold text-slate-900">
                    {r.title || "无标题"}
                  </h3>
                  <div className="flex shrink-0 items-center gap-2">
                    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${typeClass(type)}`}>
                      {type || "未知"}
                    </span>
                    {typeof r.score === "number" && (
                      <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs text-slate-500">
                        相关度 {(r.score * 100).toFixed(0)}%
                      </span>
                    )}
                  </div>
                </div>
                {r.content && (
                  <p className="text-sm leading-relaxed text-slate-600 line-clamp-3">
                    {r.content}
                  </p>
                )}
                {r.created_at && (
                  <p className="mt-2 text-xs text-slate-400">
                    {new Date(r.created_at).toLocaleString("zh-CN")}
                  </p>
                )}
              </article>
            );
          })}
        </div>
      )}

      {/* 初始空状态 */}
      {!results && !loading && !error && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white/50 p-12 text-center">
          <svg className="mx-auto mb-3 h-10 w-10 text-slate-300" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="7" />
            <path d="M21 21l-4.3-4.3" />
          </svg>
          <p className="text-sm text-slate-400">输入关键词开始搜索知识库</p>
        </div>
      )}
    </div>
  );
}
