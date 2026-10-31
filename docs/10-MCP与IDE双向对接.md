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

- 按钮：控制台的 Hive 面板（v0.2.0 时在左下角，v0.3.0 起默认改到
  底部居中，因为左下角会盖住任务输入区），标签为 “Hive mode”，副标题说明
  “并行提案 + 加权共识投票”，不做超出机制本身的保证。
- 机制（与代码一致）：多个执行体以不同 temperature 并行提案，批评与
  风险加权打分，得分最高者胜出；被判 abort 或 danger 的胜出者会被否决；
  全部失效时降级为单脑决策。
- 接口：`GET /api/hive` 查看当前模式与蜂群规模；`POST /api/hive`
 （`hive_mode` bool，`hive_size` >= 1 整数、无上限，`hive_size_mode` manual/auto）运行时切换，与 `/api/models`
  覆盖同款：不写回配置文件，重启后恢复为配置值（默认关）。
- 面板显示：当前模式（hive / multi / single）、蜂群规模输入（>= 1，常用 1、3、5、8）与规模模式（手动/自动）、
  最近一次共识（来自已有 hive 共识事件与蜂巢 think 事件）与 token 消耗
  警告（约为普通流水线的 3 倍，默认关闭）。
- 实现方式：静态覆盖层（`console/static/hive.js` + `hive.css`），未重建
  React 前端；开关通过重建协调器生效（`Orchestrator.rebuild_coordinator`），
  不影响正在运行的任务，新协调器只用于后续任务。
- 已验证（本地服务，无真实 LLM）：初始 multi → POST 开启（规模 2）→
  `/api/agents` 报告 hive → 非法规模 9 被拒绝且状态不变 → POST 关闭 →
  `/api/agents` 回到 multi；配置文件内容未变。真实 LLM 下的蜂巢投票
  仍未验证（需要模型 Key 与真实任务）。

## 双向开关与派发到 IDE 按钮（v0.3.0，代替普通派发按钮）

原来设想的“派发到 IDE”普通按钮被改成一个三段开关，因为两个
方向同时开会形成 IDE ↔ Zhuli 来回循环：IDE 把任务派给 Zhuli，
Zhuli 又把任务派回 IDE，如此往复。开关是一个分段控件、一个值，
三选一，从构造上就不可能同时开启两方向：

| 位置 | 含义 | 控制台派发按钮与目标工具 IDE 选项 | MCP 派发（IDE → Zhuli） |
| --- | --- | --- | --- |
| 左：IDE → Zhuli | 外部 IDE 经 MCP 操作 Zhuli | 禁用，Zhuli 不可反向派发 | 允许（仍需两步批准） |
| 中：关闭（默认） | 仅本助理 | 禁用 | 阻止，返回“开关关闭”错误 |
| 右：Zhuli → IDE | Zhuli 派发到外部 IDE | 启用 | 阻止，返回“防循环”错误 |

- 位置：指令台（ChatPanel）里，目标工具选择器下方；原来的目标
  工具选择器保留不删，里面的 IDE 选项在开关不在右位置时禁用，
  切离右位置时已选的 IDE 目标会被界面先行清掉。
- 派发按钮：在开关切到右时才可用，旁边有 IDE 选择器
  （codebuddy / trae / opencode）。没有任务目标时禁用，提示
  “先输入任务目标”；任务执行中禁用，提示“任务执行中，结束后
  可派发”，绝不会悄悄杀掉或重复一个正在跑的任务。点派发后还
  要再确认一次（待确认条里点“确认派发”）才提交。
- 后端路径：按钮走 `POST /api/dispatch`（goal + tool），而不是
  直接发 WebSocket 任务，原因是按钮要在提交前就给出诚实结果：
  开关位置、任务在跑、目标为空、未知 IDE、IDE 未配置、浏览器
  类 IDE 无页面、缺 OpenCode 二进制，全部在提交前返回明确错误，
  不伪造成功。检查通过且二次确认后，提交走的仍是普通任务路径
  `Orchestrator.submit(goal, target_tool)`，所以执行中遇到需要
  确认的步骤时，仍会走原有的右侧确认流程；普通任务消息也绕不
  过开关——控制台 WebSocket 任务入口与 `Orchestrator.submit`
  里各有一道同样的检查。
- 共享状态：开关值是控制台与 MCP 共用的单个运行时值，存在项目
  内 `.zhuli_runtime/bidirectional.json`（不入库、不含任何密钥，
  只有模式字符串）。控制台开关写入内存与该文件；MCP 派发每次
  调用都重读该文件，所以控制台切开关后 MCP 立刻生效，无需重启
  MCP。控制台启动时把该值复位为配置值
  （`policy.bidirectional_mode`，默认 off），停服时尽力删掉该
  文件，因此重启后回到配置值；独立 MCP 在没有控制台会话时读
  不到文件，默认回 off（fail-closed，两方向都关），绝不默认放行。
  浏览器 localStorage（`zhuli-bidirectional-mode`）只记界面显示
  位置，服务端值加载后会覆盖它。
- 接口：`GET /api/bidirectional` 查看当前与配置位置；
  `POST /api/bidirectional`（`mode` 为 off / ide_to_zhuli /
  zhuli_to_ide 之一）运行时切换，不写回配置文件；非法值返回错误
  且不做任何改动；切换只影响后续派发，正在运行的任务不受影响。
- 批准流程不变：派发按钮的二次确认与 MCP 的两步批准
  （`needs_approval` + `request_id` + `zhuli_approve`）都不绕过
  护栏，deny 永远不可被批准覆盖；MCP 派发在开关关闭或方向不对
  时直接返回模式错误，而不是先给一个“待批准”（批准不能把被
  开关关掉的方向重新打开）。
- 诚实边界：本版验证的是开关逻辑、检查与报错（见发布说明），
  真实 CodeBuddy/Trae 网页派发与真实 OpenCode CLI 仍未验证，
  原因与 v0.2.0 相同：需要真实登录与真实 CLI。
