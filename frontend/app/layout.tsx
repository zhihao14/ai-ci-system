import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { AuthProvider } from "@/lib/auth-context";
import { I18nProvider } from "@/lib/i18n";
import AppShell from "@/components/AppShell";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata: Metadata = {
  title: "AI Competitive Intelligence",
  description: "Premium Enterprise SaaS — Competitive Intelligence Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={inter.variable}>
      <body className="font-sans">
        <I18nProvider>
          <AuthProvider>
            <AppShell>{children}</AppShell>
          </AuthProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
