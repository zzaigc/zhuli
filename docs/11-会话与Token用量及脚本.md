# 11 · 会话、Token 用量与脚本（v0.3.0）

本文档说明 v0.3.0 新增的三组功能：会话、Token 用量、脚本。
设计原则和 v0.2.0 一致：先说清楚什么是真的、什么是还没验证的，
不把“写了代码”说成“已经跑通”。

## 一、会话

### 用户能做什么

- 左侧“会话”面板有“新会话”按钮和会话列表。
- 点一个会话就切换到它；切换时清空当前对话、计划、日志、思考、
  智能体活动、终端输出、事件轨迹和右侧任务栏状态（右侧栏和 Hive 面板
  会收到浏览器事件并同步清空）。
- 会话标题取自该会话的第一个任务目标（前 20 个字）加时间戳；
  没发过任务的会话标题就是“新会话”。
- 任务执行中不能新建或切换会话，避免把两个任务的状态混在一起。

### 会话存在哪里

- 只存在本机浏览器 localStorage 里：
  会话列表是 `zhuli-sessions`，当前会话是 `zhuli-session-current`。
- 刷新页面后会话列表仍在；换一台设备、换一个浏览器、清浏览器数据后，
  会话列表就会丢失。这是 v0.3.0 的明确限制，不是服务端持久化。
- 后端不拥有会话历史。后端只在任务消息里可选地接受一个
  `session_id` 字段（老客户端不带这个字段也能正常工作），
  用它给 Token 用量记录归属，不用它恢复对话。

### 相关代码

- 前端：`frontend/src/components/SessionPanel.tsx`（列表与按钮）、
  `frontend/src/App.tsx`（会话状态、新建、切换、清空、标题生成、
  任务消息里带 `session_id`）。
- 后端：`src/zhuli/core/orchestrator.py` 的 `submit()` 接受可选的
  `session_id`，`src/zhuli/console/server.py` 的 WebSocket 分发把它传过去。
- 覆盖层同步：`src/zhuli/console/static/sidebar.js` 和 `hive.js`
  监听浏览器事件 `zhuli-session-switch` 并清空各自的显示状态。

## 二、Token 用量

### 用户能看到什么

- 控制台顶部“Token 用量”按钮打开用量页，显示：
  总 token、输入、输出、缓存、调用次数、已知用量次数、未知用量次数；
  按模型统计、按天统计、最近记录、蜂巢与非蜂巢分拆。
- 蜂巢模式的消耗会单独标出来，并提示蜂巢模式 token 消耗约为普通
  流水线的 3 倍，默认关闭。

### 用量是怎么记的

- 模型层在每次真实调用后读取供应商返回的 `usage`：
  输入 token、输出 token、总 token，缓存 token 如果有的话也记。
  聊天调用和向量化调用分开记（kind 分别是 chat 和 embedding）。
- 每条记录还记供应商名、模型名、能力（vision / reasoning / default /
  embedding）、时间戳、会话编号（如果有）、是不是蜂巢模式。
- 如果供应商没有返回用量，这条记录记为“用量未知”，不记为零；
  总数只加已知用量的调用，未知调用只单独计数。
- 测试、占位和模拟调用不计入总数。代码里调用记录时传
  `source="test"` 的记录会被汇总函数排除，文档里也要这样写。

### 费用怎么算

- 默认不显示费用，只显示 token 数。
- 只有运营者在项目内 `.zhuli_runtime/prices.json` 里自己放了单价
  （模型名对应每 100 万 token 的价格）时，用量页才按这个单价算出
  一个费用。项目里不自带任何单价，不编造价格。

### 用量存在哪里

- 项目内 `.zhuli_runtime/usage.db`（SQLite，已被 .gitignore 排除，
  不进源码仓库）。
- 里面不存任何密钥、提示词正文、对话内容，只存供应商、模型、
  能力、时间、会话编号、蜂巢标志和 token 数。
- 相关代码：`src/zhuli/llm/usage.py`（记录与汇总）、
  `src/zhuli/llm/provider.py`（调用后读取用量并记录）、
  `src/zhuli/console/server.py` 的 `GET /api/usage`、
  `frontend/src/components/TokenPanel.tsx`（用量页）。

