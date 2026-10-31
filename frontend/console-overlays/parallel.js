/* Zhuli v0.3.0 并行子目标开关（静态控制台覆盖层，无需 React 重构建）。
   开关调用 POST /api/parallel，运行时覆盖只在内存中，重启后恢复
   配置 policy.parallel_enabled 的值，绝不改写配置文件。
   规则（与 src/zhuli/core/parallel.py 一致）：
   - 独立子任务分组并行思考，工具执行加锁串行；
   - 浏览器步骤、依赖步骤、共享文件/工具目标的步骤永远不与他人同组；
   - 执行前第二道防线会把含浏览器步骤的组拆回单步；
   - Hive 模式下强制顺序执行，避免双重并行打乱蜂巢投票。
   本面板不发送任务/确认/凭据消息，只读写 /api/parallel。 */
(function () {
  "use strict";
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = text;
    return n;
  }

  var section = el("div", "zhuli-parallel-section", null);
  var head = el("div", "zhuli-parallel-head", null);
  head.appendChild(el("h3", "", "并行子目标"));
  var toggle = el("button", "zhuli-parallel-toggle off", "并行：关");
  toggle.type = "button";
  toggle.title = "运行时开关并行子目标（不改写配置文件）";
  head.appendChild(toggle);
  section.appendChild(head);
  section.appendChild(el("p", "zhuli-parallel-sub",
    "独立子任务分组：组内思考并行，工具执行加锁串行；浏览器步骤永远单步。"));
  section.appendChild(el("p", "zhuli-parallel-warn",
    "Hive 模式下强制顺序执行（蜂巢已有并行提案与投票，不叠加并行）。"));
  var statusEl = el("p", "", "并行状态：—");
  section.appendChild(statusEl);
  var groupsEl = el("p", "", "当前分组：—");
  section.appendChild(groupsEl);

  var currentOn = false;
  function renderStatus(data) {
    if (!data) return;
    currentOn = !!data.parallel_enabled;
    toggle.textContent = currentOn ? "并行：开" : "并行：关";
    toggle.className = "zhuli-parallel-toggle " + (currentOn ? "on" : "off");
    statusEl.textContent = "并行状态：" + (currentOn ? "开" : "关") +
      "（配置 " + (data.config_parallel_enabled ? "开" : "关") +
      (data.hive_mode ? "，Hive 模式强制顺序" : "") + "）";
    var groups = data.groups || [];
    if (!groups.length) {
      groupsEl.textContent = "当前分组：—（提交任务并生成计划后显示）";
    } else {
      groupsEl.textContent = "当前分组：" + groups.map(function (g, i) {
        return "组" + (i + 1) + "：" + g.join(" + ");
      }).join("；");
    }
  }
  function refresh() {
    fetch("/api/parallel").then(function (r) { return r.json(); })
      .then(renderStatus).catch(function () {});
  }
  toggle.addEventListener("click", function () {
    fetch("/api/parallel", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify({parallel_enabled: !currentOn})
    }).then(function (r) { return r.json(); })
      .then(function (d) { if (d.ok) renderStatus(d); }).catch(function () {});
  });

  // 挂载：优先挂进已有的 Hive 面板（避免与右侧栏/底部栏重叠）；
  // 若 Hive 面板不存在，则作为独立悬浮面板出现。
  var hivePanel = document.getElementById("zhuli-hive-panel");
  if (hivePanel) {
    hivePanel.appendChild(section);
  } else {
    var panel = el("div", "", null);
    panel.id = "zhuli-parallel-panel";
    panel.appendChild(section);
    document.body.appendChild(panel);
  }
  window.addEventListener("zhuli-session-switch", function () {
    groupsEl.textContent = "当前分组：—（切换会话后清空）";
  });
  refresh();
})();
