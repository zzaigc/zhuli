import { useMemo } from "react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { Activity, Timer, Zap, Sparkles } from "lucide-react";
import { Card } from "./ui/card";

export interface PulsePoint {
  t: number;
  steps: number;
}

interface Props {
  pulse: PulsePoint[];
  startedAt: number | null;
  skillsHit: number;
}

function fmtDuration(ms: number) {
  const s = Math.round(ms / 1000);
  const m = Math.floor(s / 60);
  return `${m}:${String(s % 60).padStart(2, "0")}`;
}

export default function MetricsStrip({ pulse, startedAt, skillsHit }: Props) {
  const elapsed = startedAt ? Date.now() - startedAt : 0;
  const steps = useMemo(() => pulse.reduce((a, p) => a + p.steps, 0), [pulse]);
  const speed = elapsed > 0 ? (steps / (elapsed / 60000)).toFixed(1) : "0.0";

  return (
    <Card className="p-3 gap-2">
      <div className="flex items-center gap-2">
        <Activity className="w-4 h-4 text-neon-cyan" />
        <span className="text-sm font-semibold text-slate-100">决策脉搏</span>
        <span className="ml-auto text-[11px] text-slate-400 flex items-center gap-1">
          <Timer className="w-3 h-3" />
          {startedAt ? fmtDuration(elapsed) : "--:--"}
        </span>
      </div>

      <div className="h-[56px] -mx-1">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={pulse} margin={{ top: 4, right: 4, bottom: 0, left: 4 }}>
            <defs>
              <linearGradient id="pulseFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#22D3EE" stopOpacity={0.55} />
                <stop offset="100%" stopColor="#22D3EE" stopOpacity={0} />
              </linearGradient>
            </defs>
            <Area
              type="monotone"
              dataKey="steps"
              stroke="#22D3EE"
              strokeWidth={2}
              fill="url(#pulseFill)"
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      <div className="grid grid-cols-3 gap-1.5 text-center">
        {[
          { icon: Zap, label: "步数", value: String(steps), cls: "text-neon-cyan" },
          { icon: Activity, label: "步/分", value: speed, cls: "text-neon-blue" },
          { icon: Sparkles, label: "技能命中", value: String(skillsHit), cls: "text-neon-indigo" },
        ].map((k) => (
          <div key={k.label} className="rounded-lg bg-white/5 border border-white/10 py-1.5">
            <div className={`text-sm font-bold ${k.cls}`}>{k.value}</div>
            <div className="text-[10px] text-slate-500">{k.label}</div>
          </div>
        ))}
      </div>
    </Card>
  );
}
