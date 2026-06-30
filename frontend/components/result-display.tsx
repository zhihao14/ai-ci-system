"use client";

// result-display.tsx — 共享结果展示组件
// 被智能分析 / 对比页面复用: 可靠度徽标、数据卡片、列表/对象渲染

// ---- 字段名中文翻译映射 ----
const FIELD_LABELS: Record<string, string> = {
  // 通用
  action: "行动方案",
  strategy: "策略",
  topic: "主题",
  metric: "指标",
  name: "名称",
  title: "标题",
  item: "项目",
  description: "描述",
  keyword: "关键词",
  video_title: "视频标题",
  content_type: "内容类型",
  insight: "洞察",
  format: "格式",
  trend: "趋势",
  week: "周",
  competitor: "竞争对手",
  recommendation: "建议",
  // 指标
  video_count: "视频数",
  avg_engagement: "平均互动",
  occurrence_count: "出现次数",
  rank: "排名",
  digg_count: "点赞数",
  comment_count: "评论数",
  share_count: "转发数",
  total_engagement: "总互动量",
  follower_count: "粉丝数",
  // 趋势
  direction: "方向",
  current_frequency: "当前频率",
  trend_direction: "趋势方向",
  expected_avg_engagement: "预期平均互动",
  key_driver: "关键驱动因素",
  current_momentum: "当前势头",
  projected_growth: "预计增长",
  bottleneck: "增长瓶颈",
  opportunity: "机会",
  // 策略
  executive_summary: "总结",
  short_term_actions: "短期行动",
  mid_term_strategy: "中期策略",
  milestone: "里程碑",
  recommended_topics: "推荐主题",
  optimal_posting_times: "最佳发布时间",
  content_mix: "内容配比",
  kpi_targets: "KPI 目标",
  current: "当前",
  target: "目标",
  timeline: "时间线",
  risk_mitigation: "风险应对",
  risk: "风险",
  mitigation: "应对措施",
  // 内容模式
  posting_cadence: "发布节奏",
  peak_hours: "高峰时段",
  weekday_distribution: "星期分布",
  average_ratio: "平均比率",
  min_ratio: "最低比率",
  max_ratio: "最高比率",
  content_format: "内容格式",
  engagement_patterns: "互动模式",
  // 反制策略
  tactic: "策略",
  target_weakness: "攻击目标",
  action_plan: "行动方案",
  expected_impact: "预期效果",
  priority: "优先级",
  confidence_score: "可靠度",
};

const TITLE_KEYS = [
  "action", "strategy", "topic", "metric", "name", "title", "item",
  "description", "keyword", "video_title", "content_type", "insight",
  "format", "trend", "week", "competitor", "recommendation",
  "tactic", "opportunity", "risk",
];

// ---- 证据字段翻译 ----
const EVIDENCE_LABELS: Record<string, string> = {
  title: "标题",
  desc: "描述",
  create_time: "发布时间",
  digg_count: "点赞数",
  comment_count: "评论数",
  share_count: "转发数",
  video_count: "视频数",
  avg_engagement: "平均互动",
  follower_count: "粉丝数",
  consistency_score: "一致性评分",
  total_shares: "总转发",
  total_likes: "总点赞",
  top_video_engagement: "最高视频互动",
  avg: "平均",
};

function translateField(key: string): string {
  return FIELD_LABELS[key] || key.replace(/_/g, " ");
}

function translateEvidence(field: string): string {
  return EVIDENCE_LABELS[field] || field.replace(/_/g, " ");
}

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
      {s !== null ? `${(s * 100).toFixed(0)}%` : "—"}
    </span>
  );
}

export function EvidenceTags({ fields }: { fields?: string[] }) {
  if (!fields || !fields.length) return null;
  return (
    <div className="flex flex-wrap gap-1">
      {fields.map((f, i) => (
        <span key={i} className="rounded bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-500">
          {translateEvidence(f)}
        </span>
      ))}
    </div>
  );
}

// 渲染数组: 字符串列表或对象列表 (自动识别标题, 附可靠度/数据来源)
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
              k !== "supporting_data" &&
              v !== null &&
              v !== undefined &&
              v !== ""
          )
          .map(([k, v]) => `${translateField(k)}: ${Array.isArray(v) ? v.join(", ") : String(v)}`)
          .join("  ·  ");
        return (
          <div key={i} className="rounded-lg border border-slate-200 px-3 py-2">
            {title && <p className="text-sm font-medium text-slate-800">{title}</p>}
            {rest && <p className="mt-0.5 text-xs text-slate-500">{rest}</p>}
            {o.supporting_data != null && String(o.supporting_data) && (
              <p className="mt-1 text-xs text-slate-400">数据支撑: {String(o.supporting_data)}</p>
            )}
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

// 渲染单个对象: 键值对列表 + 可靠度/数据来源
export function ObjectView({ obj }: { obj: Record<string, unknown> | undefined | null }) {
  if (!obj || typeof obj !== "object")
    return <p className="text-sm text-slate-400">暂无数据</p>;
  const entries = Object.entries(obj).filter(
    ([k]) => k !== "confidence_score" && k !== "evidence_fields" && k !== "supporting_data"
  );
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <dl className="space-y-1.5">
        {entries.map(([k, v]) => (
          <div key={k} className="flex gap-2 text-sm">
            <dt className="min-w-[120px] shrink-0 text-slate-500">{translateField(k)}:</dt>
            <dd className="text-slate-800">
              {Array.isArray(v) ? v.join(", ") : String(v)}
            </dd>
          </div>
        ))}
      </dl>
      {obj.supporting_data != null && String(obj.supporting_data) && (
        <p className="mt-2 text-xs text-slate-400">数据支撑: {String(obj.supporting_data)}</p>
      )}
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
