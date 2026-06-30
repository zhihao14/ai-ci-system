"use client";

// lib/i18n.tsx — Internationalization context provider
// Supports: zh (Simplified Chinese, default), en (English)
// All UI text is read from /locales/zh.json and /locales/en.json

import React, { createContext, useContext, useState, useCallback, useEffect } from "react";
import zh from "../locales/zh.json";
import en from "../locales/en.json";

export type Locale = "zh" | "en";

const dictionaries: Record<Locale, Record<string, unknown>> = {
  zh: zh as Record<string, unknown>,
  en: en as Record<string, unknown>,
};

// ---- Nested key lookup: "dashboard.title" → dict.dashboard.title ----
function resolve(dict: Record<string, unknown>, key: string): string {
  const parts = key.split(".");
  let cur: unknown = dict;
  for (const p of parts) {
    if (cur && typeof cur === "object" && p in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[p];
    } else {
      return key; // fallback: return the key itself
    }
  }
  return typeof cur === "string" ? cur : key;
}

// ---- Interpolation: "Found {count} results" with {count: 5} → "Found 5 results" ----
function interpolate(str: string, vars?: Record<string, string | number>): string {
  if (!vars) return str;
  return str.replace(/\{(\w+)\}/g, (_, k) => String(vars[k] ?? `{${k}}`));
}

// ---- Context ----
interface I18nContextValue {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}

const I18nContext = createContext<I18nContextValue | null>(null);

const STORAGE_KEY = "ai-ci-locale";

export function I18nProvider({ children }: { children: React.ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>("zh");

  // Load saved locale from localStorage on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY) as Locale | null;
      if (saved === "zh" || saved === "en") {
        setLocaleState(saved);
      }
    } catch {
      // localStorage not available (SSR or privacy mode)
    }
  }, []);

  // Update <html lang="..."> when locale changes
  useEffect(() => {
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  }, [locale]);

  const setLocale = useCallback((l: Locale) => {
    setLocaleState(l);
    try {
      localStorage.setItem(STORAGE_KEY, l);
    } catch {
      // ignore
    }
  }, []);

  const t = useCallback(
    (key: string, vars?: Record<string, string | number>) => {
      const dict = dictionaries[locale];
      const str = resolve(dict, key);
      return interpolate(str, vars);
    },
    [locale]
  );

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

// ---- Hook ----
export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used within I18nProvider");
  }
  return ctx;
}

// ---- Language Switcher Component ----
export function LanguageSwitcher({ className = "" }: { className?: string }) {
  const { locale, setLocale } = useI18n();

  return (
    <div className={`flex items-center gap-1 rounded-lg bg-slate-100 p-0.5 ${className}`}>
      <button
        onClick={() => setLocale("zh")}
        className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
          locale === "zh"
            ? "bg-white text-slate-900 shadow-sm"
            : "text-slate-500 hover:text-slate-700"
        }`}
      >
        中文
      </button>
      <button
        onClick={() => setLocale("en")}
        className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
          locale === "en"
            ? "bg-white text-slate-900 shadow-sm"
            : "text-slate-500 hover:text-slate-700"
        }`}
      >
        EN
      </button>
    </div>
  );
}
