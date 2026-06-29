"use client";

// AccountList.tsx - 账号列表 + 添加按钮
import type { Account } from "@/app/dashboard/types";
import { formatNumber, platformColor } from "@/app/dashboard/lib";
import { PlusIcon, RefreshIcon } from "./Icons";

export default function AccountList({
  accounts,
  activeId,
  onSelect,
  onAdd,
  onCrawl,
  crawling,
}: {
  accounts: Account[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onAdd: () => void;
  onCrawl: (id: string) => void;
  crawling: boolean;
}) {
  return (
    <div className="flex h-full flex-col">
      {/* 头部 */}
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="text-[13px] font-semibold text-slate-700">
          账号列表
          <span className="ml-1.5 text-slate-400">({accounts.length})</span>
        </h2>
        <button
          onClick={onAdd}
          className="flex items-center gap-1 rounded-lg bg-brand-600 px-2.5 py-1 text-[12px] font-medium text-white transition hover:bg-brand-700"
        >
          <PlusIcon className="w-3.5 h-3.5" />
          添加
        </button>
      </div>

      {/* 列表 */}
      <div className="flex-1 overflow-y-auto">
        {accounts.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center px-4 py-12 text-center">
            <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-100 text-slate-400">
              <PlusIcon className="w-5 h-5" />
            </div>
            <p className="mt-3 text-[13px] text-slate-500">还没有账号</p>
            <p className="text-[11px] text-slate-400">点击右上角"添加"开始</p>
          </div>
        ) : (
          <div className="px-2 py-1">
            {accounts.map((acc) => {
              const isActive = acc.id === activeId;
              return (
                <div
                  key={acc.id}
                  className={`group cursor-pointer rounded-lg border px-3 py-2.5 transition ${
                    isActive
                      ? "border-brand-200 bg-brand-50"
                      : "border-transparent hover:border-slate-200 hover:bg-slate-50"
                  }`}
                  onClick={() => onSelect(acc.id)}
                >
                  <div className="flex items-center gap-2.5">
                    {/* 头像 */}
                    {acc.avatar_url ? (
                      <img
                        src={acc.avatar_url}
                        alt={acc.name}
                        className="h-8 w-8 shrink-0 rounded-full object-cover"
                      />
                    ) : (
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-[12px] font-medium text-slate-600">
                        {acc.name.slice(0, 1)}
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-1.5">
                        <p className="truncate text-[13px] font-medium text-slate-900">{acc.name}</p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className={`rounded px-1 py-0.5 text-[9px] font-medium uppercase ${platformColor(acc.platform)}`}>
                          {acc.platform}
                        </span>
                        <span className="text-[11px] text-slate-400">
                          {formatNumber(acc.follower_count)} 粉丝
                        </span>
                      </div>
                    </div>
                    {/* 爬虫按钮 */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onCrawl(acc.id);
                      }}
                      disabled={crawling}
                      className="shrink-0 rounded-md p-1.5 text-slate-400 opacity-0 transition hover:bg-white hover:text-brand-600 group-hover:opacity-100 disabled:opacity-50"
                      title="爬取视频"
                    >
                      <RefreshIcon className={`w-3.5 h-3.5 ${crawling ? "animate-spin" : ""}`} />
                    </button>
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
