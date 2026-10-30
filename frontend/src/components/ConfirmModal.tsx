import { motion } from "framer-motion";
import { ShieldAlert, ShieldCheck, Ban } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import type { ZAction } from "../ws";

interface Props {
  request: { reason: string; pending_action: ZAction };
  onResolve: (approved: boolean) => void;
}

export default function ConfirmModal({ request, onResolve }: Props) {
  const a = request.pending_action;
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <motion.div
        initial={{ opacity: 0, y: 12, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.22 }}
        className="glass glass-strong rounded-2xl w-[440px] p-5"
      >
        <div className="flex items-center gap-2 mb-3">
          <ShieldAlert className="w-5 h-5 text-func-amber" />
          <span className="font-semibold text-func-amber">敏感操作需要你批准</span>
          <Badge variant="warn" className="ml-auto">
            风险智能体
          </Badge>
        </div>

        <p className="text-sm text-slate-200 mb-2">{request.reason}</p>

        <div className="rounded-xl bg-black/30 border border-white/10 px-3 py-2 text-xs mb-4 space-y-1">
          <div>
            <span className="text-slate-500">动作：</span>
            <span className="text-neon-cyan">{a.action}</span>
          </div>
          {a.target && (
            <div>
              <span className="text-slate-500">目标：</span>
              <span className="text-slate-300 break-all">{a.target}</span>
            </div>
          )}
          {a.reason && (
            <div>
              <span className="text-slate-500">理由：</span>
              <span className="text-slate-300">{a.reason}</span>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={() => onResolve(false)}>
            <Ban className="w-3.5 h-3.5" /> 取消该操作
          </Button>
          <Button variant="default" onClick={() => onResolve(true)}>
            <ShieldCheck className="w-3.5 h-3.5" /> 确认执行
          </Button>
        </div>
      </motion.div>
    </motion.div>
  );
}
