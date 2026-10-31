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
  head.title = "拖动此处可移动蜂巢面板";
  head.appendChild(el("h2", "", "Hive mode"));
  var toggle = el("button", "zhuli-hive-toggle off", "Hive: OFF");
  toggle.type = "button";
  toggle.title = "运行时切换蜂巢模式（不改写配置文件）";
  head.appendChild(toggle);
  var collapseBtn = el("button", "zhuli-hive-collapse", "收起");
  collapseBtn.type = "button";
  collapseBtn.title = "收起蜂巢面板，变成可拖动的小圆按钮";
  collapseBtn.setAttribute("aria-label", "收起蜂巢面板，变成可拖动的小圆按钮");
  head.appendChild(collapseBtn);
  var resetBtn = el("button", "zhuli-hive-reset", "复位");
  resetBtn.type = "button";
  resetBtn.title = "恢复蜂巢面板到默认底部居中位置";
  resetBtn.setAttribute("aria-label", "恢复蜂巢面板到默认底部居中位置");
  head.appendChild(resetBtn);
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
  var sizeInput = document.createElement("input");
  sizeInput.type = "number"; sizeInput.min = "1"; sizeInput.step = "1"; sizeInput.value = "3";
  sizeInput.className = "zhuli-hive-size-input";
  sizeInput.title = "输入大于等于 1 的整数，无上限；点“应用规模”才生效";
  sizeInput.setAttribute("aria-label", "蜂群规模，输入大于等于 1 的整数");
  sizeRow.appendChild(sizeInput);
  var applySizeBtn = el("button", "zhuli-hive-apply", "应用规模");
  applySizeBtn.type = "button";
  applySizeBtn.title = "确认应用上面输入的蜂群规模";
  sizeRow.appendChild(applySizeBtn);
  panel.appendChild(sizeRow);
  var presetRow = el("div", "zhuli-hive-row zhuli-hive-presets", null);
  presetRow.appendChild(el("label", "", "常用："));
  ["1", "3", "5", "8"].forEach(function (v) {
    var b = el("button", "zhuli-hive-preset", v);
    b.type = "button";
    b.title = "把规模填为 " + v + "（还需点“应用规模”确认）";
    b.addEventListener("click", function () { sizeInput.value = v; updateEstimate(); });
    presetRow.appendChild(b);
  });
  panel.appendChild(presetRow);
  var modeRow = el("div", "zhuli-hive-row", null);
  modeRow.appendChild(el("label", "", "规模模式："));
  var modeSel = document.createElement("select");
  [["manual", "手动"], ["auto", "自动"]].forEach(function (kv) {
    var o = document.createElement("option");
    o.value = kv[0]; o.textContent = kv[1]; modeSel.appendChild(o);
  });
  modeRow.appendChild(modeSel);
  panel.appendChild(modeRow);
  var estimateEl = el("p", "zhuli-hive-estimate", "");
  panel.appendChild(estimateEl);
  function estimateText(size) {
    if (!size || isNaN(size) || size < 1 || Math.floor(size) !== size) {
      return "规模无效：请输入大于等于 1 的整数，才会应用；小于 1 或非整数会被拒绝且不改动当前规模。";
    }
    var t = "预估 token：约 " + size + " 倍单脑成本（规模 3 约 3 倍，规模 8 约 8 倍）。";
    if (size > 16) {
      t += " 警告：规模超过 16 后成本、延迟与噪声都会大幅上升，大蜂群不一定更好，请再次确认后再点“应用规模”。";
    } else if (size > 8) {
      t += " 注意：规模超过 8 后 token 与延迟都会明显上升，请确认确实需要再点“应用规模”。";
    }
    return t;
  }
  function updateEstimate() {
    estimateEl.textContent = estimateText(parseInt(sizeInput.value, 10));
  }
  sizeInput.addEventListener("input", updateEstimate);
  sizeInput.addEventListener("change", updateEstimate);

  var voteBox = el("div", "zhuli-hive-votes", null);
  voteBox.appendChild(el("h3", "", "最近一次共识"));
  var voteEl = el("p", "", "暂无共识（开启蜂巢后，下一步决策的投票会显示在这里）");
  voteBox.appendChild(voteEl);
  panel.appendChild(voteBox);
  var autoEl = el("p", "zhuli-hive-auto", "");
  panel.appendChild(autoEl);

  // ---- 可拖动、可收起（纯界面行为，不调任何接口、不改蜂巢状态）----
  var LS_KEY = "zhuli-hive-panel-state";
  function loadState() {
    try { var s = JSON.parse(localStorage.getItem(LS_KEY) || "null"); return (s && typeof s === "object") ? s : {}; }
    catch (e) { return {}; }
  }
  function saveState(s) {
    try { localStorage.setItem(LS_KEY, JSON.stringify(s)); } catch (e) {}
  }
  var savedState = loadState();
  function clampPos(left, top, w, h) {
    var minTop = 60;
    return {
      left: Math.max(0, Math.min(left, Math.max(0, window.innerWidth - 80))),
      top: Math.max(minTop, Math.min(top, Math.max(minTop, window.innerHeight - 60)))
    };
  }
  function defaultPanelTop() {
    return Math.max(60, window.innerHeight - 92 - panel.offsetHeight);
  }
  function defaultPanelLeft() {
    // v0.3.0 修正：默认位置从左下角改到底部居中。左下角默认值会盖住
    // 指令台的任务输入区与双向开关（实测 1280×800 下开关点不到），
    // 而底部居中在 1280 宽时正好落在中间列，不盖左侧输入区，也不
    // 盖右侧栏（右侧栏覆盖层在更右且 z-index 更高，右下角反而会让
    // 面板按钮点不到）。面板仍可拖到任意位置，拖动位置会保存。
    return Math.max(0, Math.floor((window.innerWidth - panel.offsetWidth) / 2));
  }
  function applyPanelPos(pos) {
    panel.style.left = pos.left + "px";
    panel.style.top = pos.top + "px";
    panel.style.bottom = "auto";
  }
  function resetPanelPos() {
    savedState = {};
    saveState({});
    applyPanelPos({ left: defaultPanelLeft(), top: defaultPanelTop() });
  }
  var fab = el("div", "zhuli-hive-fab off", null);
  fab.id = "zhuli-hive-fab";
  fab.tabIndex = 0;
  fab.setAttribute("role", "button");
  fab.title = "点击展开蜂巢面板，双击恢复默认位置；拖动可移动";
  fab.setAttribute("aria-label", "展开蜂巢面板，双击恢复默认位置");
  fab.appendChild(el("span", "zhuli-hive-fab-mark", "🐝"));
  var fabStateEl = el("span", "zhuli-hive-fab-state", "OFF");
  fab.appendChild(fabStateEl);
  function defaultCirclePos() {
    // 与面板默认位置一致：底部居中，避免圆按钮默认盖住输入区左角。
    return { left: Math.max(0, Math.floor((window.innerWidth - 60) / 2)),
             top: Math.max(60, window.innerHeight - 92 - 60) };
  }
  function applyCirclePos(pos) {
    var p = clampPos(pos.left, pos.top, 60, 60);
    fab.style.left = p.left + "px";
    fab.style.top = p.top + "px";
  }
  function showPanel() {
    fab.style.display = "none";
    panel.style.display = "";
    if (savedState.panelPos) { applyPanelPos(savedState.panelPos); }
    else { applyPanelPos({ left: defaultPanelLeft(), top: defaultPanelTop() }); }
  }
  function showCircle(fromPanel) {
    panel.style.display = "none";
    fab.style.display = "flex";
    if (fromPanel) {
      var r = panel.getBoundingClientRect();
      applyCirclePos({ left: r.left, top: r.top });
    } else if (savedState.circlePos) {
      applyCirclePos(savedState.circlePos);
    } else {
      applyCirclePos(defaultCirclePos());
    }
  }
  function collapsePanel() {
    var r = panel.getBoundingClientRect();
    savedState.panelPos = clampPos(r.left, r.top, r.width, r.height);
    savedState.collapsed = true;
    saveState(savedState);
    showCircle(true);
  }
  function expandPanel() {
    savedState.collapsed = false;
    saveState(savedState);
    showPanel();
  }
  function resetCirclePos() {
    savedState = { collapsed: true };
    saveState(savedState);
    applyCirclePos(defaultCirclePos());
  }
  collapseBtn.addEventListener("click", collapsePanel);
  resetBtn.addEventListener("click", resetPanelPos);
  var fabClickTimer = null;
  function makeDraggable(handle, onMove, onEnd) {
    handle.addEventListener("pointerdown", function (e) {
      if (e.target && e.target.closest && e.target.closest("button,select,input,textarea,a")) return;
      var startX = e.clientX, startY = e.clientY, moved = 0;
      var rect = handle.getBoundingClientRect();
      var startLeft = rect.left, startTop = rect.top;
      try { handle.setPointerCapture(e.pointerId); } catch (err) {}
      function onMoveEv(ev) {
        var dx = ev.clientX - startX, dy = ev.clientY - startY;
        moved = Math.max(moved, Math.abs(dx) + Math.abs(dy));
        onMove(startLeft + dx, startTop + dy);
      }
      function onUpEv() {
        handle.removeEventListener("pointermove", onMoveEv);
        handle.removeEventListener("pointerup", onUpEv);
        handle.removeEventListener("pointercancel", onUpEv);
        if (onEnd) onEnd(moved);
      }
      handle.addEventListener("pointermove", onMoveEv);
      handle.addEventListener("pointerup", onUpEv);
      handle.addEventListener("pointercancel", onUpEv);
    });
  }
  makeDraggable(head, function (left, top) {
    var r = panel.getBoundingClientRect();
    applyPanelPos(clampPos(left, top, r.width, r.height));
  }, function () {
    var r = panel.getBoundingClientRect();
    savedState.panelPos = clampPos(r.left, r.top, r.width, r.height);
    saveState(savedState);
  });
  makeDraggable(fab, function (left, top) {
    applyCirclePos({ left: left, top: top });
  }, function (moved) {
    if (moved >= 5) {
      var r = fab.getBoundingClientRect();
      savedState.circlePos = clampPos(r.left, r.top, 60, 60);
      savedState.collapsed = true;
      saveState(savedState);
      return;
    }
    if (fabClickTimer) {
      clearTimeout(fabClickTimer);
      fabClickTimer = null;
      resetCirclePos();
      return;
    }
    fabClickTimer = setTimeout(function () { fabClickTimer = null; expandPanel(); }, 250);
  });
  fab.addEventListener("keydown", function (e) {
    if (e.key === "Enter" || e.key === " ") { e.preventDefault(); expandPanel(); }
  });

  var currentMode = "multi";
  var currentOn = false;

  function renderStatus(data) {
    if (!data) return;
    currentMode = data.mode || currentMode;
    currentOn = !!data.hive_mode;
    var sizeMode = data.hive_size_mode || "manual";
    modeEl.textContent = "当前模式：" + currentMode +
      "（蜂巢 " + (currentOn ? "开" : "关") + "，蜂群规模 " + data.hive_size +
      "，规模模式 " + (sizeMode === "auto" ? "自动" : "手动") + "）";
    sizeInput.value = String(data.hive_size || 3);
    modeSel.value = sizeMode;
    updateEstimate();
    if (sizeMode === "auto" && data.last_auto) {
      autoEl.textContent = "自动规模：" + data.last_auto.size +
        "（原因：" + (data.last_auto.reason || "") + "；自动范围 2~8，仅为启发式估计，不是保证最优；可随时切回手动）";
    } else if (sizeMode === "auto") {
      autoEl.textContent = "自动模式：下一次蜂巢决策时会按任务自动选规模（2~8），原因会在这里显示；可随时切回手动。";
    } else {
      autoEl.textContent = "";
    }
    toggle.textContent = currentOn ? "Hive: ON" : "Hive: OFF";
    toggle.className = "zhuli-hive-toggle " + (currentOn ? "on" : "off");
    fabStateEl.textContent = currentOn ? "ON" : "OFF";
    fab.className = "zhuli-hive-fab " + (currentOn ? "on" : "off");
    fab.setAttribute("aria-label", "展开蜂巢面板，当前蜂巢" + (currentOn ? "开" : "关") + "，双击恢复默认位置");
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
  applySizeBtn.addEventListener("click", function () {
    var v = parseInt(sizeInput.value, 10);
    if (isNaN(v) || v < 1 || String(sizeInput.value).trim() !== String(v)) {
      estimateEl.textContent = estimateText(NaN);
      return;
    }
    post({hive_mode: currentOn, hive_size: v});
  });
  modeSel.addEventListener("change", function () {
    post({hive_size_mode: modeSel.value});
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

  // v0.3.0: React session switching clears the last consensus shown here.
  window.addEventListener("zhuli-session-switch", function () {
    voteEl.textContent = "暂无共识（开启蜂巢后，下一步决策的投票会显示在这里）";
  });

  document.body.appendChild(panel);
  document.body.appendChild(fab);
  if (savedState.collapsed) { showCircle(false); } else { showPanel(); }
  updateEstimate();
  refresh();
  connect();
})();
