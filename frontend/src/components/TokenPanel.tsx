import { Card, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import type { UsageResponse } from "../ws";

interface Props {
  data: UsageResponse | null;
  loading: boolean;
  onReload: () => void;
  onClose: () => void;
}

export default function TokenPanel({ data, loading, onReload, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4" onClick={onClose}>
      <Card className="w-full max-w-3xl max-h-[85vh] overflow-y-auto" >
        <div onClick={(e) => e.stopPropagation()}>
          <CardHeader>
            <CardTitle>Token 用量</CardTitle>
            <Button size="sm" variant="outline" onClick={onReload} disabled={loading}>
              {loading ? "刷新中…" : "刷新"}
            </Button>
            <Button size="sm" variant="ghost" onClick={onClose}>关闭</Button>
          </CardHeader>
          <div className="px-4 pb-4 space-y-4 text-sm text-slate-200">
            {!data && <p className="text-xs text-slate-400">暂无用量数据（还没有真实模型调用，或后端未返回）。</p>}
            {data && (
              <>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-center">
                  {[
                    ["总 token", String(data.total_tokens)],
                    ["输入", String(data.prompt_tokens)],
                    ["输出", String(data.completion_tokens)],
                    ["缓存", String(data.cached_tokens)],
                  ].map(([label, value]) => (
                    <div key={label} className="rounded-lg border border-white/10 bg-white/5 py-2">
                      <div className="font-bold">{value}</div>
                      <div className="text-[10px] text-slate-500">{label}</div>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-slate-400">
                  调用 {data.calls} 次（已知用量 {data.known_calls} 次，未知用量 {data.unknown_calls} 次）。
                  {data.cost !== null && data.cost !== undefined
                    ? ` 费用约 ${data.cost}（按运营者提供的单价计算）。`
                    : " 未配置单价，只显示 token 数，不编造成本。"}
                </p>
                <div>
                  <h3 className="font-medium mb-1">按模型</h3>
                  {data.by_model.length === 0 ? (
                    <p className="text-xs text-slate-400">暂无</p>
                  ) : (
                    data.by_model.map((m) => (
                      <p key={m.model} className="text-xs">• {m.model}：{m.calls} 次，{m.total_tokens} token</p>
                    ))
                  )}
                </div>
                <div>
                  <h3 className="font-medium mb-1">按天</h3>
                  {data.by_day.length === 0 ? (
                    <p className="text-xs text-slate-400">暂无</p>
                  ) : (
                    data.by_day.map((d) => (
                      <p key={d.date} className="text-xs">• {d.date}：{d.calls} 次，{d.total_tokens} token</p>
                    ))
                  )}
                </div>
                <div>
                  <h3 className="font-medium mb-1">蜂巢与非蜂巢</h3>
                  <p className="text-xs">蜂巢：{data.hive.hive.calls} 次，{data.hive.hive.total_tokens} token；非蜂巢：{data.hive.non_hive.calls} 次，{data.hive.non_hive.total_tokens} token；模式未知：{data.hive.unknown_mode.calls} 次，{data.hive.unknown_mode.total_tokens} token。</p>
                  <p className="text-xs text-amber-200">注意：蜂巢模式 token 消耗约为普通流水线的 3 倍，默认关闭。</p>
                </div>
                <div>
                  <h3 className="font-medium mb-1">最近记录</h3>
                  {data.recent.length === 0 ? (
                    <p className="text-xs text-slate-400">暂无</p>
                  ) : (
                    data.recent.slice(0, 20).map((r, i) => (
                      <p key={i} className="text-xs break-words">
                        • {r.ts} {r.provider}/{r.model}（{r.capability}，{r.kind}
                        {r.hive === true ? "，蜂巢" : r.hive === false ? "，非蜂巢" : ""}
                        {r.session_id ? `，会话 ${r.session_id}` : ""}）：
                        {r.usage_known ? `${r.total_tokens ?? 0} token` : "用量未知"}
                      </p>
                    ))
                  )}
                </div>
                {data.notes?.map((n) => (
                  <p key={n} className="text-[11px] text-slate-500">• {n}</p>
                ))}
                <p className="text-[11px] text-slate-500">测试、占位和模拟调用不计入上面所有总数；没有返回用量的调用记为未知，不记为零。</p>
              </>
            )}
          </div>
        </div>
      </Card>
    </div>
  );
}
