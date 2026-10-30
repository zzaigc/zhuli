import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

/** shadcn 约定的类名合并工具（clsx + tailwind-merge）。 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** 把秒级时间戳格式化为 HH:MM:SS。 */
export function fmtTime(ts: number) {
  const d = new Date(ts);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

/** 截断长文本，避免撑破面板布局。 */
export function clip(text: string, max = 160) {
  return text.length > max ? text.slice(0, max) + "…" : text;
}
