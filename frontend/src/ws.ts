// WebSocket 客户端 + 事件契约 + REST 接口（严格对齐后端 src/zhuli/core/events.py）
// 新增事件类型时必须同步：core/events.py 的 Event 联合类型 与 本文件的 ZEvent。

export interface ZAction {
  action: string;
  target?: string | null;
  value?: string | null;
  reason?: string | null;
  thought?: string | null;
}

export interface ZHighlight {
  selector: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface PlanEvent {
  type: "plan";
  subtasks: string[];
  current: string;
  done: string[];
  verification?: string[];
}
export interface ReflectionEvent {
  type: "reflection";
  status: "continue" | "replan" | "done" | "escalate";
  reason: string;
}
export interface StepLogEvent {
  type: "step_log";
  step: number;
  action: ZAction;
  observation_summary: string;
}
export interface ScreenshotEvent {
  type: "screenshot";
  image_b64: string;
  highlights: ZHighlight[];
}
export interface CommandEvent {
  type: "command";
  cmd: string;
  stream: "stdout" | "stderr";
  line: string;
  exit_code?: number | null;
}
export interface ConfirmRequestEvent {
  type: "confirm_request";
  reason: string;
  pending_action: ZAction;
}
export interface CredentialRequestEvent {
  type: "credential_request";
  fields: string[];
}
export interface ChatEvent {
  type: "chat";
  role: "user" | "assistant" | "system";
  text: string;
}
export interface StatusEvent {
  type: "status";
  state: "idle" | "running" | "paused" | "awaiting_confirm" | "awaiting_credential" | "stopped" | "error" | "done";
  message?: string | null;
}
export interface SkillEvent {
  type: "skill";
  name: string;
  description: string;
  action: "learned" | "updated" | "matched" | "promoted";
  reason?: string | null;
}
export interface ThinkEvent {
  type: "think";
  stage: "plan" | "decide" | "reflect";
  text: string;
}
export interface AgentEvent {
  type: "agent";
  agent: string;
  stage: "plan" | "observe" | "decide" | "critique" | "risk" | "reflect" | "skill" | "delegate" | "consensus";
  summary: string;
  verdict?: string | null;
}
export interface ErrorEvent {
  type: "error";
  message: string;
}

export type ZEvent =
  | PlanEvent
  | ReflectionEvent
  | StepLogEvent
  | ScreenshotEvent
  | CommandEvent
  | ConfirmRequestEvent
  | CredentialRequestEvent
  | ChatEvent
  | StatusEvent
  | SkillEvent
  | ThinkEvent
  | AgentEvent
  | ErrorEvent;

/* ---------------- REST 返回结构 ---------------- */

export interface ConfigResponse {
  providers: string[];
  routing: Record<string, string>;
  integrations: string[];
}
export interface AgentInfo {
  name: string;
  role: string;
  provider?: string | null;
  model?: string | null;
  capability?: string | null;
  tool?: string | null;
}
export interface AgentsResponse {
  agents: AgentInfo[];
  total: number;
  mode: "single" | "multi" | "hive";
}
export interface SecurityInfo {
  available?: boolean;
  iterations?: number;
  master_source?: string;
  envelope?: boolean;
  [k: string]: unknown;
}
export interface SkillItem {
  id: number;
  name: string;
  description: string;
  trigger?: string;
  uses?: number;
  successes?: number;
  [k: string]: unknown;
}
export interface ModelsResponse {
  providers: string[];
  routing: Record<string, string>;
  overrides: Record<string, string>;
  capabilities: string[];
}

/* ---------------- WebSocket ---------------- */

export function connectWs(onEvent: (e: ZEvent) => void): WebSocket {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onopen = () => onEvent({ type: "status", state: "idle", message: "已连接控制台" });
  ws.onmessage = (ev) => {
    try {
      onEvent(JSON.parse(ev.data) as ZEvent);
    } catch {
      /* 忽略畸形帧 */
    }
  };
  ws.onclose = () => onEvent({ type: "status", state: "error", message: "与本地服务断开连接" });
  return ws;
}

async function getJson<T>(url: string, init?: RequestInit): Promise<T | null> {
  try {
    const r = await fetch(url, init);
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

export const api = {
  config: () => getJson<ConfigResponse>("/api/config"),
  agents: () => getJson<AgentsResponse>("/api/agents"),
  skills: () => getJson<SkillItem[]>("/api/skills"),
  security: () => getJson<SecurityInfo>("/api/security"),
  models: () => getJson<ModelsResponse>("/api/models"),
  setModel: (capability: string, provider: string) =>
    getJson<{ ok: boolean }>("/api/models", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ capability, provider }),
    }),
  deleteSkill: (id: number) => getJson<{ ok: boolean }>(`/api/skills/${id}`, { method: "DELETE" }),
};
