import { CheckCircle2, Circle, BrainCircuit, Target, ShieldCheck } from "lucide-react";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { Progress } from "./ui/progress";
import { cn } from "../lib/utils";

export interface PlanState {
  subtasks: string[];
  current: string;
  done: string[];
  verification?: string[];
}

interface Props {
  plan: PlanState | null;
  reflection: { status: string; reason: string } | null;
}

const REFLECTION_META: Record<string, { label: string; variant: "success" | "warn" | "danger" | "default" }> = {
  continue: { label: "继续执行", variant: "default" },
  replan: { label: "触发重规划", variant: "warn" },
  done: { label: "目标达成", variant: "success" },
  escalate: { label: "升级求助", variant: "danger" },
};

export default function PlanPanel({ plan, reflection }: Props) {
  if (!plan) {
    return (
      <Card className="p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-200">
          <BrainCircuit className="w-4 h-4 text-neon-indigo" />
          任务计划
        </div>
        <p className="mt-2 text-xs text-slate-400 leading-relaxed">
          提交目标后，规划智能体会把目标拆解为可验证的子任务，并在右侧「思维链」中展示它的推理过程。
        </p>
      </Card>
    );
  }

  const total = plan.subtasks.length || 1;
  const pct = (plan.done.length / total) * 100;
  const curIdx = plan.subtasks.indexOf(plan.current);
  const verification =
    plan.verification && curIdx >= 0 && curIdx < plan.verification.length
      ? plan.verification[curIdx]
      : "";

  return (
    <Card className="p-4 gap-2">
      <div className="flex items-center gap-2">
        <BrainCircuit className="w-4 h-4 text-neon-indigo" />
        <span className="text-sm font-semibold text-slate-100">任务计划</span>
        <span className="ml-auto text-xs text-slate-400">
          {plan.done.length}/{total}
        </span>
      </div>
      <Progress value={pct} />

      <div className="max-h-[168px] overflow-y-auto pr-1 space-y-1">
        {plan.subtasks.map((s, i) => {
          const done = plan.done.includes(s);
          const isCurrent = s === plan.current && !done;
          return (
            <div
              key={i}
              className={cn(
                "flex items-start gap-2 text-xs rounded-lg px-2 py-1.5 border transition",
                isCurrent
                  ? "bg-neon-cyan/10 border-neon-cyan/30"
                  : "bg-white/5 border-transparent"
              )}
            >
              {done ? (
                <CheckCircle2 className="w-3.5 h-3.5 text-func-green mt-0.5 shrink-0" />
              ) : (
                <Circle className="w-3.5 h-3.5 text-slate-500 mt-0.5 shrink-0" />
              )}
              <span className={done ? "text-slate-500 line-through" : "text-slate-200"}>{s}</span>
            </div>
          );
        })}
      </div>

      {verification && (
        <div className="flex items-start gap-2 text-[11px] rounded-lg bg-ink-800/70 border border-white/10 px-2.5 py-1.5 text-slate-300">
          <Target className="w-3.5 h-3.5 text-neon-cyan mt-0.5 shrink-0" />
          <span>
            <span className="text-slate-400">完成标准：</span>
            {verification}
          </span>
        </div>
      )}

      {reflection && (
        <div className="flex items-start gap-2 text-[11px] rounded-lg bg-ink-800/70 border border-white/10 px-2.5 py-1.5">
          <ShieldCheck className="w-3.5 h-3.5 text-neon-indigo mt-0.5 shrink-0" />
          <span className="text-slate-300">
            <Badge variant={(REFLECTION_META[reflection.status] ?? REFLECTION_META.continue).variant}>
              {(REFLECTION_META[reflection.status] ?? REFLECTION_META.continue).label}
            </Badge>{" "}
            {reflection.reason}
          </span>
        </div>
      )}
    </Card>
  );
}
