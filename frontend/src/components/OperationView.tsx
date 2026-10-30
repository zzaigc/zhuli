import { useEffect, useRef, useState } from "react";
import { Monitor, Crosshair } from "lucide-react";
import { Card, CardHeader, CardTitle } from "./ui/card";
import { Badge } from "./ui/badge";
import type { ZHighlight } from "../ws";
import { fmtTime } from "../lib/utils";

export interface Shot {
  image: string;
  highlights: ZHighlight[];
  ts: number;
}

interface Props {
  shot: Shot | null;
  running: boolean;
}

export default function OperationView({ shot, running }: Props) {
  const [lag, setLag] = useState(0);
  const lastRef = useRef(0);

  // 统计画面刷新间隔，让「AI 在动」这件事可度量
  useEffect(() => {
    if (!shot) return;
    const now = Date.now();
    if (lastRef.current) setLag(now - lastRef.current);
    lastRef.current = now;
    const id = setTimeout(() => setLag(0), 2000);
    return () => clearTimeout(id);
  }, [shot?.ts]);

  return (
    <Card className="h-full">
      <CardHeader className="justify-between">
        <div className="flex items-center gap-2">
          <Monitor className="w-4 h-4 text-neon-cyan" />
          <CardTitle>操作视图</CardTitle>
          <Badge variant="outline" className="font-mono">
            隔离 Chromium
          </Badge>
        </div>
        <div className="flex items-center gap-2">
          {lag > 0 && <Badge variant="indigo">{lag} ms/帧</Badge>}
          <Badge variant={running ? "success" : "outline"}>
            <span
              className={`w-1.5 h-1.5 rounded-full ${running ? "bg-func-green animate-pulse" : "bg-slate-500"}`}
            />
            {running ? "LIVE" : "IDLE"}
          </Badge>
        </div>
      </CardHeader>

      <div className="flex-1 min-h-0 p-2 relative">
        {!shot ? (
          <div className="h-full rounded-xl border border-dashed border-white/10 bg-black/20 overflow-hidden relative flex items-center justify-center">
            <div className="absolute inset-x-0 h-16 bg-gradient-to-b from-transparent via-neon-cyan/10 to-transparent animate-scan" />
            <div className="text-center px-6">
              <Crosshair className="w-8 h-8 text-neon-cyan/60 mx-auto mb-2 animate-pulseRing" />
              <p className="text-sm text-slate-300">浏览器画面将实时回传到这里</p>
              <p className="mt-1 text-xs text-slate-500 leading-relaxed">
                AI 操作的是独立弹出的 Chromium 窗口（独立 Profile，与你的日常浏览器完全隔离）。
                <br />
                执行命令或视频任务时，请切换到「终端」标签查看输出。
              </p>
            </div>
          </div>
        ) : (
          <div className="h-full rounded-xl overflow-hidden relative bg-black/40">
            <img
              src={`data:image/jpeg;base64,${shot.image}`}
              alt="浏览器操作画面"
              className="w-full h-full object-contain"
            />
            {shot.highlights.map((h, i) => (
              <div
                key={i}
                style={{ left: h.x, top: h.y, width: h.w, height: h.h }}
                className="absolute border-2 border-neon-cyan rounded-md shadow-glow pointer-events-none animate-pulseRing"
              >
                <span className="absolute -top-5 left-0 text-[10px] px-1.5 py-0.5 rounded-md bg-neon-cyan text-ink-900 font-bold">
                  {i + 1}
                </span>
              </div>
            ))}
            <span className="absolute bottom-2 right-2 text-[10px] px-2 py-0.5 rounded-md bg-black/60 text-slate-300 font-mono">
              {fmtTime(shot.ts)}
            </span>
          </div>
        )}
      </div>
    </Card>
  );
}
