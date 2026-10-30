import * as React from "react";
import { cn } from "../../lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, ...props }, ref) => (
    <input
      ref={ref}
      className={cn(
        "w-full rounded-xl border border-white/10 bg-ink-800/80 px-3 py-2 text-sm text-slate-100",
        "placeholder:text-slate-500 outline-none transition",
        "focus:border-neon-cyan/60 focus:shadow-glow",
        className
      )}
      {...props}
    />
  )
);
Input.displayName = "Input";
