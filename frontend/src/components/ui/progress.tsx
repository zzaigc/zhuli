import * as React from "react";
import { cn } from "../../lib/utils";

interface Props {
  value: number; // 0-100
  className?: string;
  barClassName?: string;
}

export function Progress({ value, className, barClassName }: Props) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-white/10", className)}>
      <div
        className={cn(
          "h-full rounded-full bg-gradient-to-r from-neon-cyan to-neon-blue transition-all duration-500",
          barClassName
        )}
        style={{ width: `${v}%` }}
      />
    </div>
  );
}
