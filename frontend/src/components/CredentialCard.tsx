import { useState } from "react";
import { motion } from "framer-motion";
import { Lock, KeyRound, ShieldOff } from "lucide-react";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

interface Props {
  fields: string[];
  onSubmit: (values: Record<string, string>) => void;
  onCancel: () => void;
}

export default function CredentialCard({ fields, onSubmit, onCancel }: Props) {
  const [values, setValues] = useState<Record<string, string>>({});

  const submit = () => {
    onSubmit(values);
    // 提交后立即清空内存中的明文（不保留、不落盘、不进日志）
    setValues({});
  };

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
        <div className="flex items-center gap-2 mb-1">
          <Lock className="w-5 h-5 text-neon-cyan" />
          <span className="font-semibold neon-text">安全凭据卡片</span>
        </div>
        <p className="text-xs text-slate-400 mb-4 leading-relaxed">
          AI 只收到「此处需要凭据」的信号，
          <span className="text-neon-cyan"> 明文不会进入模型、日志与磁盘</span>
          ；提交后本卡片立即清空内存。
        </p>

        <div className="space-y-3">
          {fields.map((f, idx) => (
            <div key={f}>
              <label className="text-xs text-slate-400 flex items-center gap-1">
                <KeyRound className="w-3 h-3" />
                {f}
              </label>
              <Input
                type="password"
                autoFocus={idx === 0}
                value={values[f] || ""}
                onChange={(e) => setValues((v) => ({ ...v, [f]: e.target.value }))}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submit();
                }}
                className="mt-1"
                placeholder={`请输入 ${f}`}
              />
            </div>
          ))}
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <Button variant="outline" onClick={onCancel}>
            <ShieldOff className="w-3.5 h-3.5" /> 取消
          </Button>
          <Button variant="default" onClick={submit}>
            注入并继续
          </Button>
        </div>
      </motion.div>
    </motion.div>
  );
}
