import { useEffect, useRef, useState } from "react";
import { Terminal, Monitor } from "lucide-react";
import { api, connectWs } from "./ws";
import type {
  AgentInfo, AgentsResponse, ModelsResponse, SecurityInfo, SkillItem, ZAction, ZEvent,
} from "./ws";
import TopBar from "./components/TopBar";
import ChatPanel, { type ChatMsg } from "./components/ChatPanel";
import PlanPanel, { type PlanState } from "./components/PlanPanel";
import OperationView, { type Shot } from "./components/OperationView";
import TerminalPanel, { type TermLine } from "./components/TerminalPanel";
import RightDock, { type DockTab } from "./components/RightDock";
import MetricsStrip, { type PulsePoint } from "./components/MetricsStrip";
import ControlBar, { type ControlAction } from "./components/ControlBar";
import ConfirmModal from "./components/ConfirmModal";
import CredentialCard from "./components/CredentialCard";
import AgentsModal from "./components/AgentsModal";
import SettingsModal from "./components/SettingsModal";
import type { AgentActivity } from "./components/AgentSwarm";
import type { SkillActivity } from "./components/SkillPanel";
import type { LogItem } from "./components/LogFeed";
import type { Thought } from "./components/ThinkStream";
import { cn } from "./lib/utils";

