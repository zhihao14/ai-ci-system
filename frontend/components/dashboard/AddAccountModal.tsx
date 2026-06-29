"use client";

// AddAccountModal.tsx - 添加账号弹窗
import { useState } from "react";
import { CloseIcon } from "./Icons";

export default function AddAccountModal({
  open,
  onClose,
  onAdd,
}: {
  open: boolean;
  onClose: () => void;
  onAdd: (data: {
    platform: string;
    platform_uid: string;
    name: string;
    follower_count: number;
  }) => Promise<void>;
}) {
  const [platform, setPlatform] = useState("douyin");
  const [platform_uid, setPlatformUid] = useState("");
  const [name, setName] = useState("");
  const [follower_count, setFollowers] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!platform_uid.trim() || !name.trim()) {
      setError("账号 UID 和名称为必填项");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await onAdd({
        platform,
        platform_uid: platform_uid.trim(),
        name: name.trim(),
        follower_count: Number(follower_count) || 0,
      });
      // 重置
      setPlatformUid("");
      setName("");
      setFollowers(0);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "添加失败");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* 遮罩 */}
      <div
        className="absolute inset-0 bg-slate-900/20 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* 弹窗 */}
      <div className="relative w-full max-w-md rounded-xl border border-slate-200 bg-white p-5 shadow-xl">
        {/* 头部 */}
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-[15px] font-semibold text-slate-900">添加竞争对手账号</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          >
            <CloseIcon className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          {/* 平台 */}
          <div>
            <label className="mb-1 block text-[12px] font-medium text-slate-600">平台</label>
            <select
              value={platform}
              onChange={(e) => setPlatform(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-[13px] outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            >
              <option value="douyin">抖音</option>
              <option value="tiktok">TikTok</option>
              <option value="youtube">YouTube</option>
              <option value="bilibili">哔哩哔哩</option>
            </select>
          </div>

          {/* 账号 UID */}
          <div>
            <label className="mb-1 block text-[12px] font-medium text-slate-600">
              账号 UID <span className="text-slate-400">(sec_user_id 或用户名)</span>
            </label>
            <input
              type="text"
              value={platform_uid}
              onChange={(e) => setPlatformUid(e.target.value)}
              placeholder="MS4wLjABAAAA..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-[13px] outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            />
          </div>

          {/* 名称 */}
          <div>
            <label className="mb-1 block text-[12px] font-medium text-slate-600">名称</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="某品牌官方号"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-[13px] outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            />
          </div>

          {/* 粉丝数 */}
          <div>
            <label className="mb-1 block text-[12px] font-medium text-slate-600">
              粉丝数 <span className="text-slate-400">(可选)</span>
            </label>
            <input
              type="number"
              value={follower_count || ""}
              onChange={(e) => setFollowers(Number(e.target.value))}
              placeholder="0"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-[13px] outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500"
            />
          </div>

          {error && (
            <p className="rounded-lg bg-rose-50 px-3 py-2 text-[12px] text-rose-600">{error}</p>
          )}

          {/* 按钮 */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-3 py-2 text-[13px] font-medium text-slate-600 transition hover:bg-slate-100"
            >
              取消
            </button>
            <button
              type="submit"
              disabled={submitting}
              className="rounded-lg bg-brand-600 px-4 py-2 text-[13px] font-medium text-white transition hover:bg-brand-700 disabled:opacity-50"
            >
              {submitting ? "添加中..." : "添加账号"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
