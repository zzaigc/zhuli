import { useState } from "react";
import { motion } from "framer-motion";
import { Send, Sparkles, CornerDownLeft } from "lucide-react";
import { Card, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Textarea } from "./ui/textarea";
import { cn } from "../lib/utils";

export interface ChatMsg {
  role: "user" | "assistant" | "system";
  text: string;
}

interface Props {
  messages: ChatMsg[];
  tools: string[];
  targetTool: string;
  onTargetChange: (t: string) => void;
  onSend: (goal: string, targetTool: string) => void;
  disabled: boolean;
}

const EXAMPLES = [
  "打开百度搜索「北京天气」并总结前三条结果",
  "用 OpenCode 在当前目录写一个快速排序并跑通测试",
  "把桌面视频裁剪前 10 秒并转码为 720p",
];

export default function ChatPanel({
  messages,
  tools,
  targetTool,
  onTargetChange,
  onSend,
  disabled,
}: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    const g = text.trim();
    if (!g || disabled) return;
    onSend(g, targetTool);
    setText("");
  };

  return (
    <Card className="h-full">
      <CardHeader>
        <Sparkles className="w-4 h-4 text-neon-cyan" />
        <CardTitle>指令台</CardTitle>
        <Badge variant="outline" className="ml-auto">
          {targetTool || "本助理"}
        </Badge>
      </CardHeader>

      <div className="flex-1 min-h-0 overflow-y-auto px-4 py-3 space-y-2">
        {messages.length === 0 && (
          <div className="text-xs text-slate-400/90 leading-relaxed space-y-1.5">
            <p>下达自然语言目标，助理会自动规划、观察、执行并反思。</p>
            {EXAMPLES.map((e) => (
              <button
                key={e}
                onClick={() => setText(e)}
                className="block w-full text-left text-[11px] rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-slate-300 hover:border-neon-cyan/40 hover:text-neon-cyan transition cursor-pointer"
              >
                {e}
              </button>
            ))}
          </div>
        )}

        {messages.map((m, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className={cn(
              "text-sm rounded-xl px-3 py-2 border",
              m.role === "user"
                ? "bg-neon-cyan/10 border-neon-cyan/30 ml-6"
                : m.role === "system"
                ? "bg-func-amber/10 border-func-amber/30 text-amber-200 mr-6"
                : "bg-white/5 border-white/10 mr-6"
            )}
          >
            <span className="text-[10px] uppercase tracking-widest text-slate-400">
              {m.role === "user" ? "你" : m.role === "system" ? "系统" : "助理"}
            </span>
            <div className="mt-0.5 text-slate-200 whitespace-pre-wrap break-words">{m.text}</div>
          </motion.div>
        ))}
      </div>

      <div className="p-3 border-t border-white/10 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 shrink-0">目标工具</span>
          <select
            value={targetTool}
            onChange={(e) => onTargetChange(e.target.value)}
            className="flex-1 bg-ink-800/80 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-neon-cyan/50 cursor-pointer"
          >
            <option value="">本助理（直接操作浏览器/命令/视频）</option>
            {tools.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        <div className="flex items-end gap-2">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            rows={2}
            placeholder={disabled ? "任务执行中，可暂停后再下达新目标…" : "输入任务目标，Enter 发送 / Shift+Enter 换行"}
            className="flex-1"
          />
          <Button
            onClick={submit}
            disabled={disabled || !text.trim()}
            size="default"
            className="h-[52px] w-11"
            title="发送任务"
          >
            <Send className="w-4 h-4" />
          </Button>
        </div>
        <div className="flex items-center gap-1 text-[10px] text-slate-500">
          <CornerDownLeft className="w-3 h-3" /> Enter 发送
        </div>
      </div>
    </Card>
  );
}
