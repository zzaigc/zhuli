# 10 · MCP 与 IDE 双向对接（v0.2.0 新增）

本版本新增两个方向，互不替代：

## 方向一：AI IDE 操作 Zhuli（MCP 服务器）

Zhuli 提供一个仅用标准库的 MCP 服务器，JSON-RPC over stdio：

```
PYTHONPATH=src python -m zhuli.mcp.server
# 或安装后：zhuli-mcp
```

IDE（OpenCode / Trae / CodeBuddy）作为 MCP 客户端连接它，示例配置
（以 OpenCode 为例，Trae / CodeBuddy 按各自 MCP 客户端格式填入同一命令）：

```json
{
  "mcpServers": {
    "zhuli": {
      "command": "python",
      "args": ["-m", "zhuli.mcp.server"],
      "env": {"PYTHONPATH": "src"}
    }
  }
}
```

工具清单（见 `src/zhuli/mcp/server.py`）：

- `zhuli_status` / `zhuli_config`：状态与供应商名，不返回任何密钥。
- `zhuli_skills`：SQLite 技能库。
- `zhuli_shell`：走 `computer.guard` 分级；deny 永远不可被批准覆盖，
  confirm 需两步批准（先返回 `needs_approval` + `request_id`，再调
  `zhuli_approve`，再以 `approved: true` 重调）。
- `zhuli_workflow_run`：按顺序执行一组受护栏的 shell 步骤，任一步失败即停。
- `zhuli_tool_dispatch`：派发给外部 IDE，见方向二。
- `zhuli_run_task`：尽力复用控制台 Orchestrator，需要真实配置与模型 Key；
  在 stdio 下无法回答确认/凭据卡片，到达此类提示时按超时报告，不越过它执行。

## 方向二：Zhuli 操作 AI IDE（派发器）

入口在 orchestrator 的 `tool_task` 动作与 `Coordinator.delegate`，
派发前由 `src/zhuli/integrations/dispatch.py` 做显式检查：

- 未知工具、空任务、浏览器工具缺页面、opencode 缺二进制 → 直接返回
  清晰错误，不进入决策循环。
- 派发给外部 IDE 时，`confirm_dangerous` 开启且未被风险智能体预确认
  时，orchestrator 会先弹确认（IDE 可能读写文件）。

各工具的 v0.2.0 验证状态（诚实标注）：

- OpenCode（命令类）：已用本地 stub 二进制验证——参数列表执行、
  输出与退出码都会返回给 orchestrator。真实 OpenCode CLI 未安装，
  故真实 CLI 路径未验证。
- CodeBuddy / Trae（浏览器类）：连接器逻辑已用 stub 页面验证
  （打开页面、填入任务、发送、读回页面文本），但真实网站未验证：
  页面可能需要登录，选择器是 best-effort，站点改版会失效。

## 安全边界（本版本不变）

- 命令护栏、危险命令 deny、凭据明文不进 LLM、内存 SecureString、
  项目内 `.zhuli_runtime/` 运行时目录，均保持 v0.1.0 的做法。
- MCP 的 shell 与派发工具都不绕过护栏；批准不能覆盖 deny。

## 控制台右侧栏（v0.2.0，静态覆盖层）

- 文件：`console/static/sidebar.js`、`sidebar.css`，在 `index.html` 中
  引用；未重建 React 前端，控制台 API 与事件不变。
- 布局：右侧栏打开时主控制台右移 320px，形成三栏（React 左栏、
  中栏 + 右侧栏）；折叠后主控制台变宽，右侧边缘保留展开按钮；
  开关记在 localStorage（`zhuli-sidebar`）。
- 内容只来自已有 WebSocket 事件：任务目标（取自“收到任务：”对话）、
  总体状态、计划、技能事件、确认/凭据请求、最近事件轨迹；无数据时
  显示空状态，不编造。右侧栏本身不发送确认/凭据，确认仍在主控制台完成。
- 局限：这不是 React 网格重构，窄屏（<900px）时右侧栏改为覆盖；
  侧栏用独立 WebSocket 连接接收事件（含启动期回放），与主控制台
  的连接互不干扰。

## 蜂巢开关（v0.2.0，运行时覆盖）

- 按钮：控制台左下角的 Hive 面板，标签为 “Hive mode”，副标题说明
  “并行提案 + 加权共识投票”，不做超出机制本身的保证。
- 机制（与代码一致）：多个执行体以不同 temperature 并行提案，批评与
  风险加权打分，得分最高者胜出；被判 abort 或 danger 的胜出者会被否决；
  全部失效时降级为单脑决策。
- 接口：`GET /api/hive` 查看当前模式与蜂群规模；`POST /api/hive`
 （`hive_mode` bool，`hive_size` 1~4 整数）运行时切换，与 `/api/models`
  覆盖同款：不写回配置文件，重启后恢复为配置值（默认关）。
- 面板显示：当前模式（hive / multi / single）、蜂群规模选择器（1~4）、
  最近一次共识（来自已有 hive 共识事件与蜂巢 think 事件）与 token 消耗
  警告（约为普通流水线的 3 倍，默认关闭）。
- 实现方式：静态覆盖层（`console/static/hive.js` + `hive.css`），未重建
  React 前端；开关通过重建协调器生效（`Orchestrator.rebuild_coordinator`），
  不影响正在运行的任务，新协调器只用于后续任务。
- 已验证（本地服务，无真实 LLM）：初始 multi → POST 开启（规模 2）→
  `/api/agents` 报告 hive → 非法规模 9 被拒绝且状态不变 → POST 关闭 →
  `/api/agents` 回到 multi；配置文件内容未变。真实 LLM 下的蜂巢投票
  仍未验证（需要模型 Key 与真实任务）。
