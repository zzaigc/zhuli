import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold tracking-wide transition-colors",
  {
    variants: {
      variant: {
        default: "border-neon-cyan/40 bg-neon-cyan/10 text-neon-cyan",
        indigo: "border-neon-indigo/40 bg-neon-indigo/10 text-indigo-300",
        success: "border-func-green/40 bg-func-green/10 text-func-green",
        danger: "border-func-red/40 bg-func-red/10 text-func-red",
        warn: "border-func-amber/40 bg-func-amber/10 text-func-amber",
        outline: "border-white/15 bg-white/5 text-slate-300",
      },
    },
    defaultVariants: { variant: "default" },
  }
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}

export { badgeVariants };
