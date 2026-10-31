import { cn } from "../lib/utils";

export type BidirectionalMode = "off" | "ide_to_zhuli" | "zhuli_to_ide";

const SEGMENTS: {
  value: BidirectionalMode;
  label: string;
  title: string;
}[] = [
  {
    value: "ide_to_zhuli",
    label: "IDE → Zhuli",
    title: "外部 IDE 经 MCP 操作 Zhuli；Zhuli 不能反向派发，避免 IDE ↔ Zhuli 来回循环",
  },
  {
    value: "off",
    label: "关闭",
    title: "仅本助理：两方向的 IDE 派发都关闭（默认位置）",
  },
  {
    value: "zhuli_to_ide",
    label: "Zhuli → IDE",
    title: "Zhuli 派发到外部 IDE；来自 IDE 的 MCP 派发被阻止，避免来回循环",
  },
];

interface Props {
  mode: BidirectionalMode;
  onChange: (m: BidirectionalMode) => void;
}

/**
 * v0.3.0 双向开关：一个分段控件、一个值、三选一。
 * 不是两个独立开关，所以两方向从构造上就不可能同时开启；
 * 后端（控制台 /api/dispatch、WebSocket 任务、Orchestrator.submit、
 * MCP zhuli_tool_dispatch）还会各自再查一次同一个值。
 */
export default function BidirectionalSwitch({ mode, onChange }: Props) {
  return (
    <div className="space-y-1">
      <div
        role="group"
        aria-label="IDE 双向开关：同一时刻只能选一个方向"
        title="IDE 双向开关：同一时刻只能选一个方向，避免 IDE ↔ Zhuli 来回循环"
        className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 p-1"
      >
        <span className="text-xs text-slate-400 shrink-0 px-1">双向开关</span>
        {SEGMENTS.map((s) => (
          <button
            key={s.value}
            type="button"
            onClick={() => onChange(s.value)}
            aria-pressed={mode === s.value}
            title={s.title}
            className={cn(
              "flex-1 rounded-md px-1 py-1.5 text-xs transition cursor-pointer",
              mode === s.value
                ? "bg-neon-cyan/20 border border-neon-cyan/50 text-neon-cyan font-medium"
                : "border border-transparent text-slate-400 hover:text-slate-200 hover:bg-white/5"
            )}
          >
            {s.label}
          </button>
        ))}
      </div>
      <p className="text-[10px] text-slate-500 leading-relaxed">
        {mode === "off" && "当前：仅本助理。两方向的 IDE 派发都已关闭。"}
        {mode === "ide_to_zhuli" &&
          "当前：IDE → Zhuli。外部 IDE 可经 MCP 操作 Zhuli；控制台「派发到 IDE」按钮与目标工具的 IDE 选项已禁用，Zhuli 不会反向派发。"}
        {mode === "zhuli_to_ide" &&
          "当前：Zhuli → IDE。控制台「派发到 IDE」按钮可用；来自 IDE 的 MCP 派发已被阻止。"}
        默认关闭；开关是运行时覆盖，重启恢复为配置值。
      </p>
    </div>
  );
}
