// app/(auth)/layout.tsx — 认证页面布局 (登录/注册)
import { Inter } from "next/font/google";
import { AuthProvider } from "@/lib/auth-context";
import "../globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata = {
  title: "AI 竞争情报系统 - 登录",
};

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={inter.variable}>
      <body className="font-sans min-h-screen bg-gradient-to-br from-slate-50 to-slate-100">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
