import { Hexagon, Cpu, Settings, Users, Radio, Wifi, WifiOff } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { cn } from "../lib/utils";
import type { AgentsResponse, ModelsResponse } from "../ws";

interface Props {
  status: string;
  connected: boolean;
  mode: AgentsResponse["mode"];
  models: ModelsResponse | null;
  onModelChange: (capability: string, provider: string) => void;
  onOpenAgents: () => void;
  onOpenSettings: () => void;
}

const MODE_META: Record<AgentsResponse["mode"], { label: string; variant: "default" | "indigo" | "warn" }> = {
  single: { label: "单脑模式", variant: "outline" },
  multi: { label: "多智能体", variant: "indigo" },
  hive: { label: "🐝 蜂巢思维", variant: "default" },
};

const STATUS_META: Record<string, { label: string; variant: "success" | "warn" | "danger" | "default" | "outline" }> = {
  idle: { label: "空闲", variant: "outline" },
  running: { label: "执行中", variant: "success" },
  paused: { label: "已暂停", variant: "warn" },
  awaiting_confirm: { label: "等待确认", variant: "warn" },
  awaiting_credential: { label: "等待凭据", variant: "warn" },
  stopped: { label: "已停止", variant: "danger" },
  error: { label: "异常", variant: "danger" },
  done: { label: "已完成", variant: "success" },
};

export default function TopBar({
  status,
  connected,
  mode,
  models,
  onModelChange,
  onOpenAgents,
  onOpenSettings,
}: Props) {
  const m = MODE_META[mode] ?? MODE_META.multi;
  const s = STATUS_META[status] ?? { label: status, variant: "outline" as const };

  return (
    <header className="fixed top-0 inset-x-0 z-40 h-14 glass border-b border-white/10 flex items-center gap-3 px-5">
      <div className="flex items-center gap-2">
        <div className="relative">
          <Hexagon className="w-6 h-6 text-neon-cyan animate-pulseRing" />
          <Cpu className="w-3 h-3 text-neon-blue absolute inset-0 m-auto" />
        </div>
        <span className="text-lg font-bold tracking-[0.2em] neon-text">ZHULI</span>
        <span className="hidden xl:inline text-xs text-slate-400">本地 AI 操作台 · 蜂巢决策系统</span>
      </div>

      <div className="flex items-center gap-2 ml-4">
        <Badge variant={m.variant}>{m.label}</Badge>
        <Badge variant={s.variant}>
          <span
            className={cn(
              "w-1.5 h-1.5 rounded-full",
              status === "running" ? "bg-func-green animate-pulse" : "bg-current"
            )}
          />
          {s.label}
        </Badge>
      </div>

      <div className="ml-auto flex items-center gap-2">
        {models && (
          <label className="hidden lg:flex items-center gap-2 text-xs text-slate-400">
            <span>决策模型</span>
            <select
              value={models.routing?.default ?? ""}
              onChange={(e) => onModelChange("default", e.target.value)}
              className="bg-ink-800/80 border border-white/10 rounded-lg px-2 py-1 text-xs text-slate-200 outline-none focus:border-neon-cyan/50 cursor-pointer"
            >
              {models.providers.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
        )}

        <div className="hidden md:flex items-center gap-1 text-xs text-slate-400 mr-1">
          <Radio className="w-3.5 h-3.5 text-neon-cyan" />
          <span>WS</span>
          {connected ? (
            <Wifi className="w-3.5 h-3.5 text-func-green" />
          ) : (
            <WifiOff className="w-3.5 h-3.5 text-func-red" />
          )}
        </div>

        <Button variant="outline" size="sm" onClick={onOpenAgents}>
          <Users className="w-3.5 h-3.5" /> 智能体团队
        </Button>
        <Button variant="ghost" size="icon" onClick={onOpenSettings} title="设置与安全">
          <Settings className="w-4 h-4" />
        </Button>
      </div>
    </header>
  );
}
