/* Zhuli v0.2.0 right sidebar (static console overlay, no React rebuild).
   The React app already owns the main console. This script adds a
   collapsible right sidebar for current task status, in the same
   hacker theme, by listening to the existing WebSocket events only.
   It never sends task, confirm or credential messages, so the main
   console approval flow stays the single source of truth. All text
   from events is inserted with textContent, never as HTML.
   Choice is remembered in localStorage under "zhuli-sidebar". */
(function () {
  "use strict";
  var KEY = "zhuli-sidebar";
  var state = {
    goal: "", status: "idle", subtasks: [], current: "", done: [],
    verification: [], skills: [], pending: null, pendingCred: null, trace: []
  };

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }
  function empty(text) { var p = el("p", "zhuli-side-empty", text); return p; }

  var aside = el("aside", "", null);
  aside.id = "zhuli-right-sidebar";
  var head = el("div", "zhuli-side-head", null);
  head.appendChild(el("h2", "", "任务状态"));
  var toggle = el("button", "zhuli-side-toggle", "收起 →");
  toggle.type = "button";
  toggle.title = "收起右侧栏";
  head.appendChild(toggle);
  aside.appendChild(head);

  var goalBox = el("div", "zhuli-side-section", null);
  goalBox.appendChild(el("h3", "", "任务目标"));
  var goalEl = el("p", "", "");
  goalBox.appendChild(goalEl);
  aside.appendChild(goalBox);

  var statusBox = el("div", "zhuli-side-section", null);
  statusBox.appendChild(el("h3", "", "总体状态"));
  var statusEl = el("p", "", "");
  statusBox.appendChild(statusEl);
  aside.appendChild(statusBox);

  var planBox = el("div", "zhuli-side-section", null);
  planBox.appendChild(el("h3", "", "计划"));
  var planEl = el("div", "", null);
  planBox.appendChild(planEl);
  aside.appendChild(planBox);

  var skillBox = el("div", "zhuli-side-section", null);
  skillBox.appendChild(el("h3", "", "本次任务技能"));
  var skillEl = el("div", "", null);
  skillBox.appendChild(skillEl);
  aside.appendChild(skillBox);

  var apprBox = el("div", "zhuli-side-section", null);
  apprBox.appendChild(el("h3", "", "待确认 / 待填写"));
  var apprEl = el("div", "", null);
  apprBox.appendChild(apprEl);
  aside.appendChild(apprBox);

  var traceBox = el("div", "zhuli-side-section", null);
  var details = document.createElement("details");
  var summary = el("summary", "", "事件轨迹（最近 20 条）");
  details.appendChild(summary);
  var traceEl = el("div", "", null);
  details.appendChild(traceEl);
  traceBox.appendChild(details);
  aside.appendChild(traceBox);

  var expand = el("button", "", "◀ 任务状态");
  expand.id = "zhuli-sidebar-expand";
  expand.type = "button";
  expand.title = "展开右侧栏";

  function apply(open) {
    document.body.classList.toggle("zhuli-sidebar-open", open);
    document.body.classList.toggle("zhuli-sidebar-collapsed", !open);
    try { localStorage.setItem(KEY, open ? "open" : "collapsed"); } catch (e) {}
  }
  toggle.addEventListener("click", function () { apply(false); });
  expand.addEventListener("click", function () { apply(true); });

  function render() {
    goalEl.textContent = state.goal || "暂无任务";
    statusEl.textContent = state.status || "空闲";
    planEl.innerHTML = "";
    if (!state.subtasks.length) {
      planEl.appendChild(empty("暂无计划（任务开始后会显示子任务）"));
    } else {
      var doneSet = {};
      state.done.forEach(function (d) { doneSet[d] = true; });
      state.subtasks.forEach(function (s) {
        var mark = doneSet[s] ? "[x] " : (s === state.current ? "[>] " : "[ ] ");
        planEl.appendChild(el("p", "", mark + s));
      });
      if (state.verification.length) {
        planEl.appendChild(el("p", "zhuli-side-note",
          "完成标准：" + state.verification.join("；")));
      }
    }
    skillEl.innerHTML = "";
    if (!state.skills.length) {
      skillEl.appendChild(empty("暂无技能（任务开始后命中或学会的技能会显示在这里）"));
    } else {
      state.skills.forEach(function (s) {
        skillEl.appendChild(el("p", "", s.name + "（" + s.action + "）" +
          (s.description ? "：" + s.description : "")));
      });
    }
    apprEl.innerHTML = "";
    if (!state.pending && !state.pendingCred) {
      apprEl.appendChild(empty("暂无待确认事项"));
    }
    if (state.pending) {
      apprEl.appendChild(el("p", "", "等待确认：" + (state.pending.reason || "")));
      if (state.pending.action) {
        apprEl.appendChild(el("p", "", "待执行：" + (state.pending.action.action || "") +
          " " + (state.pending.action.target || "")));
      }
      apprEl.appendChild(el("p", "zhuli-side-note", "请在主控制台确认"));
    }
    if (state.pendingCred) {
      apprEl.appendChild(el("p", "", "等待填写凭据字段：" +
        state.pendingCred.fields.join("、")));
      apprEl.appendChild(el("p", "zhuli-side-note", "请在主控制台填写"));
    }
    traceEl.innerHTML = "";
    if (!state.trace.length) {
      traceEl.appendChild(empty("暂无事件"));
    } else {
      state.trace.slice(0, 20).forEach(function (t) {
        traceEl.appendChild(el("p", "zhuli-side-trace", t));
      });
    }
  }

  function summaryOf(ev) {
    if (!ev || !ev.type) return "事件";
    if (ev.type === "plan") return "计划：" + (ev.subtasks || []).length + " 个子任务";
    if (ev.type === "status") return "状态：" + ev.state + (ev.message ? "：" + ev.message : "");
    if (ev.type === "skill") return "技能 " + ev.name + "（" + ev.action + "）";
    if (ev.type === "confirm_request") return "等待确认：" + (ev.reason || "");
    if (ev.type === "credential_request") return "等待凭据：" + (ev.fields || []).join("、");
    if (ev.type === "chat") return "对话：" + String(ev.text || "").slice(0, 80);
    if (ev.type === "step_log") return "步骤 " + ev.step + "：" +
      ((ev.action && ev.action.action) || "") + " " + ((ev.action && ev.action.target) || "");
    if (ev.type === "think") return "思考（" + ev.stage + "）：" + String(ev.text || "").slice(0, 80);
    if (ev.type === "agent") return "智能体 " + ev.agent + "（" + ev.stage + "）：" +
      String(ev.summary || "").slice(0, 80);
    if (ev.type === "reflection") return "反思：" + ev.status + "：" + (ev.reason || "");
    if (ev.type === "command") return "命令输出：" + String(ev.line || "").slice(0, 80);
    if (ev.type === "screenshot") return "截图已更新";
    if (ev.type === "error") return "错误：" + (ev.message || "");
    return ev.type;
  }

  function handle(ev) {
    if (!ev || !ev.type) return;
    state.trace.unshift(summaryOf(ev));
    if (state.trace.length > 50) state.trace.length = 50;
    if (ev.type === "chat" && ev.role === "assistant" &&
        typeof ev.text === "string" && ev.text.indexOf("收到任务：") === 0) {
      state.goal = ev.text.slice("收到任务：".length);
    } else if (ev.type === "status") {
      state.status = ev.state;
      if (ev.state === "done" || ev.state === "stopped" || ev.state === "error") {
        state.pending = null; state.pendingCred = null;
      }
    } else if (ev.type === "plan") {
      state.subtasks = ev.subtasks || [];
      state.current = ev.current || "";
      state.done = ev.done || [];
      state.verification = ev.verification || [];
    } else if (ev.type === "skill") {
      var found = false;
      state.skills = state.skills.map(function (s) {
        if (s.name === ev.name) { found = true; return {name: ev.name, action: ev.action, description: ev.description || s.description}; }
        return s;
      });
      if (!found) state.skills.push({name: ev.name, action: ev.action, description: ev.description || ""});
    } else if (ev.type === "confirm_request") {
      state.pending = {reason: ev.reason || "", action: ev.pending_action || null};
    } else if (ev.type === "credential_request") {
      state.pendingCred = {fields: ev.fields || []};
    } else if (ev.type === "step_log") {
      state.pending = null; state.pendingCred = null;
    }
    render();
  }

  function connect() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var ws;
    try { ws = new WebSocket(proto + "//" + location.host + "/ws"); } catch (e) { return; }
    ws.onmessage = function (msg) {
      try { handle(JSON.parse(msg.data)); } catch (e) {}
    };
    ws.onclose = function () { setTimeout(connect, 3000); };
    ws.onerror = function () { try { ws.close(); } catch (e) {} };
  }

  document.body.appendChild(aside);
  document.body.appendChild(expand);
  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}
  apply(saved !== "collapsed");
  render();
  connect();
})();
