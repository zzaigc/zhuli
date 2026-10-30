import { motion } from "framer-motion";
import { Settings, ShieldCheck, Network, Cpu, Lock, X } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import type { ModelsResponse, SecurityInfo } from "../ws";

interface Props {
  models: ModelsResponse | null;
  security: SecurityInfo | null;
  integrations: string[];
  onModelChange: (capability: string, provider: string) => void;
  onClose: () => void;
}

const CAP_LABEL: Record<string, string> = {
  default: "默认决策",
  reasoning: "深度推理",
  vision: "视觉理解",
};

function Row({ label, value, good }: { label: string; value: string; good?: boolean }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-slate-400 w-32 shrink-0">{label}</span>
      <span className={good ? "text-func-green" : "text-slate-200"}>{value}</span>
    </div>
  );
}

export default function SettingsModal({ models, security, integrations, onModelChange, onClose }: Props) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    >
      <motion.div
        initial={{ opacity: 0, y: 14, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.22 }}
        className="glass glass-strong rounded-2xl w-[560px] max-h-[84vh] flex flex-col overflow-hidden"
      >
        <div className="flex items-center gap-2 px-5 py-3 border-b border-white/10">
          <Settings className="w-4 h-4 text-neon-cyan" />
          <span className="font-semibold text-slate-100">设置与状态</span>
          <Button variant="ghost" size="icon" className="ml-auto" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-5 space-y-5">
          {/* 模型路由 */}
          <section className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
              <Cpu className="w-4 h-4 text-neon-indigo" /> 模型能力路由
            </div>
            {(models?.capabilities ?? ["default", "reasoning", "vision"]).map((c) => (
              <div key={c} className="flex items-center gap-2">
                <span className="text-xs text-slate-400 w-24 shrink-0">{CAP_LABEL[c] ?? c}</span>
                <select
                  value={models?.routing?.[c] ?? ""}
                  onChange={(e) => onModelChange(c, e.target.value)}
                  className="flex-1 bg-ink-800/80 border border-white/10 rounded-lg px-2 py-1.5 text-xs text-slate-200 outline-none focus:border-neon-cyan/50 cursor-pointer"
                >
                  {(models?.providers ?? []).map((p) => (
                    <option key={p} value={p}>
                      {p}
                    </option>
                  ))}
                </select>
              </div>
            ))}
            <p className="text-[11px] text-slate-500">
              按能力拆分模型：视觉任务走 vision，复杂推理走 reasoning，常规决策走 default。
            </p>
          </section>

          {/* 安全与加密 */}
          <section className="space-y-2 rounded-xl bg-black/25 border border-white/10 p-3">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
              <Lock className="w-4 h-4 text-neon-cyan" /> 军事级加密
              <Badge variant={security?.available ? "success" : "warn"} className="ml-auto">
                {security?.available ? "已启用" : "降级模式"}
              </Badge>
            </div>
            <div className="space-y-1">
              <Row label="算法" value="AES-256-GCM（AEAD，128bit 认证标签）" good />
              <Row
                label="密钥派生"
                value={`PBKDF2-HMAC-SHA256 · ${security?.iterations ?? 600000} 轮 · 32B 随机盐`}
              />
              <Row label="主密钥来源" value={String(security?.master_source ?? "内存临时密钥")} />
              <Row label="信封加密" value={security?.envelope ? "已启用（ZH1 信封）" : "未启用"} good={!!security?.envelope} />
              <Row label="比对方式" value="HMAC 常量时间比较（防时序侧信道）" good />
            </div>
          </section>

          {/* 外部工具 */}
          <section className="space-y-2">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-100">
              <Network className="w-4 h-4 text-emerald-300" /> 外部工具连接器
            </div>
            <div className="flex flex-wrap gap-1.5">
              {(integrations ?? []).length === 0 && (
                <span className="text-xs text-slate-500">未配置外部工具</span>
              )}
              {(integrations ?? []).map((i) => (
                <Badge key={i} variant="success">
                  {i}
                </Badge>
              ))}
            </div>
          </section>

          <section className="flex items-start gap-2 text-[11px] text-slate-400 leading-relaxed rounded-xl bg-neon-cyan/5 border border-neon-cyan/20 p-3">
            <ShieldCheck className="w-4 h-4 text-neon-cyan mt-0.5 shrink-0" />
            <span>
              凭据明文永不进入模型上下文与日志；危险命令需确认后才执行；浏览器使用独立 Profile，
              与你的日常浏览器完全隔离。
            </span>
          </section>
        </div>

        <div className="px-5 py-3 border-t border-white/10 flex justify-end">
          <Button variant="default" onClick={onClose}>
            完成
          </Button>
        </div>
      </motion.div>
    </motion.div>
  );
}
