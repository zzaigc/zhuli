import { Pause, Play, Square, Hand, Gauge } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";

export type ControlAction = "pause" | "resume" | "stop" | "takeover";

interface Props {
  status: string;
  speed: number;
  onControl: (a: ControlAction) => void;
  onSpeed: (v: number) => void;
}

const SPEEDS = [
  { v: 1, label: "1x" },
  { v: 2, label: "2x" },
  { v: 4, label: "4x" },
];

export default function ControlBar({ status, speed, onControl, onSpeed }: Props) {
  const running = status === "running" || status === "awaiting_confirm" || status === "awaiting_credential";
  const paused = status === "paused";

  return (
    <div className="glass rounded-2xl px-4 py-2 flex items-center gap-3">
      <span className="text-xs text-slate-400">人在回路</span>
      <Badge variant={running ? "success" : paused ? "warn" : "outline"}>
        {status === "awaiting_confirm"
          ? "等待你确认"
          : status === "awaiting_credential"
          ? "等待凭据"
          : paused
          ? "已暂停"
          : running
          ? "自动执行中"
          : status}
      </Badge>

      <div className="flex items-center gap-1 ml-2">
        <Gauge className="w-3.5 h-3.5 text-slate-400" />
        {SPEEDS.map((s) => (
          <button
            key={s.v}
            onClick={() => onSpeed(s.v)}
            className={`text-[11px] px-2 py-0.5 rounded-md border transition cursor-pointer ${
              speed === s.v
                ? "border-neon-cyan/50 text-neon-cyan bg-neon-cyan/10"
                : "border-white/10 text-slate-400 hover:text-slate-200"
            }`}
          >
            {s.label}
          </button>
        ))}
      </div>

      <div className="ml-auto flex items-center gap-2">
        {paused ? (
          <Button variant="ok" size="sm" onClick={() => onControl("resume")}>
            <Play className="w-3.5 h-3.5" /> 继续
          </Button>
        ) : (
          <Button variant="warn" size="sm" onClick={() => onControl("pause")} disabled={!running}>
            <Pause className="w-3.5 h-3.5" /> 暂停
          </Button>
        )}
        <Button variant="outline" size="sm" onClick={() => onControl("takeover")} disabled={!running}>
          <Hand className="w-3.5 h-3.5" /> 接管
        </Button>
        <Button variant="danger" size="sm" onClick={() => onControl("stop")}>
          <Square className="w-3.5 h-3.5" /> 停止
        </Button>
      </div>
    </div>
  );
}
