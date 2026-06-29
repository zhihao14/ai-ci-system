"use client";

// page.tsx - 主页: 提交分析 + 报告列表 + 详情面板
import { useEffect, useState } from "react";
import ReportCard from "@/components/ReportCard";
import ReportDetail from "@/components/ReportDetail";
import type { Report, ReportSummary } from "./types";

export default function Home() {
  // 表单状态
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 报告列表 & 当前选中
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [selected, setSelected] = useState<Report | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  // 拉取报告列表
  const fetchReports = async () => {
    try {
      const res = await fetch("/api/reports");
      const data = await res.json();
      setReports(data || []);
    } catch {
      /* 后端未启动时忽略 */
    }
  };

  useEffect(() => {
    fetchReports();
  }, []);

  // 提交分析
  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, name: name || undefined }),
      });
      if (!res.ok) {
        const msg = await res.json().catch(() => ({}));
        throw new Error(msg.detail || `请求失败 (${res.status})`);
      }
      const report: Report = await res.json();
      // 选中刚生成的报告并刷新列表
      setSelected(report);
      setActiveId(report.id);
      await fetchReports();
      setUrl("");
      setName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "未知错误");
    } finally {
      setLoading(false);
    }
  };

  // 查看某条报告详情
  const handleSelect = async (id: string) => {
    setActiveId(id);
    try {
      const res = await fetch(`/api/reports/${id}`);
      const data: Report = await res.json();
      setSelected(data);
    } catch {
      /* 忽略 */
    }
  };

  return (
    <main className="mx-auto max-w-6xl px-4 py-8">
      <header className="mb-8">
        <h1 className="text-2xl font-bold text-slate-900">AI 竞争情报系统</h1>
        <p className="text-sm text-slate-500">
          输入竞争对手官网地址, 自动爬取并由 AI 生成结构化情报报告
        </p>
      </header>

      {/* 提交表单 */}
      <form
        onSubmit={handleAnalyze}
        className="mb-8 grid grid-cols-1 gap-3 rounded-2xl border border-slate-200 bg-white p-5 sm:grid-cols-[1fr_220px_auto]"
      >
        <input
          type="url"
          required
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://competitor.com"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <input
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="竞争对手名称(可选)"
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-brand px-5 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "分析中..." : "开始分析"}
        </button>
      </form>

      {error && (
        <div className="mb-6 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
        {/* 报告列表 */}
        <section>
          <h2 className="mb-3 text-sm font-semibold text-slate-500">
            最近报告 ({reports.length})
          </h2>
          <div className="space-y-3">
            {reports.map((r) => (
              <ReportCard
                key={r.id}
                report={r}
                active={r.id === activeId}
                onClick={() => handleSelect(r.id)}
              />
            ))}
            {!reports.length && (
              <p className="text-sm text-slate-400">暂无报告, 提交一个 URL 试试。</p>
            )}
          </div>
        </section>

        {/* 详情面板 */}
        <section className="rounded-2xl border border-slate-200 bg-white p-6">
          {selected ? (
            <ReportDetail report={selected} />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-slate-400">
              选择左侧报告查看详情
            </div>
          )}
        </section>
      </div>
    </main>
  );
}
