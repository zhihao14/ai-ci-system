// dashboard/layout.tsx - Dashboard 布局 (加载 Inter 字体)
import { Inter } from "next/font/google";
import "../globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });

export const metadata = {
  title: "CI Insight - AI 竞争情报系统",
  description: "竞争对手视频情报与爆款分析平台",
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className={inter.variable}>
      <body className="font-sans">{children}</body>
    </html>
  );
}
