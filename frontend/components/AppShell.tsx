"use client";

// AppShell.tsx — Premium Enterprise SaaS 外壳: 固定侧边栏 + 可滚动主内容区
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { useI18n, LanguageSwitcher } from "@/lib/i18n";

const NAV_KEYS = [
  { href: "/", key: "dashboard", icon: "dashboard" },
  { href: "/intelligence", key: "intelligence", icon: "intelligence" },
  { href: "/compare", key: "compare", icon: "compare" },
  { href: "/knowledge", key: "knowledge", icon: "knowledge" },
  { href: "/settings", key: "settings", icon: "settings" },
] as const;

function NavIcon({ name }: { name: string }) {
  const cls = "h-[18px] w-[18px] shrink-0";
  const p = {
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.8,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
  };
  switch (name) {
    case "dashboard":
      return (
        <svg className={cls} viewBox="0 0 24 24" {...p}>
          <rect x="3" y="3" width="7" height="7" rx="1.5" />
          <rect x="14" y="3" width="7" height="7" rx="1.5" />
          <rect x="3" y="14" width="7" height="7" rx="1.5" />
          <rect x="14" y="14" width="7" height="7" rx="1.5" />
        </svg>
      );
    case "intelligence":
      return (
        <svg className={cls} viewBox="0 0 24 24" {...p}>
          <path d="M3 12h4l2-6 4 12 2-6h6" />
        </svg>
      );
    case "compare":
      return (
        <svg className={cls} viewBox="0 0 24 24" {...p}>
          <rect x="3" y="4" width="7" height="16" rx="1.5" />
          <rect x="14" y="4" width="7" height="16" rx="1.5" />
        </svg>
      );
    case "knowledge":
      return (
        <svg className={cls} viewBox="0 0 24 24" {...p}>
          <path d="M4 5.5A2.5 2.5 0 0 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z" />
          <path d="M4 20.5A2.5 2.5 0 0 1 6.5 18H20" />
        </svg>
      );
    case "settings":
      return (
        <svg className={cls} viewBox="0 0 24 24" {...p}>
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1-1.51 1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09a1.65 1.65 0 0 0 1.51-1 1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33h.01a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82v.01a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
        </svg>
      );
    default:
      return null;
  }
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { t } = useI18n();

  const isActive = (href: string) =>
    href === "/" ? pathname === "/" : pathname.startsWith(href);

  return (
    <div className="relative z-10 flex h-screen overflow-hidden bg-slate-50">
      {/* Mobile top bar */}
      <div className="fixed inset-x-0 top-0 z-30 flex h-14 items-center gap-3 border-b border-slate-200 bg-white px-4 md:hidden">
        <button
          onClick={() => setOpen(true)}
          aria-label={t("common.openMenu")}
          className="rounded-md p-1.5 text-slate-600 hover:bg-slate-100"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <span className="text-sm font-semibold text-slate-900">{t("common.brand")}</span>
      </div>

      {/* Mobile overlay */}
      {open && (
        <div
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-40 bg-slate-900/50 backdrop-blur-sm md:hidden"
        />
      )}

      {/* Sidebar — light theme to match content area */}
      <aside
        className={`fixed left-0 top-0 z-50 flex h-full w-60 flex-col border-r border-slate-200 bg-white text-slate-700 transition-transform duration-200 md:static md:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo */}
        <div className="flex h-16 shrink-0 items-center gap-3 border-b border-slate-100 px-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 shadow-lg shadow-indigo-200">
            <svg className="h-5 w-5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2l2.4 7.4H22l-6 4.4 2.3 7.2-6.3-4.6L5.7 21l2.3-7.2-6-4.4h7.6z" />
            </svg>
          </div>
          <div className="min-w-0">
            <p className="truncate text-sm font-bold text-slate-900">{t("common.brandShort")}</p>
            <p className="truncate text-[11px] text-slate-400">{t("common.brandSub")}</p>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-3 py-4">
          <p className="mb-2 px-3 text-[10px] font-medium uppercase tracking-wider text-slate-400">
            {t("common.nav")}
          </p>
          <div className="space-y-1">
            {NAV_KEYS.map((item) => {
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={() => setOpen(false)}
                  className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition ${
                    active
                      ? "bg-indigo-50 text-indigo-700"
                      : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                  }`}
                >
                  <NavIcon name={item.icon} />
                  <span>{t(`common.nav_${item.key}`)}</span>
                </Link>
              );
            })}
          </div>
        </nav>

        {/* Language Switcher */}
        <div className="shrink-0 border-t border-slate-100 px-5 py-3">
          <LanguageSwitcher />
        </div>

        {/* Version info */}
        <div className="shrink-0 px-5 pb-4">
          <p className="text-[11px] font-medium text-slate-400">{t("common.brand")}</p>
          <p className="mt-0.5 text-[11px] text-slate-300">{t("common.version")}</p>
        </div>
      </aside>

      {/* Main content */}
      <main
        className="premium-scroll flex-1 overflow-y-auto bg-slate-50 pt-14 md:pt-0"
        style={{ colorScheme: "light" }}
      >
        <div className="mx-auto max-w-7xl px-6 py-8">{children}</div>
      </main>
    </div>
  );
}
