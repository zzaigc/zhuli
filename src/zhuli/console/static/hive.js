/* Zhuli v0.2.0 Hive control (static console overlay, no React rebuild).
   Button toggles hive_mode at runtime only, via POST /api/hive, exactly
   like the existing /api/models override: the config file is never
   rewritten, and a restart returns to the config value.
   Label is honest: "Hive mode" plus a subtitle explaining parallel
   proposals plus weighted consensus voting. No effect beyond the
   mechanism itself is claimed.
   Mechanism, as implemented in agents/hive.py and core/orchestrator.py:
   several actors at different temperatures propose in parallel, critic
   and risk vote with weighted scores, the highest score wins, a winner
   judged abort or danger is vetoed, and total failure falls back to a
   single-brain decision. Votes shown here come only from existing
   WebSocket events (hive consensus agent events and hive think events).
   This panel never sends task, confirm or credential messages. */
(function () {
  "use strict";
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  var panel = el("div", "", null);
  panel.id = "zhuli-hive-panel";
  var head = el("div", "zhuli-hive-head", null);
  head.appendChild(el("h2", "", "Hive mode"));
  var toggle = el("button", "zhuli-hive-toggle off", "Hive: OFF");
  toggle.type = "button";
  toggle.title = "运行时切换蜂巢模式（不改写配置文件）";
  head.appendChild(toggle);
  panel.appendChild(head);
  panel.appendChild(el("p", "zhuli-hive-sub",
    "并行提案 + 加权共识投票：多个执行体并行提案，批评与风险加权打分，得分最高者胜出。"));
  panel.appendChild(el("p", "zhuli-hive-mech",
    "机制：被判 abort 或 danger 的胜出者会被否决；全部失效时降级为单脑决策。"));
  panel.appendChild(el("p", "zhuli-hive-warn",
    "注意：蜂巢模式 token 消耗约为普通流水线的 3 倍，默认关闭。重启后恢复为配置文件值。"));

  var modeEl = el("p", "", "当前模式：—");
  panel.appendChild(modeEl);
  var sizeRow = el("div", "zhuli-hive-row", null);
  sizeRow.appendChild(el("label", "", "蜂群规模："));
  var sizeSel = document.createElement("select");
  ["1", "2", "3", "4"].forEach(function (v) {
    var o = document.createElement("option");
    o.value = v; o.textContent = v; sizeSel.appendChild(o);
  });
  sizeRow.appendChild(sizeSel);
  panel.appendChild(sizeRow);

  var voteBox = el("div", "zhuli-hive-votes", null);
  voteBox.appendChild(el("h3", "", "最近一次共识"));
  var voteEl = el("p", "", "暂无共识（开启蜂巢后，下一步决策的投票会显示在这里）");
  voteBox.appendChild(voteEl);
  panel.appendChild(voteBox);

  var currentMode = "multi";
  var currentOn = false;

  function renderStatus(data) {
    if (!data) return;
    currentMode = data.mode || currentMode;
    currentOn = !!data.hive_mode;
    modeEl.textContent = "当前模式：" + currentMode +
      "（蜂巢 " + (currentOn ? "开" : "关") + "，蜂群规模 " + data.hive_size + "）";
    sizeSel.value = String(data.hive_size || 3);
    toggle.textContent = currentOn ? "Hive: ON" : "Hive: OFF";
    toggle.className = "zhuli-hive-toggle " + (currentOn ? "on" : "off");
  }
  function refresh() {
    fetch("/api/hive").then(function (r) { return r.json(); })
      .then(renderStatus).catch(function () {});
  }
  function post(body) {
    fetch("/api/hive", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); })
      .then(function (d) { if (d.ok) renderStatus(d); }).catch(function () {});
  }
  toggle.addEventListener("click", function () { post({hive_mode: !currentOn}); });
  sizeSel.addEventListener("change", function () {
    post({hive_mode: currentOn, hive_size: parseInt(sizeSel.value, 10)});
  });

  function clean(text) {
    return String(text || "").replace(/^🐝\s*/, "").slice(0, 400);
  }
  function connect() {
    var proto = location.protocol === "https:" ? "wss:" : "ws:";
    var ws;
    try { ws = new WebSocket(proto + "//" + location.host + "/ws"); } catch (e) { return; }
    ws.onmessage = function (msg) {
      var ev;
      try { ev = JSON.parse(msg.data); } catch (e) { return; }
      if (ev.type === "agent" && ev.agent === "hive" && ev.stage === "consensus") {
        voteEl.textContent = clean(ev.summary) + (ev.verdict ? " | " + ev.verdict : "");
      } else if (ev.type === "think" && ev.stage === "decide" &&
                 typeof ev.text === "string" && ev.text.indexOf("蜂巢共识") >= 0) {
        voteEl.textContent = clean(ev.text);
      } else if (ev.type === "status") {
        refresh();
      }
    };
    ws.onclose = function () { setTimeout(connect, 3000); };
    ws.onerror = function () { try { ws.close(); } catch (e) {} };
  }

  document.body.appendChild(panel);
  refresh();
  connect();
})();
