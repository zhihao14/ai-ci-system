// components/ui/badge.tsx — shadcn/ui Badge
import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "bg-brand-500/20 text-brand-300 border border-brand-500/30",
        success: "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30",
        warning: "bg-amber-500/15 text-amber-300 border border-amber-500/30",
        danger: "bg-red-500/15 text-red-300 border border-red-500/30",
        glass: "bg-white/5 text-slate-300 border border-white/10",
        gradient:
          "bg-gradient-to-r from-brand-500/20 to-purple-500/20 text-purple-200 border border-purple-500/30",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { Badge, badgeVariants };
