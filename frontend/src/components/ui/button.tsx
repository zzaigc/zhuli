import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon-cyan/60 disabled:pointer-events-none disabled:opacity-40 cursor-pointer",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-neon-cyan to-neon-blue text-ink-900 shadow-glow hover:shadow-glow-strong",
        indigo:
          "bg-gradient-to-r from-neon-blue to-neon-indigo text-white shadow-glow hover:shadow-glow-strong",
        destructive:
          "bg-func-red/20 text-func-red border border-func-red/40 hover:bg-func-red/30",
        outline:
          "border border-white/15 bg-white/5 text-slate-200 hover:bg-white/10 hover:border-neon-cyan/40",
        ghost: "text-slate-300 hover:bg-white/10 hover:text-neon-cyan",
        danger:
          "border border-func-red/40 text-func-red hover:bg-func-red/10",
        warn: "border border-func-amber/40 text-func-amber hover:bg-func-amber/10",
        ok: "border border-func-green/40 text-func-green hover:bg-func-green/10",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-11 rounded-xl px-6",
        icon: "h-9 w-9",
        xs: "h-7 rounded-md px-2 text-[11px]",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, ...props }, ref) => (
    <button
      ref={ref}
      className={cn(buttonVariants({ variant, size }), className)}
      {...props}
    />
  )
);
Button.displayName = "Button";

export { buttonVariants };
