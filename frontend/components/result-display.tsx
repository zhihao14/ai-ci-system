"use client";

// result-display.tsx — 共享的 evidence-based 结果展示组件
// 被 intelligence / compare 页面复用: 置信度徽标、证据标签、列表/对象渲染、卡片

const TITLE_KEYS = [
  "action", "strategy", "topic", "metric", "name", "title", "item",
  "description", "keyword", "video_title", "content_type", "insight",
  "format", "trend", "week", "competitor", "recommendation",
];

export function ConfidenceBadge({ score }: { score: number | null | undefined }) {
  const s = score ?? null;
  const cls =
    s === null
      ? "bg-slate-100 text-slate-500"
      : s >= 0.8
      ? "bg-emerald-100 text-emerald-700"
      : s >= 0.5
      ? "bg-amber-100 text-amber-700"
      : "bg-rose-100 text-rose-700";
  return (
    <span className={`rounded-md px-2 py-0.5 text-xs font-medium ${cls}`}>
      {s !== null ? `${(s * 100).toFixed(0)}%` : "N/A"}
    </span>
  );
}

export function EvidenceTags({ fields }: { fields?: string[] }) {
  if (!fields || !fields.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {fields.map((f, i) => (
        <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] text-slate-500">
          {f}
        </span>
      ))}
    </div>
  );
}

// 渲染数组: 字符串列表或对象列表 (自动识别 title 字段, 附置信度/证据)
export function Items({ items }: { items?: unknown[] }) {
  if (!items || !items.length)
    return <p className="text-sm text-slate-400">暂无数据</p>;
  return (
    <div className="space-y-2">
      {items.map((it, i) => {
        if (typeof it === "string")
          return (
            <div key={i} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700">
              {it}
            </div>
          );
        const o = (it || {}) as Record<string, unknown>;
        const tk = TITLE_KEYS.find((k) => o[k] !== undefined);
        const title = tk ? String(o[tk]) : "";
        const rest = Object.entries(o)
          .filter(
            ([k, v]) =>
              !TITLE_KEYS.includes(k) &&
              k !== "confidence_score" &&
              k !== "evidence_fields" &&
              v !== null &&
              v !== undefined
          )
          .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
          .join("  ·  ");
        return (
          <div key={i} className="rounded-lg border border-slate-200 px-3 py-2">
            {title && <p className="text-sm font-medium text-slate-800">{title}</p>}
            {rest && <p className="mt-0.5 text-xs text-slate-500">{rest}</p>}
            <div className="mt-1.5 flex items-center gap-2">
              <ConfidenceBadge score={(o.confidence_score as number) ?? null} />
              <EvidenceTags fields={o.evidence_fields as string[] | undefined} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// 渲染单个对象: 键值对列表 + 置信度/证据
export function ObjectView({ obj }: { obj: Record<string, unknown> | undefined | null }) {
  if (!obj || typeof obj !== "object")
    return <p className="text-sm text-slate-400">暂无数据</p>;
  const entries = Object.entries(obj).filter(
    ([k]) => k !== "confidence_score" && k !== "evidence_fields"
  );
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <dl className="space-y-1.5">
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-2 text-sm">
            <dt className="min-w-[120px] shrink-0 text-slate-500">{k}:</dt>
            <dd className="text-slate-800">
              {Array.isArray(v) ? v.join(", ") : String(v)}
            </dd>
          </div>
        ))}
      </dl>
      <div className="mt-2 flex items-center gap-2">
        <ConfidenceBadge score={(obj.confidence_score as number) ?? null} />
        <EvidenceTags fields={obj.evidence_fields as string[] | undefined} />
      </div>
    </div>
  );
}

export function SectionCard({
  title,
  children,
  right,
}: {
  title: string;
  children: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-base font-semibold text-slate-900">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}
