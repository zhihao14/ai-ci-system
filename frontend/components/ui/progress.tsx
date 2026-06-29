// components/ui/progress.tsx — 渐变进度条
"use client";

import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

interface ProgressProps {
  value: number; // 0-100
  className?: string;
  color?: string; // CSS gradient
  animated?: boolean;
}

export function Progress({
  value,
  className,
  color = "linear-gradient(90deg, #6366f1, #8b5cf6)",
  animated = true,
}: ProgressProps) {
  const pct = Math.min(100, Math.max(0, value));

  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-white/5", className)}>
      <motion.div
        className="h-full rounded-full"
        style={{ background: color }}
        initial={animated ? { width: 0 } : false}
        animate={{ width: `${pct}%` }}
        transition={{ duration: 0.8, ease: "easeOut" }}
      />
    </div>
  );
}
