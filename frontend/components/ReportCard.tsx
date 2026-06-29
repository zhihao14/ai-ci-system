"use client";

// ReportCard.tsx - 报告列表项卡片
import type { ReportSummary } from "@/app/types";

export default function ReportCard({
  report,
  active,
  onClick,
}: {
  report: ReportSummary;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left rounded-xl border p-4 transition hover:border-brand hover:shadow-sm ${
        active ? "border-brand bg-indigo-50" : "border-slate-200 bg-white"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <h3 className="font-semibold text-slate-900 truncate">
          {report.title || report.url}
        </h3>
        <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
          {report.ai_provider}
        </span>
      </div>
      <p className="mt-1 truncate text-sm text-slate-500">{report.url}</p>
      <p className="mt-2 line-clamp-2 text-sm text-slate-600">
        {report.summary || "暂无概述"}
      </p>
      <p className="mt-2 text-xs text-slate-400">
        {new Date(report.created_at).toLocaleString("zh-CN")}
      </p>
    </button>
  );
}
