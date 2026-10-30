import { useEffect, useRef } from "react";
import { Terminal, Eraser } from "lucide-react";
import { Card, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";

export interface TermLine {
  stream: "stdout" | "stderr" | "system";
  line: string;
  ts: number;
}

interface Props {
  lines: TermLine[];
  onClear: () => void;
  tool?: string;
}

export default function TerminalPanel({ lines, onClear, tool }: Props) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines.length]);

  return (
    <Card className="h-full">
      <CardHeader className="justify-between">
        <div className="flex items-center gap-2">
          <div className="flex gap-1.5 mr-1">
            <span className="w-2.5 h-2.5 rounded-full bg-func-red" />
            <span className="w-2.5 h-2.5 rounded-full bg-func-amber" />
            <span className="w-2.5 h-2.5 rounded-full bg-func-green" />
          </div>
          <Terminal className="w-3.5 h-3.5 text-neon-cyan" />
          <CardTitle>终端输出</CardTitle>
          {tool && <Badge variant="indigo">{tool}</Badge>}
        </div>
        <Button variant="ghost" size="xs" onClick={onClear}>
          <Eraser className="w-3 h-3" /> 清屏
        </Button>
      </CardHeader>

      <div
        ref={ref}
        className="flex-1 min-h-0 overflow-y-auto p-3 font-mono text-[12px] leading-relaxed bg-black/40"
      >
        {lines.length === 0 ? (
          <span className="text-slate-500">
            {"// 命令执行、ffmpeg 剪辑、OpenCode 等终端型任务的输出会实时回传到这里"}
          </span>
        ) : (
          lines.map((l, i) => (
            <div
              key={i}
              className={
                l.stream === "stderr"
                  ? "text-func-red"
                  : l.stream === "system"
                  ? "text-neon-cyan"
                  : "text-emerald-300"
              }
            >
              <span className="text-slate-600 select-none mr-1.5">
                {l.stream === "stderr" ? "!" : l.stream === "system" ? ">" : "$"}
              </span>
              {l.line}
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
