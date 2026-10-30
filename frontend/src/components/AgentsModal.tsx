import { motion } from "framer-motion";
import { Users, Cpu, Wrench, Sparkles, X } from "lucide-react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import type { AgentInfo, AgentsResponse } from "../ws";

interface Props {
  data: AgentsResponse | null;
  onClose: () => void;
}

const ROLE_ICON = (a: AgentInfo) =>
  a.tool ? (
    <Wrench className="w-3.5 h-3.5 text-emerald-300" />
  ) : a.name.startsWith("skill:") ? (
    <Sparkles className="w-3.5 h-3.5 text-neon-cyan" />
  ) : (
    <Cpu className="w-3.5 h-3.5 text-neon-indigo" />
  );

export default function AgentsModal({ data, onClose }: Props) {
  const modeLabel =
    data?.mode === "hive" ? "🐝 蜂巢思维" : data?.mode === "multi" ? "多智能体流水线" : "单脑模式";

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
        className="glass glass-strong rounded-2xl w-[620px] max-h-[80vh] flex flex-col overflow-hidden"
      >
        <div className="flex items-center gap-2 px-5 py-3 border-b border-white/10">
          <Users className="w-4 h-4 text-neon-indigo" />
          <span className="font-semibold text-slate-100">智能体团队</span>
          <Badge variant={data?.mode === "hive" ? "default" : "indigo"}>{modeLabel}</Badge>
          <span className="ml-auto text-xs text-slate-400">{data?.total ?? 0} 个模块</span>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="w-4 h-4" />
          </Button>
        </div>

        <div className="px-5 py-3 text-[11px] text-slate-400 border-b border-white/10 leading-relaxed">
          {data?.mode === "hive"
            ? "蜂巢模式：多个提案者并行思考，批评者与风险官并行投票，按加权共识择优执行；技能成熟后自动升格为专项智能体，模块随使用增长。"
            : "流水线模式：规划 → 观察 → 执行 → 批评/风险 → 反思。技能成熟后自动升格为专项智能体，模块随使用增长。"}
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1.5">
          {(data?.agents ?? []).map((a) => (
            <div
              key={a.name}
              className="flex items-center gap-2.5 rounded-xl bg-white/5 border border-white/10 px-3 py-2"
            >
              {ROLE_ICON(a)}
              <div className="min-w-0">
                <div className="text-xs font-semibold text-slate-100 truncate">
                  {a.role || a.name}
                  <span className="ml-2 text-[10px] text-slate-500 font-mono">{a.name}</span>
                </div>
                <div className="text-[10px] text-slate-500 truncate">
                  {a.tool ? `外部工具连接器 · ${a.tool}` : a.capability ? `能力：${a.capability}` : ""}
                </div>
              </div>
              <div className="ml-auto text-right shrink-0">
                <div className="text-[11px] text-slate-300">{a.provider || "-"}</div>
                <div className="text-[10px] text-slate-500 truncate max-w-[160px]">{a.model || ""}</div>
              </div>
            </div>
          ))}
          {!data?.agents?.length && (
            <p className="text-xs text-slate-500 p-2">团队未就绪（检查 config/settings.yaml 是否配置）。</p>
          )}
        </div>

        <div className="px-5 py-3 border-t border-white/10 flex justify-end">
          <Button variant="outline" onClick={onClose}>
            关闭
          </Button>
        </div>
      </motion.div>
    </motion.div>
  );
}
