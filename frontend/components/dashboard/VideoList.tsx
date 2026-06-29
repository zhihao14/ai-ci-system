"use client";

// VideoList.tsx - 视频列表 (表格 + 卡片混合风格)
import type { Video } from "@/app/dashboard/types";
import { formatNumber, formatDate, engagementRate } from "@/app/dashboard/lib";
import { HeartIcon, ChatIcon, ShareIcon, PlayIcon } from "./Icons";

export default function VideoList({
  videos,
  loading,
  selectedIds,
  onToggleSelect,
  onAnalyze,
  analyzing,
  accountName,
}: {
  videos: Video[];
  loading: boolean;
  selectedIds: Set<string>;
  onToggleSelect: (id: string) => void;
  onAnalyze: () => void;
  analyzing: boolean;
  accountName: string | null;
}) {
  return (
    <div className="flex h-full flex-col">
      {/* 头部 */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div>
          <h2 className="text-[13px] font-semibold text-slate-700">
            视频列表
            {accountName && <span className="ml-1.5 text-slate-400">/ {accountName}</span>}
          </h2>
          <p className="text-[11px] text-slate-400">
            {videos.length} 条 · 已选 {selectedIds.size} 条
          </p>
        </div>
        {selectedIds.size > 0 && (
          <button
            onClick={onAnalyze}
            disabled={analyzing}
            className="flex items-center gap-1.5 rounded-lg bg-brand-600 px-3 py-1.5 text-[12px] font-medium text-white transition hover:bg-brand-700 disabled:opacity-50"
          >
            {analyzing ? (
              <>
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                分析中
              </>
            ) : (
              <>AI 爆款分析 ({selectedIds.size})</>
            )}
          </button>
        )}
      </div>

      {/* 列表 */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-200 border-t-brand-500" />
          </div>
        ) : videos.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-4 py-12 text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400">
              <PlayIcon className="w-5 h-5" />
            </div>
            <p className="mt-3 text-[13px] text-slate-500">暂无视频</p>
            <p className="text-[11px] text-slate-400">选择账号后点击刷新按钮爬取</p>
          </div>
        ) : (
          <div className="divide-y divide-slate-100">
            {videos.map((v) => {
              const checked = selectedIds.has(v.id);
              return (
                <div
                  key={v.id}
                  className={`flex items-start gap-3 px-4 py-3 transition hover:bg-slate-50 ${
                    checked ? "bg-brand-50/50" : ""
                  }`}
                >
                  {/* 复选框 */}
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => onToggleSelect(v.id)}
                    className="mt-0.5 h-4 w-4 cursor-pointer rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                  />

                  {/* 封面 */}
                  {v.cover_url ? (
                    <img
                      src={v.cover_url}
                      alt={v.title || ""}
                      className="h-12 w-16 shrink-0 rounded-lg object-cover"
                    />
                  ) : (
                    <div className="flex h-12 w-16 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-300">
                      <PlayIcon className="w-4 h-4" />
                    </div>
                  )}

                  {/* 内容 */}
                  <div className="min-w-0 flex-1">
                    <p className="line-clamp-2 text-[13px] font-medium text-slate-900">
                      {v.title || "(无标题)"}
                    </p>
                    <div className="mt-1 flex items-center gap-3 text-[11px] text-slate-500">
                      <span className="flex items-center gap-1">
                        <HeartIcon className="h-3 w-3 text-rose-400" />
                        {formatNumber(v.like_count)}
                      </span>
                      <span className="flex items-center gap-1">
                        <ChatIcon className="h-3 w-3 text-blue-400" />
                        {formatNumber(v.comment_count)}
                      </span>
                      <span className="flex items-center gap-1">
                        <ShareIcon className="h-3 w-3 text-emerald-400" />
                        {formatNumber(v.share_count)}
                      </span>
                      <span className="text-slate-400">{formatDate(v.published_at)}</span>
                      <span className="text-slate-400">·</span>
                      <span className="font-medium text-brand-600">
                        互动 {engagementRate(v)}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
