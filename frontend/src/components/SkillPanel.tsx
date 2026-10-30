import { BookOpen, Sparkles, TrendingUp, GraduationCap, Trash2 } from "lucide-react";
import { Badge } from "./ui/badge";
import type { SkillEvent, SkillItem } from "../ws";
import { api } from "../ws";
import { clip } from "../lib/utils";

export interface SkillActivity {
  name: string;
  action: SkillEvent["action"];
  reason: string | null;
  ts: number;
}

interface Props {
  skills: SkillItem[];
  activity: SkillActivity[];
  onReload: () => void;
}

const ACTION_META: Record<SkillEvent["action"], { label: string; variant: "success" | "default" | "indigo" | "warn" }> = {
  learned: { label: "学会", variant: "success" },
  updated: { label: "强化", variant: "default" },
  matched: { label: "命中", variant: "indigo" },
  promoted: { label: "升格", variant: "warn" },
};

export default function SkillPanel({ skills, activity, onReload }: Props) {
  const remove = async (id: number) => {
    await api.deleteSkill(id);
    onReload();
  };

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-2 border-b border-white/10 flex items-center gap-2">
        <BookOpen className="w-4 h-4 text-neon-cyan" />
        <span className="text-sm font-semibold text-slate-100">技能库</span>
        <Badge variant="outline" className="ml-auto">
          {skills.length} 项 · 越用越聪明
        </Badge>
      </div>

      <div className="max-h-[45%] overflow-y-auto p-2.5 space-y-1.5 border-b border-white/10">
        {skills.length === 0 && (
          <p className="text-xs text-slate-500 px-1">
            成功完成的任务会被自动沉淀为可复用技能；成熟后升格为专项智能体，成为系统的新模块。
          </p>
        )}
        {skills.map((s) => (
          <div
            key={s.id}
            className="group rounded-xl bg-white/5 border border-white/10 px-2.5 py-2 hover:border-neon-cyan/30 transition"
          >
            <div className="flex items-center gap-1.5">
              <GraduationCap className="w-3.5 h-3.5 text-neon-indigo shrink-0" />
              <span className="text-xs font-semibold text-slate-200 truncate">{s.name}</span>
              <button
                onClick={() => remove(s.id)}
                className="ml-auto opacity-0 group-hover:opacity-100 transition text-slate-500 hover:text-func-red cursor-pointer"
                title="删除技能"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
            {s.description && (
              <p className="mt-0.5 text-[11px] text-slate-400 line-clamp-2">{s.description}</p>
            )}
            <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
              <span className="flex items-center gap-1">
                <TrendingUp className="w-3 h-3" />
                命中 {s.uses ?? 0} · 成功 {s.successes ?? 0}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-2.5 space-y-1.5">
        {activity.map((a, i) => (
          <div
            key={i}
            className="flex items-start gap-1.5 rounded-lg bg-white/5 border border-white/10 px-2.5 py-1.5 animate-floatIn"
          >
            <Sparkles className="w-3.5 h-3.5 text-neon-cyan mt-0.5 shrink-0" />
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-xs text-slate-200 truncate">{a.name}</span>
                <Badge variant={ACTION_META[a.action]?.variant ?? "default"}>
                  {ACTION_META[a.action]?.label ?? a.action}
                </Badge>
              </div>
              {a.reason && <p className="text-[10px] text-slate-500">{clip(a.reason, 160)}</p>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
