import { useState } from "react";
import { motion } from "framer-motion";
import { ScrollText, ChevronRight, EyeOff } from "lucide-react";
import { Card, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { cn, clip } from "../lib/utils";
import type { ZAction } from "../ws";

export interface LogItem {
  step: number;
  action: ZAction;
  observation_summary: string;
}

interface Props {
  logs: LogItem[];
}

const ACTION_META: Record<string, { label: string; cls: string }> = {
  click: { label: "点击", cls: "text-neon-cyan" },
  type: { label: "输入", cls: "text-neon-blue" },
  goto: { label: "跳转", cls: "text-indigo-300" },
  navigate: { label: "跳转", cls: "text-indigo-300" },
  scroll: { label: "滚动", cls: "text-indigo-300" },
  submit: { label: "提交", cls: "text-func-amber" },
  wait: { label: "等待", cls: "text-slate-400" },
  shell: { label: "命令", cls: "text-emerald-300" },
  video: { label: "视频", cls: "text-emerald-300" },
  tool_task: { label: "外部工具", cls: "text-emerald-300" },
  fill_credential: { label: "凭据注入", cls: "text-neon-cyan" },
  done: { label: "完成", cls: "text-func-green" },
};

export default function LogFeed({ logs }: Props) {
  const [open, setOpen] = useState<number | null>(null);

  return (
    <Card className="h-full">
      <CardHeader className="justify-between">
        <div className="flex items-center gap-2">
          <ScrollText className="w-4 h-4 text-neon-cyan" />
          <CardTitle>动作日志</CardTitle>
        </div>
        <span className="text-[11px] text-slate-400">{logs.length} 步</span>
      </CardHeader>

      <div className="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-1.5">
        {logs.length === 0 && (
          <p className="text-xs text-slate-500 px-1">
            每一步动作（含目标、理由与脱敏后的值）都会逐条出现在这里。
          </p>
        )}
        {logs.map((l, i) => {
          const meta = ACTION_META[l.action.action] ?? {
            label: l.action.action,
            cls: "text-slate-300",
          };
          const expanded = open === i;
          return (
            <motion.div
              key={i}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.2 }}
              className="rounded-lg bg-white/5 border border-white/10 overflow-hidden"
            >
              <button
                onClick={() => setOpen(expanded ? null : i)}
                className="w-full flex items-center gap-1.5 text-left px-2.5 py-1.5 cursor-pointer hover:bg-white/5 transition"
              >
                <span className="text-[10px] text-slate-500 font-mono">#{l.step}</span>
                <span className={cn("text-xs font-semibold", meta.cls)}>{meta.label}</span>
                {l.action.target && (
                  <span className="text-[11px] text-slate-400 truncate">→ {l.action.target}</span>
                )}
                <ChevronRight
                  className={cn(
                    "w-3.5 h-3.5 text-slate-500 ml-auto shrink-0 transition-transform",
                    expanded && "rotate-90"
                  )}
                />
              </button>
              {expanded && (
                <div className="px-2.5 pb-2 text-[11px] text-slate-400 space-y-1 border-t border-white/5 pt-1.5">
                  {l.action.reason && <div>理由：{l.action.reason}</div>}
                  {l.action.value && (
                    <div className="flex items-center gap-1">
                      <EyeOff className="w-3 h-3 text-func-amber" />
                      <span className="text-func-amber">值（已脱敏）：</span>
                      {clip(String(l.action.value), 60)}
                    </div>
                  )}
                  {l.action.thought && <div className="text-slate-500">思考：{clip(l.action.thought, 160)}</div>}
                  <div className="text-slate-500">观察：{clip(l.observation_summary, 220)}</div>
                </div>
              )}
            </motion.div>
          );
        })}
      </div>

      {logs.length > 0 && (
        <div className="px-3 pb-2">
          <Button variant="ghost" size="xs" onClick={() => setOpen(null)}>
            折叠全部
          </Button>
        </div>
      )}
    </Card>
  );
}
