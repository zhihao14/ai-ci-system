"use client";

// result-display.tsx — 共享结果展示组件
// 被分析/对比页面复用: 数据卡片、列表渲染
// 原则: 不显示任何技术字段名，用普通中文

const FIELD_LABELS: Record<string, string> = {
  action: "行动方案",
  strategy: "策略",
  topic: "主题",
  metric: "指标",
  name: "名称",
  title: "标题",
  item: "项目",
  description: "说明",
  keyword: "关键词",
  video_title: "视频标题",
  content_type: "内容类型",
  insight: "发现",
  format: "形式",
  trend: "趋势",
  week: "周",
  competitor: "对手",
  recommendation: "建议",
  video_count: "视频数",
  avg_engagement: "平均互动",
  occurrence_count: "出现次数",
  rank: "排名",
  digg_count: "点赞数",
  comment_count: "评论数",
  share_count: "转发数",
  total_engagement: "总互动量",
  follower_count: "粉丝数",
  direction: "方向",
  current_frequency: "当前频率",
  trend_direction: "趋势方向",
  expected_avg_engagement: "预期平均互动",
  key_driver: "关键因素",
  current_momentum: "当前势头",
  projected_growth: "预计增长",
  bottleneck: "瓶颈",
  opportunity: "机会",
  executive_summary: "总结",
  short_term_actions: "短期行动",
  mid_term_strategy: "中期策略",
  milestone: "里程碑",
  recommended_topics: "推荐主题",
  optimal_posting_times: "最佳发布时间",
  content_mix: "内容配比",
  kpi_targets: "目标",
  current: "当前",
  target: "目标",
  timeline: "时间",
  risk_mitigation: "风险应对",
  risk: "风险",
  mitigation: "应对措施",
  posting_cadence: "发布频率",
  peak_hours: "高峰时段",
  weekday_distribution: "星期分布",
  average_ratio: "平均比率",
  min_ratio: "最低比率",
  max_ratio: "最高比率",
  content_format: "视频形式",
  engagement_patterns: "互动特点",
  tactic: "策略",
  target_weakness: "针对弱点",
  action_plan: "行动方案",
  expected_impact: "预期效果",
  priority: "优先级",
  confidence_score: "数据准确度",
};

const TITLE_KEYS = [
  "action", "strategy", "topic", "metric", "name", "title", "item",
  "description", "keyword", "video_title", "content_type", "insight",
  "format", "trend", "week", "competitor", "recommendation",
  "tactic", "opportunity", "risk",
];

function translateField(key: string): string {
  return FIELD_LABELS[key] || key.replace(/_/g, " ");
}

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
          </div>
        );
      })}
    </div>
  );
}

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
