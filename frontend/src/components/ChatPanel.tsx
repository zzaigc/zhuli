import { useState } from "react";
import { motion } from "framer-motion";
import { Send, Sparkles, CornerDownLeft } from "lucide-react";
import { Card, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Textarea } from "./ui/textarea";
import { cn } from "../lib/utils";
import BidirectionalSwitch, { type BidirectionalMode } from "./BidirectionalSwitch";

export interface ChatMsg {
  role: "user" | "assistant" | "system";
  text: string;
}

export interface DispatchResult {
  ok: boolean;
  needs_approval?: boolean;
  request_id?: string;
  reason?: string;
  error?: string;
  submitted?: boolean;
}

interface Props {
  messages: ChatMsg[];
  tools: string[];
  targetTool: string;
  onTargetChange: (t: string) => void;
  onSend: (goal: string, targetTool: string) => void;
  disabled: boolean;
  // v0.3.0 双向开关与派发到 IDE（App 持有开关状态并调后端接口）。
  bidirectionalMode: BidirectionalMode;
  onBidirectionalChange: (m: BidirectionalMode) => void;
  dispatchToIde: (goal: string, tool: string, approvalId?: string) => Promise<DispatchResult | null>;
}

// 与后端 integrations.dispatch.KNOWN_TOOLS / agents.bidirectional.IDE_TOOLS 一致。
const IDE_TOOLS = ["codebuddy", "trae", "opencode"];

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
  bidirectionalMode,
  onBidirectionalChange,
  dispatchToIde,
}: Props) {
  const [text, setText] = useState("");
  // 派发到 IDE 的独立选择器（不替换上面的目标工具选择器）。
  const [dispatchTool, setDispatchTool] = useState("");
  const [dispatchMsg, setDispatchMsg] = useState<string | null>(null);
  const [dispatchPending, setDispatchPending] = useState<{
    goal: string;
    tool: string;
    requestId: string;
    reason: string;
  } | null>(null);
  const [dispatching, setDispatching] = useState(false);

  const submit = () => {
    const g = text.trim();
    if (!g || disabled) return;
    onSend(g, targetTool);
    setText("");
  };

  const handleModeChange = (m: BidirectionalMode) => {
    // 切换方向时丢弃未完成的派发确认：第二次调用会由后端按新位置重查。
    setDispatchPending(null);
    setDispatchMsg(null);
    onBidirectionalChange(m);
  };

  const dispatchHint = (): string => {
    if (disabled) return "任务执行中，结束后可派发";
    if (bidirectionalMode === "off") return "双向开关在关闭位置：切到 Zhuli → IDE 才能派发";
    if (bidirectionalMode === "ide_to_zhuli")
      return "双向开关在 IDE → Zhuli 位置：Zhuli 不能反向派发，避免来回循环";
    if (!text.trim()) return "先输入任务目标";
    if (!dispatchTool) return "请选择要派发的 IDE";
    return "点派发后需再确认一次，确认后提交为任务；执行中的确认仍走右侧确认流程";
  };

  const dispatchDisabled =
    disabled ||
    dispatching ||
    bidirectionalMode !== "zhuli_to_ide" ||
    !text.trim() ||
    !dispatchTool ||
    dispatchPending !== null;

  const doDispatch = async (goal: string, tool: string, approvalId?: string) => {
    setDispatching(true);
    setDispatchMsg(null);
    try {
      const res = await dispatchToIde(goal, tool, approvalId);
      if (!res) {
        setDispatchMsg("派发失败：后端无响应，请检查控制台服务是否还在运行");
        return;
      }
      if (res.needs_approval && res.request_id) {
        setDispatchPending({
          goal,
          tool,
          requestId: res.request_id,
          reason: res.reason || `派发到外部 IDE（${tool}）需要确认`,
        });
        return;
      }
      if (!res.ok) {
        // 诚实报错，绝不显示成功。
        setDispatchMsg(`派发失败：${res.error || "未知错误"}`);
        return;
      }
      setDispatchPending(null);
      setDispatchMsg(`已派发到 ${tool}：任务已提交，执行中的确认仍会走右侧确认流程`);
      setText("");
    } finally {
      setDispatching(false);
    }
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
            className="flex-1 min-w-0 bg-ink-800/80 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-neon-cyan/50 cursor-pointer"
          >
            <option value="">本助理（直接操作浏览器/命令/视频）</option>
            {tools.map((t) => {
              // 双向开关不在 Zhuli → IDE 时，IDE 选项禁用（本助理始终可用）；
              // 后端对普通任务消息还有同样的检查，界面禁用只是第一道。
              const ideBlocked = IDE_TOOLS.includes(t) && bidirectionalMode !== "zhuli_to_ide";
              return (
                <option key={t} value={t} disabled={ideBlocked}>
                  {t}
                  {ideBlocked ? "（需双向开关切到 Zhuli → IDE）" : ""}
                </option>
              );
            })}
          </select>
        </div>

        <BidirectionalSwitch mode={bidirectionalMode} onChange={handleModeChange} />

        <div className="space-y-1.5 rounded-lg border border-white/10 bg-white/5 p-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-400 shrink-0">派发到 IDE</span>
            <select
              value={dispatchTool}
              onChange={(e) => setDispatchTool(e.target.value)}
              disabled={bidirectionalMode !== "zhuli_to_ide"}
              title={
                bidirectionalMode !== "zhuli_to_ide"
                  ? "双向开关不在 Zhuli → IDE 位置时不可选择 IDE"
                  : "选择要派发的外部 IDE"
              }
              className="flex-1 min-w-0 bg-ink-800/80 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-neon-cyan/50 cursor-pointer disabled:opacity-50"
            >
              <option value="">选择 IDE</option>
              {IDE_TOOLS.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <Button
              size="sm"
              onClick={() => doDispatch(text.trim(), dispatchTool)}
              disabled={dispatchDisabled}
              title={dispatchHint()}
            >
              {dispatching ? "派发中…" : "派发到 IDE"}
            </Button>
          </div>
          <p className="text-[10px] text-slate-500 leading-relaxed">{dispatchHint()}</p>
          {dispatchPending && (
            <div className="flex items-center gap-2 rounded-lg border border-func-amber/40 bg-func-amber/10 px-2 py-1.5">
              <span className="flex-1 text-xs text-amber-200">{dispatchPending.reason}</span>
              <Button
                size="sm"
                onClick={() =>
                  doDispatch(dispatchPending.goal, dispatchPending.tool, dispatchPending.requestId)
                }
                disabled={dispatching}
              >
                确认派发
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setDispatchPending(null)}>
                取消
              </Button>
            </div>
          )}
          {dispatchMsg && (
            <p
              className={cn(
                "text-xs leading-relaxed",
                dispatchMsg.startsWith("派发失败") ? "text-func-red" : "text-neon-cyan"
              )}
            >
              {dispatchMsg}
            </p>
          )}
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