### 用量页不显示什么

- 不显示任何供应商的账单余额、不显示按用户或按账号的费用、
  不显示没有返回用量的调用的 token 数（只显示“未知”）。
- 用量页的会话编号只是归属标记，不是会话历史；想看对话历史请用
  左侧会话面板，刷新后主对话区也不会自动恢复旧会话的全部对话。

## 三、脚本

### 自检

- `zhuli.main --check` 本来就存在，v0.3.0 把它接进了安装脚本：
  安装结束时自动做一次自检，打印版本、项目根、运行时目录、
  浏览器目录和配置文件是否存在，不启动服务、不调用模型。
- 也可以单独运行自检：Linux/macOS 用 `scripts/doctor.sh`，
  Windows 用 `scripts/doctor.bat`。自检只检查，不安装、不改数据。

### 启动

- Linux/macOS 用 `scripts/start.sh`，Windows 用 `run.bat`。
- 虚拟环境不存在时，启动脚本先自动运行安装脚本，再启动服务；
  以前是虚拟环境不存在就直接用系统 Python 跑，容易缺依赖。

### 就地升级

- Linux/macOS 用 `scripts/upgrade.sh <新版本解压目录>`，
  Windows 用 `scripts/upgrade.bat <新版本解压目录>`。
- 只覆盖代码、脚本、文档和版本文件：`src/`、`docs/`、
  `frontend/src`、前端配置文件、README、许可证、版本文件、
  安装与启动脚本、发布说明。
- 绝不改动：`.zhuli_runtime/`（虚拟环境、浏览器、profile、
  记忆库、用量库）、`config/settings.yaml`、`.git`、
  `frontend/node_modules`。
- 来源里没有的旧文件不会被删除；升级脚本本身不会自动覆盖
  正在运行的那个文件，如有新版会提示手动复制。
- 升级后如果虚拟环境存在，会再跑一次 `--check`；如果不存在，
  会提示先运行安装脚本。升级不自动安装依赖、不删除虚拟环境。

### 复用 Chromium

- Linux/macOS 用 `scripts/reuse_chromium.sh`，
  Windows 用 `scripts/reuse_chromium.bat`。
- 先看项目内 `.zhuli_runtime/browsers` 里是不是已经有 Chromium，
  有就直接跳过下载；没有就依次看命令行参数、环境变量、
  同级目录和常见系统缓存里有没有 `chromium-*` 目录，有就复制进来。
- 找到时返回 0，安装脚本就跳过下载；没找到时返回 2，
  安装脚本就正常下载。复用只复制浏览器二进制目录，
  不改 profile、记忆库、配置文件和虚拟环境。

### 控制台构建

- 直接 `npm run build` 会清空 `src/zhuli/console/static/`，
  从而删掉 v0.2.0 的覆盖层文件（hacker.css、sidebar.css/js、
  hive.css/js）。v0.3.0 新增了 `scripts/build_console.sh`：
  先构建，再从 `frontend/console-overlays/`（覆盖层源文件）
  恢复这些文件，并给生成的 index.html 重新加上覆盖层引用。
- 以后改前端请用构建脚本，不要直接用 `npm run build`。

## 四、还没有验证的内容

- 浏览器端到端、真实模型决策链、真实蜂巢投票、
  真实 CodeBuddy/Trae 派发、真实 OpenCode 命令行、Release 资产上传：
  这些在 v0.2.0 就没验证，v0.3.0 也没有因为加了会话和用量就自动
  变成已验证。需要真实 Chromium、真实模型 Key、真实登录和真实机器。
- Windows 的 .bat 脚本（doctor、reuse、upgrade、install、run）
  在本机没有 Windows 环境，只能做人工语法检查，没有在真实
  Windows 上跑过；Linux/macOS 的 .sh 脚本做了语法检查和隔离测试。
- 服务整体启动和 `/api/usage` 的在线检查在本机受限：
  系统 Python 缺少 fastapi、openai、pydantic 等依赖，
  且临时目录只有 512 MB，无法在这里完整安装和启动服务；
  用量逻辑用标准库做了隔离测试，语法和导入检查通过，
  在线检查要到真实机器上按发布说明里的步骤做。
