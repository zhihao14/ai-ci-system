"use client";

// page.tsx — Dashboard 首页: 统计卡片 + 最近分析 + 知识库类型分布
import { useEffect, useState } from "react";
import Link from "next/link";

// ---- 类型 ----
interface RecentAnalysis {
  id?: string;
  account_name?: string;
  url?: string;
  video_count?: number;
  ai_provider?: string;
  created_at?: string;
  [k: string]: unknown;
}

interface KnowledgeType {
  content_type?: string;
  type?: string;
  count?: number;
  [k: string]: unknown;
}

interface DashboardData {
  total_analyses?: number;
  competitor_count?: number;
  knowledge_count?: number;
  comparison_count?: number;
  recent_analyses?: RecentAnalysis[];
  knowledge_type_distribution?: KnowledgeType[];
  [k: string]: unknown;
}

export default function DashboardHomePage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/intelligence/dashboard");
        if (!res.ok) throw new Error(`请求失败 (${res.status})`);
        const d = (await res.json()) as DashboardData;
        setData(d);
      } catch (e) {
        setError(e instanceof Error ? e.message : "加载失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const stats = [
    { label: "总分析数", value: data?.total_analyses ?? 0, icon: "M9 17v-2m3 2v-4m3 4v-6M4 19h16" },
    { label: "竞争对手数", value: data?.competitor_count ?? 0, icon: "M17 20h5v-2a4 4 0 0 0-3-3.87M9 20H4v-2a4 4 0 0 1 3-3.87m6-1.13a4 4 0 1 0-4-4 4 4 0 0 0 4 4z" },
    { label: "知识库条目数", value: data?.knowledge_count ?? 0, icon: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5z" },
    { label: "对比数", value: data?.comparison_count ?? 0, icon: "M8 7h8m-8 5h8m-8 5h8M4 4v16h16" },
  ];

  return (
    <div>
      {/* 页头 */}
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">仪表盘</h1>
        <p className="mt-1 text-sm text-slate-500">
          竞争情报系统总览 · 分析、对比与知识库统计
        </p>
      </header>

      {error && (
        <div className="mb-6 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      {/* 统计卡片 */}
      <section className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((s) => (
          <div
            key={s.label}
            className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"
          >
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-slate-500">{s.label}</span>
              <svg className="h-5 w-5 text-indigo-600" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d={s.icon} />
              </svg>
            </div>
            <p className="mt-3 text-3xl font-bold text-slate-900">
              {loading ? "—" : (s.value as number).toLocaleString()}
            </p>
          </div>
        ))}
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.6fr_1fr]">
        {/* 最近分析 */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">最近分析</h2>
            <Link
              href="/intelligence"
              className="text-sm font-medium text-indigo-600 hover:text-indigo-700"
            >
              新建分析 →
            </Link>
          </div>
          {loading ? (
            <p className="py-8 text-center text-sm text-slate-400">加载中...</p>
          ) : !data?.recent_analyses?.length ? (
            <p className="py-8 text-center text-sm text-slate-400">暂无分析记录</p>
          ) : (
            <div className="divide-y divide-slate-100">
              {data.recent_analyses.slice(0, 5).map((a, i) => (
                <Link
                  key={a.id ?? i}
                  href="/intelligence"
                  className="flex items-center justify-between gap-3 py-3 transition hover:bg-slate-50"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {a.account_name || a.url || "未命名分析"}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-slate-500">{a.url || "—"}</p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
                    {a.video_count != null && <span>{a.video_count} 条视频</span>}
                    {a.ai_provider && (
                      <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-indigo-600">
                        {a.ai_provider}
                      </span>
                    )}
                    {a.created_at && (
                      <span>{new Date(a.created_at).toLocaleDateString("zh-CN")}</span>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>

        {/* 知识库类型分布 */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-base font-semibold text-slate-900">知识库类型分布</h2>
            <Link
              href="/knowledge"
              className="text-sm font-medium text-indigo-600 hover:text-indigo-700"
            >
              搜索 →
            </Link>
          </div>
          {loading ? (
            <p className="py-8 text-center text-sm text-slate-400">加载中...</p>
          ) : !data?.knowledge_type_distribution?.length ? (
            <p className="py-8 text-center text-sm text-slate-400">暂无知识库数据</p>
          ) : (
            <div className="space-y-3">
              {data.knowledge_type_distribution.map((t, i) => {
                const label = t.content_type || t.type || "未知";
                const count = t.count ?? 0;
                const total = data.knowledge_type_distribution!.reduce(
                  (s, x) => s + (x.count ?? 0),
                  0
                );
                const pct = total > 0 ? Math.round((count / total) * 100) : 0;
                return (
                  <div key={i}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="text-slate-600">{label}</span>
                      <span className="text-slate-400">{count}</span>
                    </div>
                    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div
                        className="h-full rounded-full bg-indigo-600"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
