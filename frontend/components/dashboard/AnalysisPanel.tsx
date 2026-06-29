"use client";

// AnalysisPanel.tsx - AI 爆款分析结果展示
import type { ViralAnalysis } from "@/app/dashboard/types";
import { FireIcon, ChartIcon, LayersIcon, TargetIcon, LightbulbIcon, SparklesIcon } from "./Icons";

function SectionTitle({ icon, title }: { icon: React.ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-slate-400">{icon}</span>
      <h3 className="text-[13px] font-semibold text-slate-700">{title}</h3>
    </div>
  );
}

export default function AnalysisPanel({
  analysis,
  loading,
}: {
  analysis: ViralAnalysis | null;
  loading: boolean;
}) {
  // ---- 加载中 ----
  if (loading) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6">
        <div className="relative flex h-14 w-14 items-center justify-center">
          <span className="absolute h-14 w-14 animate-ping rounded-full bg-brand-100" />
          <span className="relative flex h-10 w-10 items-center justify-center rounded-full bg-brand-500">
            <SparklesIcon className="w-5 h-5 text-white" />
          </span>
        </div>
        <p className="mt-4 text-[13px] font-medium text-slate-600">AI 正在分析爆款规律...</p>
        <p className="mt-1 text-[11px] text-slate-400">提取标题结构、内容套路与可复制选题</p>
      </div>
    );
  }

  // ---- 空状态 ----
  if (!analysis) {
    return (
      <div className="flex h-full flex-col items-center justify-center px-6 text-center">
        <div className="flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-300">
          <FireIcon className="w-6 h-6" />
        </div>
        <p className="mt-3 text-[13px] font-medium text-slate-600">AI 爆款分析</p>
        <p className="mt-1 max-w-[200px] text-[11px] text-slate-400">
          勾选左侧视频后点击"AI 爆款分析",系统将自动提炼爆款规律
        </p>
      </div>
    );
  }

  // ---- 结果展示 ----
  return (
    <div className="h-full overflow-y-auto">
      {/* 头部: 模型信息 */}
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <h2 className="flex items-center gap-1.5 text-[13px] font-semibold text-slate-700">
            <FireIcon className="w-4 h-4 text-amber-500" />
            爆款分析结果
          </h2>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] font-medium text-slate-500">
            {analysis.provider} · {analysis.model_used}
          </span>
        </div>
        <p className="mt-2 text-[12px] leading-relaxed text-slate-600">{analysis.overview}</p>
      </div>

      <div className="space-y-5 px-4 py-4">
        {/* 爆款原因 */}
        {analysis.viral_reasons?.length > 0 && (
          <div>
            <SectionTitle icon={<ChartIcon className="w-4 h-4" />} title="爆款原因" />
            <div className="mt-2 space-y-2">
              {analysis.viral_reasons.map((r, i) => (
                <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
                  <div className="flex items-start gap-2">
                    <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-brand-50 text-[10px] font-bold text-brand-600">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-[12px] font-semibold text-slate-800">{r.factor}</p>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">{r.detail}</p>
                      {r.evidence && (
                        <p className="mt-1 flex items-start gap-1 text-[11px] text-slate-400">
                          <span className="text-brand-400">证据:</span>
                          <span className="italic">{r.evidence}</span>
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 标题结构 */}
        {analysis.title_patterns?.length > 0 && (
          <div>
            <SectionTitle icon={<LayersIcon className="w-4 h-4" />} title="标题结构" />
            <div className="mt-2 space-y-2">
              {analysis.title_patterns.map((p, i) => (
                <div key={i} className="rounded-lg border border-slate-200 bg-white p-3">
                  <p className="text-[12px] font-semibold text-slate-800">{p.pattern}</p>
                  {p.examples?.length > 0 && (
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {p.examples.map((ex, j) => (
                        <span key={j} className="rounded bg-blue-50 px-1.5 py-0.5 text-[10px] text-blue-600">
                          {ex}
                        </span>
                      ))}
                    </div>
                  )}
                  {p.template && (
                    <p className="mt-1.5 rounded bg-slate-50 px-2 py-1 font-mono text-[10px] text-slate-500">
                      模板: {p.template}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 内容套路 */}
        {analysis.content_tactics?.length > 0 && (
          <div>
            <SectionTitle icon={<TargetIcon className="w-4 h-4" />} title="内容套路" />
            <div className="mt-2 space-y-2">
              {analysis.content_tactics.map((t, i) => (
                <div key={i} className="flex items-start gap-2 rounded-lg border border-slate-200 bg-white p-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between">
                      <p className="text-[12px] font-semibold text-slate-800">{t.name}</p>
                      <span className="shrink-0 rounded-full bg-emerald-50 px-1.5 py-0.5 text-[9px] font-medium text-emerald-600">
                        {t.frequency}
                      </span>
                    </div>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-slate-500">{t.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* 可复制选题 */}
        {analysis.topic_suggestions?.length > 0 && (
          <div>
            <SectionTitle icon={<LightbulbIcon className="w-4 h-4" />} title="可复制选题" />
            <div className="mt-2 space-y-2">
              {analysis.topic_suggestions.map((s, i) => (
                <div key={i} className="rounded-lg border border-brand-100 bg-brand-50/30 p-3">
                  <p className="text-[12px] font-semibold text-slate-800">{s.title}</p>
                  <div className="mt-1.5 flex items-center gap-2 text-[10px]">
                    <span className="rounded bg-white px-1.5 py-0.5 text-slate-500">
                      角度: {s.angle}
                    </span>
                    <span className="rounded bg-white px-1.5 py-0.5 text-brand-500">
                      {s.target_platform}
                    </span>
                  </div>
                  <p className="mt-1 text-[10px] leading-relaxed text-slate-400">{s.why_works}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Token 统计 */}
        <div className="flex items-center justify-between border-t border-slate-100 pt-3 text-[10px] text-slate-400">
          <span>Token: {analysis.prompt_tokens} + {analysis.completion_tokens} = {analysis.prompt_tokens + analysis.completion_tokens}</span>
        </div>
      </div>
    </div>
  );
}
