import { Card, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { cn } from "../lib/utils";

export interface ZhuliSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
}

interface Props {
  sessions: ZhuliSession[];
  currentId: string;
  busy: boolean;
  onNew: () => void;
  onSwitch: (id: string) => void;
}

function fmt(ts: number) {
  try {
    return new Date(ts).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return String(ts);
  }
}

export default function SessionPanel({ sessions, currentId, busy, onNew, onSwitch }: Props) {
  return (
    <Card className="shrink-0">
      <CardHeader>
        <CardTitle>会话</CardTitle>
        <Button size="sm" onClick={onNew} disabled={busy} title={busy ? "任务执行中，结束后可新建会话" : "新建会话"}>
          新会话
        </Button>
      </CardHeader>
      <div className="px-3 pb-3 space-y-1.5 max-h-44 overflow-y-auto">
        {sessions.length === 0 && (
          <p className="text-xs text-slate-400">暂无会话，点“新会话”开始。</p>
        )}
        {sessions.map((s) => (
          <button
            key={s.id}
            onClick={() => onSwitch(s.id)}
            disabled={busy}
            className={cn(
              "block w-full text-left rounded-lg border px-2.5 py-1.5 transition cursor-pointer",
              s.id === currentId
                ? "border-neon-cyan/50 bg-neon-cyan/10 text-slate-100"
                : "border-white/10 bg-white/5 text-slate-300 hover:border-neon-cyan/40"
            )}
          >
            <span className="block text-xs font-medium truncate">{s.title}</span>
            <span className="block text-[10px] text-slate-500">{fmt(s.updatedAt)}</span>
          </button>
        ))}
        <p className="text-[10px] text-slate-500 leading-relaxed">
          会话只保存在本机浏览器里，刷新后仍在；换设备或清浏览器数据后会丢失。切换会话会清空当前对话、计划、日志、思考、终端和右侧任务状态。
        </p>
      </div>
    </Card>
  );
}
