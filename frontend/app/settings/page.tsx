"use client";

import { useEffect, useState } from "react";

// ---- 类型 ----
interface AIConfig {
  id: string;
  provider: string;
  label: string;
  api_key: string; // 脱敏后的 key
  base_url: string | null;
  model: string;
  is_active: boolean;
  priority: number;
  created_at: string | null;
  updated_at: string | null;
}

const PROVIDERS = [
  { value: "deepseek", label: "DeepSeek", defaultModel: "deepseek-chat", defaultUrl: "https://api.deepseek.com/v1" },
  { value: "claude", label: "Claude (Anthropic)", defaultModel: "claude-3-5-sonnet-20241022", defaultUrl: "" },
  { value: "openai", label: "OpenAI", defaultModel: "gpt-4o", defaultUrl: "https://api.openai.com/v1" },
  { value: "glm", label: "GLM (智谱)", defaultModel: "glm-4", defaultUrl: "https://open.bigmodel.cn/api/paas/v4" },
];

export default function SettingsPage() {
  const [configs, setConfigs] = useState<AIConfig[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // 新增表单
  const [provider, setProvider] = useState("deepseek");
  const [label, setLabel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [model, setModel] = useState("");

  const fetchConfigs = async () => {
    try {
      const res = await fetch("/api/config");
      const data = await res.json();
      setConfigs(data || []);
    } catch {
      setError("加载配置失败");
    }
  };

  useEffect(() => {
    fetchConfigs();
  }, []);

  // 选择供应商时自动填充默认值
  const handleProviderChange = (value: string) => {
    setProvider(value);
    const p = PROVIDERS.find((x) => x.value === value);
    if (p) {
      setLabel(p.label);
      setModel(p.defaultModel);
      setBaseUrl(p.defaultUrl);
    }
  };

  // 新增配置
  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    try {
      const res = await fetch("/api/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider,
          label: label || PROVIDERS.find((p) => p.value === provider)?.label || provider,
          api_key: apiKey,
          base_url: baseUrl || null,
          model: model || PROVIDERS.find((p) => p.value === provider)?.defaultModel || "",
          is_active: true,
          priority: configs.length,
        }),
      });
      if (!res.ok) {
        const msg = await res.json().catch(() => ({}));
        throw new Error(msg.detail || `请求失败 (${res.status})`);
      }
      setSuccess("配置添加成功");
      setApiKey("");
      setLabel("");
      setBaseUrl("");
      setModel("");
      await fetchConfigs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "未知错误");
    } finally {
      setLoading(false);
    }
  };

  // 切换启用状态
  const toggleActive = async (config: AIConfig) => {
    try {
      const res = await fetch(`/api/config/${config.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active: !config.is_active }),
      });
      if (!res.ok) throw new Error("更新失败");
      await fetchConfigs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "未知错误");
    }
  };

  // 删除配置
  const handleDelete = async (id: string) => {
    if (!confirm("确定删除此配置?")) return;
    try {
      const res = await fetch(`/api/config/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("删除失败");
      await fetchConfigs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "未知错误");
    }
  };

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <header className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900">AI 配置</h1>
          <p className="text-sm text-slate-500">管理 AI 供应商的 API 密钥与模型, 分析时按优先级依次尝试</p>
        </div>
        <a
          href="/"
          className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 transition hover:bg-slate-50"
        >
          返回首页
        </a>
      </header>

      {error && (
        <div className="mb-6 rounded-lg bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>
      )}
      {success && (
        <div className="mb-6 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{success}</div>
      )}

      {/* 新增配置表单 */}
      <form
        onSubmit={handleAdd}
        className="mb-8 rounded-2xl border border-slate-200 bg-white p-6"
      >
        <h2 className="mb-4 text-sm font-semibold text-slate-700">添加 AI 供应商</h2>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">供应商</label>
            <select
              value={provider}
              onChange={(e) => handleProviderChange(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand"
            >
              {PROVIDERS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">显示名称</label>
            <input
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="如: DeepSeek 主力"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">API Key</label>
            <input
              type="password"
              required
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-..."
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">模型名</label>
            <input
              type="text"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="如: deepseek-chat"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="mb-1 block text-xs font-medium text-slate-500">接口地址 (可选)</label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="留空使用默认地址"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand"
            />
          </div>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="mt-4 rounded-lg bg-brand px-5 py-2 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50"
        >
          {loading ? "添加中..." : "添加配置"}
        </button>
      </form>

      {/* 已有配置列表 */}
      <div className="rounded-2xl border border-slate-200 bg-white p-6">
        <h2 className="mb-4 text-sm font-semibold text-slate-700">
          已配置供应商 ({configs.length})
        </h2>
        {configs.length === 0 ? (
          <p className="text-sm text-slate-400">
            暂无配置, 添加一个 AI 供应商后系统将自动使用它进行情报分析。
            <br />
            如果数据库未配置, 系统会使用环境变量中的配置作为 fallback。
          </p>
        ) : (
          <div className="space-y-3">
            {configs.map((c, i) => (
              <div
                key={c.id}
                className="flex items-center justify-between rounded-lg border border-slate-200 px-4 py-3"
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-slate-400">#{i + 1}</span>
                    <span className="text-sm font-semibold text-slate-800">{c.label}</span>
                    <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-500">
                      {c.provider}
                    </span>
                    {c.is_active ? (
                      <span className="rounded bg-emerald-100 px-2 py-0.5 text-xs text-emerald-700">启用</span>
                    ) : (
                      <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-400">禁用</span>
                    )}
                  </div>
                  <div className="mt-1 text-xs text-slate-400">
                    模型: {c.model} | Key: {c.api_key}
                    {c.base_url && ` | 接口: ${c.base_url}`}
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => toggleActive(c)}
                    className="rounded border border-slate-300 px-3 py-1 text-xs text-slate-600 transition hover:bg-slate-50"
                  >
                    {c.is_active ? "禁用" : "启用"}
                  </button>
                  <button
                    onClick={() => handleDelete(c.id)}
                    className="rounded border border-rose-300 px-3 py-1 text-xs text-rose-600 transition hover:bg-rose-50"
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
