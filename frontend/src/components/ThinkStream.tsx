import { Brain, Compass, Lightbulb, Eye } from "lucide-react";
import { Badge } from "./ui/badge";
import { clip } from "../lib/utils";
import type { ThinkEvent } from "../ws";

export interface Thought {
  stage: ThinkEvent["stage"];
  text: string;
  ts: number;
}

interface Props {
  thoughts: Thought[];
}

const STAGE_META: Record<ThinkEvent["stage"], { label: string; icon: typeof Brain; cls: string; variant: "default" | "indigo" | "warn" | "success" }> = {
  plan: { label: "规划", icon: Compass, cls: "text-neon-indigo", variant: "indigo" },
  decide: { label: "决策", icon: Lightbulb, cls: "text-neon-cyan", variant: "default" },
  reflect: { label: "反思", icon: Eye, cls: "text-func-amber", variant: "warn" },
};

export default function ThinkStream({ thoughts }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-white/10 flex items-center gap-2">
        <Brain className="w-4 h-4 text-neon-indigo" />
        <span className="text-sm font-semibold text-slate-100">思维链</span>
        <span className="ml-auto text-[11px] text-slate-400">{thoughts.length} 条</span>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-2">
        {thoughts.length === 0 && (
          <p className="text-xs text-slate-500 px-1">
            规划、决策、反思三个阶段的内部推理会实时流到这里 —— 你能看到 AI 到底在想什么。
          </p>
        )}
        {thoughts.map((t, i) => {
          const meta = STAGE_META[t.stage] ?? STAGE_META.decide;
          const Icon = meta.icon;
          return (
            <div
              key={i}
              className="rounded-xl bg-white/5 border border-white/10 px-3 py-2 animate-floatIn"
            >
              <div className="flex items-center gap-1.5 mb-1">
                <Icon className={`w-3.5 h-3.5 ${meta.cls}`} />
                <Badge variant={meta.variant}>{meta.label}</Badge>
                <span className="text-[10px] text-slate-500 ml-auto">
                  {new Date(t.ts).toLocaleTimeString()}
                </span>
              </div>
              <p className="text-[11px] text-slate-300 leading-relaxed whitespace-pre-wrap break-words">
                {clip(t.text, 600)}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}