export default function App() {
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [plan, setPlan] = useState<PlanState | null>(null);
  const [reflection, setReflection] = useState<{ status: string; reason: string } | null>(null);
  const [logs, setLogs] = useState<LogItem[]>([]);
  const [thoughts, setThoughts] = useState<Thought[]>([]);
  const [activity, setActivity] = useState<AgentActivity[]>([]);
  const [skillActivity, setSkillActivity] = useState<SkillActivity[]>([]);
  const [shot, setShot] = useState<Shot | null>(null);
  const [termLines, setTermLines] = useState<TermLine[]>([]);
  const [pulse, setPulse] = useState<PulsePoint[]>([]);
  const [confirm, setConfirm] = useState<{ reason: string; pending_action: ZAction } | null>(null);
  const [cred, setCred] = useState<{ fields: string[] } | null>(null);

  const [status, setStatusState] = useState("idle");
  const [connected, setConnected] = useState(false);
  const [tools, setTools] = useState<string[]>([]);
  const [targetTool, setTargetTool] = useState("");
  const [view, setView] = useState<"view" | "terminal">("view");
  const [dockTab, setDockTab] = useState<DockTab>("log");
  const [speed, setSpeed] = useState(1);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [skillsHit, setSkillsHit] = useState(0);

  const [agents, setAgents] = useState<AgentsResponse | null>(null);
  const [models, setModels] = useState<ModelsResponse | null>(null);
  const [security, setSecurity] = useState<SecurityInfo | null>(null);
  const [skills, setSkills] = useState<SkillItem[]>([]);
  const [showAgents, setShowAgents] = useState(false);
  const [showSettings, setShowSettings] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const speedRef = useRef(1);
  const lastShotRef = useRef(0);
  const viewRef = useRef<"view" | "terminal">("view");

  const pushChat = (role: ChatMsg["role"], text: string) =>
    setMessages((m) => [...m, { role, text }].slice(-120));

  const loadStatic = async () => {
    const [cfg, ag, sk, sec, md] = await Promise.all([
      api.config(), api.agents(), api.skills(), api.security(), api.models(),
    ]);
    if (cfg) setTools(cfg.integrations ?? []);
    if (ag) setAgents(ag);
    if (sk) setSkills(sk);
    if (sec) setSecurity(sec);
    if (md) setModels(md);
  };

  useEffect(() => {
    const ws = connectWs(handleEvent);
    wsRef.current = ws;
    setConnected(true);
    ws.onclose = () => {
      setConnected(false);
      handleEvent({ type: "status", state: "error", message: "与本地服务断开连接" });
    };
    loadStatic();
    const timer = setInterval(() => {
      api.agents().then((a) => a && setAgents(a));
      api.skills().then((s) => s && setSkills(s));
    }, 20000);
    return () => {
      clearInterval(timer);
      ws.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    speedRef.current = speed;
  }, [speed]);
  useEffect(() => {
    viewRef.current = view;
  }, [view]);

  function handleEvent(e: ZEvent) {
    switch (e.type) {
      case "plan":
        setPlan({ subtasks: e.subtasks, current: e.current, done: e.done, verification: e.verification });
        break;
      case "reflection":
        setReflection({ status: e.status, reason: e.reason });
        break;
      case "step_log":
        setLogs((l) => [...l, { step: e.step, action: e.action, observation_summary: e.observation_summary }].slice(-300));
        setPulse((p) => {
          const bucket = Math.floor(Date.now() / 5000) * 5000;
          const last = p[p.length - 1];
          const next = last && last.t === bucket ? [...p.slice(0, -1), { t: bucket, steps: last.steps + 1 }] : [...p, { t: bucket, steps: 1 }];
          return next.slice(-24);
        });
        break;
      case "screenshot": {
        const now = Date.now();
        const gap = 1000 / speedRef.current;
        if (now - lastShotRef.current < gap) break;
        lastShotRef.current = now;
        setShot({ image: e.image_b64, highlights: e.highlights ?? [], ts: now });
        if (viewRef.current !== "view") setView("view");
        break;
      }
      case "command":
        setTermLines((l) => [...l, { stream: e.stream, line: e.line, ts: Date.now() }].slice(-800));
        if (viewRef.current !== "terminal") setView("terminal");
        break;
      case "confirm_request":
        setConfirm({ reason: e.reason, pending_action: e.pending_action });
        break;
      case "credential_request":
        setCred({ fields: e.fields });
        break;
      case "chat":
        pushChat(e.role, e.text);
        break;
      case "status":
        setStatusState(e.state);
        if (e.state === "running") setStartedAt((prev) => prev ?? Date.now());
        if (e.message) pushChat("system", e.message);
        // 任务收尾：刷新技能库与智能体团队（技能可能已沉淀/升格）
        if (e.state === "done" || e.state === "error") {
          api.skills().then((s) => s && setSkills(s));
          api.agents().then((a) => a && setAgents(a));
        }
        break;
      case "think":
        setThoughts((t) => [...t, { stage: e.stage, text: e.text, ts: Date.now() }].slice(-120));
        break;
      case "agent":
        setActivity((a) => [
          ...a,
          { agent: e.agent, stage: e.stage, summary: e.summary, verdict: e.verdict ?? null, ts: Date.now() },
        ].slice(-120));
        break;
      case "skill":
        setSkillActivity((s) => [
          ...s,
          { name: e.name, action: e.action, reason: e.reason ?? null, ts: Date.now() },
        ].slice(-120));
        if (e.action === "matched") setSkillsHit((n) => n + 1);
        break;
      case "error":
        pushChat("system", "⚠ " + e.message);
        break;
    }
  }

  const send = (payload: Record<string, unknown>) => {
    wsRef.current?.send(JSON.stringify(payload));
  };

  const sendTask = (goal: string, tool: string) => {
    pushChat("user", goal);
    setLogs([]);
    setThoughts([]);
    setActivity([]);
    setSkillActivity([]);
    setTermLines([]);
    setPulse([]);
    setShot(null);
    setReflection(null);
    setSkillsHit(0);
    setStartedAt(Date.now());
    setStatusState("running");
    send({ type: "task", goal, target_tool: tool });
  };

  const sendControl = (action: ControlAction) => send({ type: "control", action });
  const resolveConfirm = (approved: boolean) => {
    send({ type: "confirm", approved });
    setConfirm(null);
  };
  const submitCred = (values: Record<string, string>) => {
    send({ type: "credential", values });
    setCred(null);
  };
  const changeModel = (capability: string, provider: string) => {
    // 先本地回显，再请求后端切换，最后以服务端「实际生效」结果为准
    setModels((m) => (m ? { ...m, routing: { ...m.routing, [capability]: provider } } : m));
    api.setModel(capability, provider).then(() => {
      api.models().then((m) => m && setModels(m));
    });
  };

  const busy =
    status === "running" || status === "awaiting_confirm" || status === "awaiting_credential";

  return (
    <div className="h-full flex flex-col">
      <TopBar
        status={status}
        connected={connected}
        mode={agents?.mode ?? "multi"}
        models={models}
        onModelChange={changeModel}
        onOpenAgents={() => setShowAgents(true)}
        onOpenSettings={() => setShowSettings(true)}
      />

      <main className="flex-1 min-h-0 pt-14 pb-[76px] p-3 grid grid-cols-12 gap-3">
        <section className="col-span-3 min-h-0">
          <ChatPanel
            messages={messages}
            tools={tools}
            targetTool={targetTool}
            onTargetChange={setTargetTool}
            onSend={sendTask}
            disabled={busy}
          />
        </section>

        <section className="col-span-6 min-h-0 flex flex-col gap-3">
          <div className="grid grid-cols-3 gap-3 shrink-0">
            <div className="col-span-2">
              <PlanPanel plan={plan} reflection={reflection} />
            </div>
            <MetricsStrip pulse={pulse} startedAt={startedAt} skillsHit={skillsHit} />
          </div>

          <div className="flex-1 min-h-0 glass rounded-2xl overflow-hidden flex flex-col">
            <div className="flex items-center gap-2 px-2 py-1.5 border-b border-white/10">
              {(["view", "terminal"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setView(t)}
                  className={cn(
                    "flex items-center gap-1 text-xs px-3 py-1 rounded-lg border transition cursor-pointer",
                    view === t
                      ? "border-neon-cyan/50 text-neon-cyan bg-neon-cyan/10"
                      : "border-transparent text-slate-400 hover:bg-white/5"
                  )}
                >
                  {t === "view" ? <Monitor className="w-3.5 h-3.5" /> : <Terminal className="w-3.5 h-3.5" />}
                  {t === "view" ? "操作视图" : "终端输出"}
                </button>
              ))}
              <span className="ml-auto text-[11px] text-slate-500">
                {targetTool ? `目标：${targetTool}` : "目标：本助理"}
              </span>
            </div>
            <div className="flex-1 min-h-0 p-2">
              {view === "view" ? (
                <OperationView shot={shot} running={busy} />
              ) : (
                <TerminalPanel lines={termLines} onClear={() => setTermLines([])} tool={targetTool} />
              )}
            </div>
          </div>
        </section>

        <section className="col-span-3 min-h-0">
          <RightDock
            tab={dockTab}
            onTab={setDockTab}
            logs={logs}
            thoughts={thoughts}
            agents={(agents?.agents ?? []) as AgentInfo[]}
            activity={activity}
            skills={skills}
            skillActivity={skillActivity}
            mode={agents?.mode ?? "multi"}
            onReloadSkills={() => api.skills().then((s) => s && setSkills(s))}
          />
        </section>
      </main>

      <footer className="fixed bottom-0 inset-x-0 z-30 px-3 pb-3 pt-2 bg-gradient-to-t from-ink-900 via-ink-900/95 to-transparent">
        <ControlBar status={status} speed={speed} onControl={sendControl} onSpeed={setSpeed} />
      </footer>

      {confirm && <ConfirmModal request={confirm} onResolve={resolveConfirm} />}
      {cred && <CredentialCard fields={cred.fields} onSubmit={submitCred} onCancel={() => submitCred({})} />}
      {showAgents && <AgentsModal data={agents} onClose={() => setShowAgents(false)} />}
      {showSettings && (
        <SettingsModal
          models={models}
          security={security}
          integrations={tools}
          onModelChange={changeModel}
          onClose={() => setShowSettings(false)}
        />
      )}
    </div>
  );
}
