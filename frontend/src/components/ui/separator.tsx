import * as React from "react";
import { cn } from "../../lib/utils";

interface Props {
  className?: string;
  orientation?: "horizontal" | "vertical";
}

export function Separator({ className, orientation = "horizontal" }: Props) {
  return (
    <div
      role="separator"
      className={cn(
        "bg-white/10",
        orientation === "horizontal" ? "h-px w-full" : "w-px h-full",
        className
      )}
    />
  );
}
