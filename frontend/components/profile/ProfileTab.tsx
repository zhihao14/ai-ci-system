// components/profile/ProfileTab.tsx — 个人资料编辑
"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";

export default function ProfileTab() {
  const { profile, session, refreshProfile } = useAuth();
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({
    username: profile?.username || "",
    full_name: profile?.full_name || "",
    avatar_url: profile?.avatar_url || "",
    bio: profile?.bio || "",
  });
  const [apiKey, setApiKey] = useState(profile?.api_key || "");
  const [regenerating, setRegenerating] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch("/be/auth/profile", {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${session?.access_token}`,
        },
        body: JSON.stringify(form),
      });
      await refreshProfile();
      setEditing(false);
    } finally {
      setSaving(false);
    }
  };

  const handleRegenKey = async () => {
    if (!confirm("确定重新生成 API Key? 旧 Key 将失效。")) return;
    setRegenerating(true);
    try {
      const res = await fetch("/be/auth/profile/api-key", {
        method: "POST",
        headers: { Authorization: `Bearer ${session?.access_token}` },
      });
      const data = await res.json();
      setApiKey(data.api_key);
    } finally {
      setRegenerating(false);
    }
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(apiKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const inputClass =
    "w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-100";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-900">个人资料</h3>
        {!editing ? (
          <button
            onClick={() => setEditing(true)}
            className="text-sm text-brand-600 hover:underline"
          >
            编辑
          </button>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={() => setEditing(false)}
              className="rounded-lg border border-slate-200 px-3 py-1 text-sm text-slate-600 hover:bg-slate-50"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="rounded-lg bg-brand-600 px-3 py-1 text-sm text-white hover:bg-brand-700 disabled:opacity-50"
            >
              {saving ? "保存中..." : "保存"}
            </button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="mb-1 block text-xs text-slate-400">用户名</label>
          {editing ? (
            <input
              value={form.username}
              onChange={(e) => setForm({ ...form, username: e.target.value })}
              className={inputClass}
            />
          ) : (
            <p className="text-sm text-slate-700">{profile?.username || "-"}</p>
          )}
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">显示名</label>
          {editing ? (
            <input
              value={form.full_name}
              onChange={(e) => setForm({ ...form, full_name: e.target.value })}
              className={inputClass}
            />
          ) : (
            <p className="text-sm text-slate-700">{profile?.full_name || "-"}</p>
          )}
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">头像 URL</label>
          {editing ? (
            <input
              value={form.avatar_url}
              onChange={(e) => setForm({ ...form, avatar_url: e.target.value })}
              className={inputClass}
            />
          ) : (
            <p className="truncate text-sm text-slate-700">
              {profile?.avatar_url || "-"}
            </p>
          )}
        </div>
        <div>
          <label className="mb-1 block text-xs text-slate-400">简介</label>
          {editing ? (
            <textarea
              value={form.bio}
              onChange={(e) => setForm({ ...form, bio: e.target.value })}
              rows={2}
              className={inputClass}
            />
          ) : (
            <p className="text-sm text-slate-700">{profile?.bio || "-"}</p>
          )}
        </div>
      </div>

      {/* API Key */}
      <div className="border-t border-slate-100 pt-6">
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-900">API Key</h3>
          <button
            onClick={handleRegenKey}
            disabled={regenerating}
            className="text-sm text-brand-600 hover:underline disabled:opacity-50"
          >
            {regenerating ? "生成中..." : "重新生成"}
          </button>
        </div>
        <p className="mb-2 text-xs text-slate-400">
          用于调用后端 API (X-API-Key header), 请妥善保管
        </p>
        <div className="flex items-center gap-2">
          <code className="flex-1 truncate rounded-lg bg-slate-900 px-3 py-2 text-xs text-green-400">
            {apiKey || "未生成"}
          </code>
          {apiKey && (
            <button
              onClick={handleCopy}
              className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50"
            >
              {copied ? "已复制" : "复制"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
