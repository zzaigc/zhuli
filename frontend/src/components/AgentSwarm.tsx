import { Users, Cpu, Wrench, Sparkles, Activity } from "lucide-react";
import { Badge } from "./ui/badge";
import type { AgentEvent, AgentInfo, AgentsResponse } from "../ws";
import { clip } from "../lib/utils";

export interface AgentActivity {
  agent: string;
  stage: AgentEvent["stage"];
  summary: string;
  verdict: string | null;
  ts: number;
}

interface Props {
  agents: AgentInfo[];
  activity: AgentActivity[];
  mode: AgentsResponse["mode"];
}

const STAGE_LABEL: Record<AgentEvent["stage"], string> = {
  plan: "规划",
  observe: "观察",
  decide: "决策",
  critique: "批评",
  risk: "风险",
  reflect: "反思",
  skill: "技能",
  delegate: "派发",
  consensus: "共识",
};

const VERDICT_VARIANT: Record<string, "success" | "warn" | "danger" | "default"> = {
  accept: "success",
  revise: "warn",
  abort: "danger",
  safe: "success",
  confirm: "warn",
  danger: "danger",
};

export default function AgentSwarm({ agents, activity, mode }: Props) {
  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-white/10 flex items-center gap-2">
        {mode === "hive" ? (
          <span className="text-base animate-bees">🐝</span>
        ) : (
          <Users className="w-4 h-4 text-neon-indigo" />
        )}
        <span className="text-sm font-semibold text-slate-100">智能体团队</span>
        <Badge variant={mode === "hive" ? "default" : "indigo"} className="ml-auto">
          {agents.length} 个模块
        </Badge>
      </div>

      {/* 团队名册 */}
      <div className="px-2.5 py-2 border-b border-white/10 max-h-[190px] overflow-y-auto">
        <div className="grid grid-cols-1 gap-1">
          {agents.length === 0 && (
            <p className="text-xs text-slate-500 px-1">正在加载智能体团队…</p>
          )}
          {agents.map((a) => (
            <div
              key={a.name}
              className="flex items-center gap-2 rounded-lg bg-white/5 border border-white/10 px-2.5 py-1.5"
            >
              {a.tool ? (
                <Wrench className="w-3.5 h-3.5 text-emerald-300 shrink-0" />
              ) : a.name.startsWith("skill:") ? (
                <Sparkles className="w-3.5 h-3.5 text-neon-cyan shrink-0" />
              ) : (
                <Cpu className="w-3.5 h-3.5 text-neon-indigo shrink-0" />
              )}
              <span className="text-xs text-slate-200 truncate">{a.role || a.name}</span>
              <span className="ml-auto text-[10px] text-slate-500 truncate max-w-[110px]">
                {a.model || a.tool || a.capability || ""}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* 活动流 */}
      <div className="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-1.5">
        {activity.length === 0 && (
          <p className="text-xs text-slate-500 px-1">
            任务开始后，每个智能体的活动（谁在规划、谁在挑刺、谁在评估风险）会实时出现在这里。
          </p>
        )}
        {activity.map((e, i) => (
          <div
            key={i}
            className="rounded-lg bg-white/5 border border-white/10 px-2.5 py-1.5 animate-floatIn"
          >
            <div className="flex items-center gap-1.5">
              <Activity className="w-3 h-3 text-neon-cyan shrink-0" />
              <span className="text-xs font-semibold text-slate-200">{e.agent}</span>
              <Badge variant="outline" className="scale-90 origin-left">
                {STAGE_LABEL[e.stage] ?? e.stage}
              </Badge>
              {e.verdict && (
                <Badge variant={VERDICT_VARIANT[e.verdict] ?? "default"} className="ml-auto">
                  {e.verdict}
                </Badge>
              )}
            </div>
            {e.summary && (
              <p className="mt-1 text-[11px] text-slate-400 leading-relaxed break-words">
                {clip(e.summary, 240)}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
