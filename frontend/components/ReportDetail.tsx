"use client";

// ReportDetail.tsx - 报告详情面板 (展示 AI 结构化情报)
import type { Report } from "@/app/types";

function TagList({ title, items, color }: { title: string; items: string[]; color: string }) {
  return (
    <div>
      <h4 className="mb-2 text-sm font-semibold text-slate-700">{title}</h4>
      <div className="flex flex-wrap gap-2">
        {(items || []).map((it, i) => (
          <span key={i} className={`rounded-lg px-2.5 py-1 text-sm ${color}`}>
            {it}
          </span>
        ))}
        {!items?.length && <span className="text-sm text-slate-400">无</span>}
      </div>
    </div>
  );
}

export default function ReportDetail({ report }: { report: Report }) {
  const pos = report.positioning || {};
  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div>
        <h2 className="text-xl font-bold text-slate-900">{report.title || report.url}</h2>
        <a
          href={report.url}
          target="_blank"
          rel="noreferrer"
          className="text-sm text-brand hover:underline"
        >
          {report.url}
        </a>
        <p className="mt-3 text-slate-700 leading-relaxed">{report.summary}</p>
      </div>

      {/* 产品 & 定价 */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <TagList
          title="主要产品 / 服务"
          items={report.products}
          color="bg-blue-50 text-blue-700"
        />
        <TagList
          title="定价信息"
          items={report.pricing}
          color="bg-amber-50 text-amber-700"
        />
      </div>

      {/* 市场定位 */}
      <div className="rounded-xl bg-slate-50 p-4">
        <h4 className="mb-2 text-sm font-semibold text-slate-700">市场定位</h4>
        <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-slate-400">目标市场</dt>
            <dd className="text-slate-700">{pos.market || "—"}</dd>
          </div>
          <div>
            <dt className="text-slate-400">目标客群</dt>
            <dd className="text-slate-700">{pos.audience || "—"}</dd>
          </div>
          <div>
            <dt className="text-slate-400">主要区域</dt>
            <dd className="text-slate-700">{pos.region || "—"}</dd>
          </div>
        </dl>
      </div>

      {/* SWOT */}
      <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
        <TagList
          title="优势 (Strengths)"
          items={report.strengths}
          color="bg-emerald-50 text-emerald-700"
        />
        <TagList
          title="劣势 (Weaknesses)"
          items={report.weaknesses}
          color="bg-rose-50 text-rose-700"
        />
      </div>

      {/* 近期动向 */}
      <div>
        <h4 className="mb-1 text-sm font-semibold text-slate-700">近期动向</h4>
        <p className="text-sm text-slate-600">
          {report.recent_changes || "无明显变化"}
        </p>
      </div>

      <p className="text-xs text-slate-400">
        由 {report.ai_provider} 生成 ·{" "}
        {report.created_at && new Date(report.created_at).toLocaleString("zh-CN")}
      </p>
    </div>
  );
}
