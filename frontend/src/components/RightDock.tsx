import { ScrollText, Brain, Users, BookOpen } from "lucide-react";
import { Card } from "./ui/card";
import LogFeed, { type LogItem } from "./LogFeed";
import ThinkStream, { type Thought } from "./ThinkStream";
import AgentSwarm, { type AgentActivity } from "./AgentSwarm";
import SkillPanel, { type SkillActivity } from "./SkillPanel";
import type { AgentInfo, AgentsResponse, SkillItem } from "../ws";
import { cn } from "../lib/utils";

export type DockTab = "log" | "think" | "swarm" | "skill";

interface Props {
  tab: DockTab;
  onTab: (t: DockTab) => void;
  logs: LogItem[];
  thoughts: Thought[];
  agents: AgentInfo[];
  activity: AgentActivity[];
  skills: SkillItem[];
  skillActivity: SkillActivity[];
  mode: AgentsResponse["mode"];
  onReloadSkills: () => void;
}

const TABS: { key: DockTab; label: string; icon: typeof ScrollText }[] = [
  { key: "log", label: "日志", icon: ScrollText },
  { key: "think", label: "思维", icon: Brain },
  { key: "swarm", label: "团队", icon: Users },
  { key: "skill", label: "技能", icon: BookOpen },
];

export default function RightDock({
  tab,
  onTab,
  logs,
  thoughts,
  agents,
  activity,
  skills,
  skillActivity,
  mode,
  onReloadSkills,
}: Props) {
  const counts: Record<DockTab, number> = {
    log: logs.length,
    think: thoughts.length,
    swarm: agents.length,
    skill: skills.length,
  };

  return (
    <Card className="h-full">
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-white/10">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = tab === t.key;
          return (
            <button
              key={t.key}
              onClick={() => onTab(t.key)}
              className={cn(
                "flex-1 flex items-center justify-center gap-1 text-[11px] py-1.5 rounded-lg border transition cursor-pointer",
                active
                  ? "border-neon-cyan/50 text-neon-cyan bg-neon-cyan/10"
                  : "border-transparent text-slate-400 hover:bg-white/5"
              )}
            >
              <Icon className="w-3.5 h-3.5" />
              {t.label}
              <span className={cn("text-[10px]", active ? "text-neon-cyan" : "text-slate-600")}>
                {counts[t.key]}
              </span>
            </button>
          );
        })}
      </div>

      <div className="flex-1 min-h-0 overflow-hidden">
        {tab === "log" && <LogFeed logs={logs} />}
        {tab === "think" && <ThinkStream thoughts={thoughts} />}
        {tab === "swarm" && <AgentSwarm agents={agents} activity={activity} mode={mode} />}
        {tab === "skill" && (
          <SkillPanel skills={skills} activity={skillActivity} onReload={onReloadSkills} />
        )}
      </div>
    </Card>
  );
}
