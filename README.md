# ZHULI · 本地模块化 AI 助理

一个运行在你本机的 AI 助理，形态为「本地服务 + 网页控制台」。它能在**独立的 headed Chromium 窗口**里自动操作浏览器、执行本地命令、剪辑视频，并可直接对接 **CodeBuddy / Trae / OpenCode** 等外部 AI 编码工具。所有「看得见 AI 在做什么」的可视化、人在回路确认、安全凭据卡片都内置其中。

> 设计原则：**全程模块化**。每个能力（browser / computer / video / integrations）对 `core.orchestrator` 暴露统一接口，新增能力零侵入。
>
> 📚 **完整文档在 [`docs/`](docs/README.md)**：架构总览 / 目录职责 / 决策链 / 蜂巢思维 / 事件契约 / 配置参考 / 安全加密 / 二次开发 / 路线图，以及 [`docs/prompts/`](docs/prompts/) 全部智能体提示词。接手开发请先读它。

## 为什么做这个项目（初心）

这个项目的起点是一次很不愉快的体验：**我的 Muse 账号被封锁了**。我多次提交申诉，得到的只有机械的模板回复，**人工客服始终不予理会**——一个每天重度依赖的 AI 工具，就这样在没有任何有效沟通渠道的情况下失去了。

这件事让我意识到一个问题：**把重要的工作流寄托在单一云端服务上，等于把控制权交了出去。** 账号说封就封，申诉石沉大海，数据与工作流都被锁在别人的服务器里。

所以我决定做一个**运行在自己电脑上、控制权完全属于自己的 AI 助理**：

- **本地优先**：服务跑在你自己的机器上，浏览器 profile 独立隔离，不依赖任何特定云端产品的账号体系；
- **模型自主**：任何兼容 OpenAI 格式的 API 都能接入（DeepSeek / Kimi / GLM / OpenAI…），还能按能力路由，一家被封随时换另一家；
- **能力开放**：浏览器自动化、本地命令、视频剪辑、对接其他 AI 编码工具——不设围墙；
- **开源共建**：代码完全开源，欢迎所有人参与开发、审查安全设计、提交想法。任何单一公司都不能再轻易切断你的工作流。

如果你的 Muse（或任何 AI 服务）账号也被无理由封锁、申诉无门，欢迎来这里一起把它变得更好。

## 能力一览

| 模块 | 说明 |
|---|---|
| `core` | 决策核心：完整决策链——Planner 分解（含达成标准/工具选择）、可见思维链、Reflection 校验、循环/卡死检测、快照回滚与主动重规划、Orchestrator 主循环、状态机 |
| `llm` | 多 provider 适配 + 能力路由（vision / reasoning / default） |
| `browser` | 隔离 headed Chromium、元素标注高亮、动作执行、敏感操作识别 |
| `computer` | 本地命令执行（subprocess 参数列表，无 shell 拼接）+ 危险命令护栏 |
| `video` | ffmpeg 剪辑方案规划 + 白名单命令执行 |
| `integrations` | 连接器（CodeBuddy / Trae / OpenCode），复用 browser/computer |
| `credential` | keyring 加密存储 + 安全卡片注入（明文不进 LLM） |
| `agents` | 多智能体团队：规划/观察/执行/批评/风险/技能挖掘 + 外部工具智能体 + 协调器，各角色可绑不同模型 |
| `memory` | 长期记忆与自进化技能：SQLite 持久化（技能/任务历史/反思/键值）+ 技能检索沉淀 |
| `security` | 军事级加密：AES-256-GCM（AEAD）+ PBKDF2-HMAC-SHA256 + 内存密文容器 + 双层保险库 |
| `console` | FastAPI + WebSocket 事件推送 + 静态托管 |

## 数据存储位置（重要）

- **Chromium 浏览器二进制**：通过 `PLAYWRIGHT_BROWSERS_PATH` 固定在项目内特定子目录 `.zhuli_runtime/browsers/`，**绝不写入 C 盘**。
- **浏览器用户 profile**：`browser.user_data_dir` 的相对路径会解析到项目内 `.zhuli_runtime/profile/`，与日常浏览器完全隔离，也不占 C 盘。
- 如需清理，直接删除项目内的 `.zhuli_runtime/` 即可，不影响系统。

## 完整决策链（分层决策 + 自我纠错 + 可见思维）

控制核心是「Planner → Orchestrator 主循环 → Reflection → 必要时重规划」的分层闭环：

```
目标 + 历史技能 ──► Planner 分解（子任务 + 达成标准 + 工具选择）
                          │
      ┌───────────────────┴───────────────────┐
      ▼                                       │
  ► 观察（元素 + a11y树 + 当前子任务进度）      │
  ► 决策（LLM 输出 thought 思维链 + 结构化 Action）
  ► 执行（Browser/Computer/Video/Integrations，经护栏·确认·凭据）
  ► 反思（对照「达成标准」校验当前子任务）      │
      │                                       │
      └─► continue / 推进下一子任务 / replan ──┘
                     / done / escalate
```

- **可见思维链**：`think` 事件把「🧭 规划 / 🎯 决策 / 🔎 反思」三阶段的思考实时推送到控制台中部，AI 在想什么一目了然。
- **带验证标准的规划**：Planner 为每个子任务输出 `verification`（达成标准）与 `tools`（所用能力），反思据此判定是否真的完成，而不是凭感觉。
- **子任务进度推进**：反思判定 `current_done` 后自动把当前子任务标记为完成、推进到下一个，计划面板实时勾选进度。
- **确定性循环/卡死检测**：连续 3 步动作指纹完全相同即判定死循环，强制重规划——保留已完成子任务，只替换无效部分。
- **快照回滚 + 重试 + 升级**：单步异常时先回滚到上一步 URL 再重试；仍失败则停止并提示介入；重规划超过 3 次仍无效则升级求助。
- **经验复用**：检索到的历史技能注入决策上下文，相同或相似场景直接沿用成熟步骤（详见下文「长期记忆」）。

## 多智能体分布式决策（多提示词 + 多模型 + 外部工具即智能体）

系统不是「一个大脑」，而是一支**各司其职、可跑在不同模型上**的智能体团队：

| 智能体 | 职责 | 可配 capability |
|---|---|---|
| `planner` 规划 | 把目标拆成带完成标准的子任务 | reasoning |
| `observer` 观察 | 蒸馏页面观察，只留与当前子任务相关的元素 | default |
| `actor` 执行 | 提出下一步动作（含思维链与预期效果） | reasoning |
| `critic` 批评 | **执行前**审查动作、执行后反思校验达成与否 | reasoning |
| `risk` 风险 | 给动作做 safe/confirm/danger 分级（与规则护栏互补） | default |
| `skill_miner` 技能挖掘 | 从成功任务提炼/迭代可复用技能 | reasoning |
| `tool:*` 外部工具 | CodeBuddy / Trae / OpenCode 作为远程智能体，可直接派发任务 | — |
| `skill:*` 专项 | 由学到的技能自动升格而成（用得越多，模块越多） | — |

```
        ┌─ planner 规划（子任务 + 完成标准）
        │
观察 ───┼─ observer 蒸馏 ──► actor 提议动作 ──┬─► critic 审查 ─┐（并发）
        │                                     └─► risk 评级 ──┘
        │                                            │
        │                          revise: 带批评重决策 / abort: 重规划
        │
        └─ critic 反思（当前子任务达成？→ 推进 / 完成 / 重规划 / 升级）
```

- **多提示词**：每个智能体有独立的 system prompt 与 JSON Schema（`src/zhuli/agents/prompts.py`，改动互不干扰）。
- **分布式**：`agents` 配置段可为每个角色指定**不同 provider + capability** —— 例如用 OpenAI 做决策、DeepSeek 做批评，互不影响。
- **并发加速**：批评与风险对同一动作**并行**推理（实测 0.31s vs 串行 0.60s）。
- **自我纠错**：批评判 `revise` 时采纳更优动作或让执行智能体带批评重决策；判 `abort` 则直接重规划。
- **外部工具即智能体**：`tool_task` 统一派发给 CodeBuddy / Trae / OpenCode 工具智能体（内部仍复用 browser/computer 能力）。
- **可观测**：`agent` 事件把「哪个智能体做了什么、结论如何」实时推到控制台中部。
- **可降级**：`policy.multi_agent=false` 时回退为传统单脑模式（沿用 `core/planner.py` 与 `core/reflection.py`）。
- **API Key 驱动**：所有智能体均走配置的 provider（`api_key_env` / `api_key_service`），与连接外部工具互不冲突。

### 🐝 蜂巢思维（分布式群体决策，可选开启）

常规形态是「一个执行体提议 → 评审 → 执行」的流水线；
开启 `policy.hive_mode` 后升级为**蜂巢共识**：

```
观察 → 共享黑板 → actor#1/#2/#3 并行提案（不同 temperature）
     → critic + risk 对每个提案并行投票 → 共识择优 → 执行
```

- **共识规则**：批评（accept +2 / revise +1 / abort −2）+ 风险（safe +2 / confirm 0 / danger −2）加权，总分最高者胜出。
- **天然偏好安全**：即使某动作能达成目标，只要风险高就会在投票中落选。
- **容错**：个别执行体失效不影响整体；全体失效自动降级为单体决策。
- **实测**：3 体各 0.3s 并发耗时 0.31s（串行需 0.90s）；三提案得分 0/1/4 时正确选中得分 4 者。
- 代价是 token 消耗约为流水线的 3 倍，故**默认关闭**，按需开启（详见 [`docs/04`](docs/04-多智能体与蜂巢思维.md)）。

## 长期记忆与自进化 Skills（Muse 式「越用越聪明」）

系统把每次成功任务自动沉淀为可复用「技能」并存进 SQLite（`memory.db`），下次相似任务会检索复用、随使用迭代，无需人工维护：

- **技能沉淀**：任务成功结束后，LLM 把有效步骤压缩成技能（名称 / 触发条件 / 可复用步骤 / 标签），写入 `memory.db` 的 `skills` 表，并通过 `skill` 事件在控制台提示「🧠 学到新技能」。
- **技能复用**：新任务开始时按目标检索相关历史技能，注入 Planner 与决策上下文，AI 可直接沿用成熟经验。
- **自动迭代**：同一目标已有技能时，把本次新经验合并精炼（`🔄 迭代更新技能`），并累计 `usage_count / success_count`，让技能越用越准。
- **技能升格为专项智能体**：技能成功复用达到阈值（`policy.skill_promote_threshold`）后，自动升格并注册为 `skill:*` 专项智能体，成为团队里新增的模块 —— **用得越多，模块越多、越智能**（控制台「🤖 智能体」可看到团队规模增长）。
- **任务记忆**：所有任务目标、成功与否、反思结论均落入 `tasks / reflections` 表，便于后续检索与复盘。
- **语义检索（可选）**：在 `routing.embeddings` 指定支持 embedding 的 provider（如 OpenAI 的 `text-embedding-3-small`），技能会以向量存储，跨表述的相似任务也能用余弦相似度命中；未配置时自动回退关键词检索，零成本可用。
- **技能库面板**：控制台顶部「🧠 技能库」可查看全部已学技能（触发条件 / 使用次数 / 成功率），并直接编辑步骤或删除，人工校正后下次任务立即生效。
- 数据库文件位于项目内 `.zhuli_runtime/memory.db`（不进 C 盘）；学习/检索失败会被静默兜底，不影响主流程。

## 快速开始

项目根目录已提供 Windows 脚本（自动设置上述环境变量）：

```bat
install.bat      :: 安装 Python 依赖 + 把 Chromium 下载到项目目录（仅首次），最后做自检
run.bat          :: 启动本地服务（默认 http://127.0.0.1:8000），虚拟环境不存在时先自动安装
```

Linux/macOS 请用 `scripts/` 下的同名脚本：`scripts/install.sh`、`scripts/start.sh`，
自检用 `scripts/doctor.sh`、就地升级用 `scripts/upgrade.sh <新版本目录>`、
复用已有 Chromium 用 `scripts/reuse_chromium.sh`，控制台构建用 `scripts/build_console.sh`。
就地升级只覆盖代码、脚本、文档和版本文件，绝不改动 `.zhuli_runtime/`、
`config/settings.yaml` 和前端 `node_modules`，详见 v0.3.0 发布说明。

或手动执行（等价）：

```bash
# 1. 安装依赖（首次）
python -m pip install -r requirements.txt
set PLAYWRIGHT_BROWSERS_PATH=%CD%\.zhuli_runtime\browsers
python -m playwright install chromium

# 2. 准备配置（敏感信息只存引用，如环境变量名，绝不写明文）
cp config/settings.yaml.example config/settings.yaml
#   编辑 routing / providers，并设置对应 API Key 环境变量（如 DEEPSEEK_API_KEY）

# 3. 启动
set PLAYWRIGHT_BROWSERS_PATH=%CD%\.zhuli_runtime\browsers
set PYTHONPATH=%CD%\src
python -m zhuli.main
```

打开浏览器访问 `http://127.0.0.1:8000`，左侧下达指令（可选目标工具：本助理 / CodeBuddy / Trae / OpenCode），即可看到 AI 在独立 Chromium 窗口实时操作。

> 控制台由 `frontend/`（React + TypeScript + Vite）构建，**构建产物已随仓库提交在 `src/zhuli/console/static/`**——clone 后无需安装 Node 环境即可直接使用完整控制台。想改前端再进入 `frontend/` 执行 `npm install`，然后用 `scripts/build_console.sh` 构建：直接 `npm run build` 会清空静态目录并删掉覆盖层文件（hacker.css、sidebar.css/js、hive.css/js），构建脚本会在构建后从 `frontend/console-overlays/` 恢复它们并修补 index.html。

## 配置要点

- `providers`：任意兼容 OpenAI 格式的 API（DeepSeek / Kimi / GLM / OpenAI…），敏感 Key 只填 `api_key_env`（环境变量名）或 `api_key_service`（keyring 服务标识）。
- `routing`：按能力把 `vision / reasoning / default` 路由到不同 provider 名称（provider 内部再按能力选模型）。
- 没有 `config/settings.yaml` 时服务启动会提示复制示例配置。

## 安全模型

- **军事级加密**：凭据落库前先做 **AES-256-GCM**（AEAD，256 位密钥 + 96 位随机 nonce + 认证标签）信封加密，密钥由 **PBKDF2-HMAC-SHA256（600,000 次迭代）** 从主口令派生，且用 AAD 绑定账户名防止密文搬运。主口令可来自环境变量 `ZHULI_MASTER_KEY`（推荐）、系统凭据库或仅内存会话密钥。详见 [`docs/07-安全与军事级加密.md`](docs/07-安全与军事级加密.md)。
- **内存密文持有**：凭据在内存中仅以 `SecureString` 密文存在，`repr` 恒为 `***`，注入瞬间才解密、用完即销毁。
- **凭据隔离**：登录/API Key 由安全卡片在前端输入，经 WebSocket 回传内存后注入页面；LLM 只收到「需要凭据」信号，绝不接触明文；日志对值脱敏为 `***`。
- **命令护栏**：命令一律以参数列表方式执行（无 shell 拼接）；`rm -rf /`、格式化、diskpart 等禁止，写系统目录/网络外发等需确认。
- **人在回路**：提交/支付/删除/跨域/危险命令默认弹确认，可随时暂停/接管/停止。

## 迭代指引

新增能力只需在 `src/zhuli/<new>/` 实现与现有模块一致的 `execute / observe` 接口，并在 `core/orchestrator.py` 注册路由即可。详见 `src/zhuli/` 各模块源码与 `core/events.py` 事件契约。

## 参与贡献 🤝

**非常欢迎参与开发！** 这是一个持续演进的项目，无论你是想修 Bug、加新能力（新连接器、新护栏策略、新智能体角色），还是改进文档与控制台体验，都欢迎：

1. Fork 本仓库，从 `main` 拉出特性分支（如 `feat/new-connector`）；
2. 动手前先读 [`docs/README.md`](docs/README.md)（5 分钟上手）与 [`docs/08-二次开发指引.md`](docs/08-二次开发指引.md)；
3. 保持模块化：新能力实现统一 `execute / observe` 接口，新增事件需同步 `core/events.py` 契约与前端 `ws.ts`；
4. 提交 Pull Request，说明动机与验证方式。涉及安全护栏的改动请额外在 PR 中写明威胁模型。

 issue 描述问题请附上：复现步骤、`server` 日志片段（**注意先脱敏，绝不要贴 API Key 或凭据明文**）、预期 vs 实际行为。

## 版本与发布

- 采用**语义化版本**（`v主版本.次版本.修订号`）+ git tag 管理，每个 tag 对应一次可用发布；
- 主干 `main` 始终保持可运行（clone 即用），功能开发走特性分支合并；
- 迭代节奏较快（几乎每天有推送），建议 watch 仓库或定期 `git pull` 获取新版本：
  ```bash
  git fetch --tags
  git checkout v0.1.0   # 切到某个稳定版本
  ```
- 变更要点见各 tag 的 Release 说明；架构层面的大调整会提前在 issue 里开讨论。

## 许可证

本项目以 [MIT License](LICENSE) 开源——你可以自由使用、修改、分发，也请保留原作者版权声明。

## v0.3.0（本地开发中，未推送）

- 新增会话支持：左侧有“新会话”按钮和会话列表，切换会话会清空当前对话、
  计划、日志、思考、终端、事件轨迹和右侧任务栏状态；会话标题取自第一个
  任务目标加时间戳。会话只保存在本机浏览器里，刷新后仍在，换设备或清
  浏览器数据后会丢失；后端只在任务里可选地带一个会话编号，用于用量归属，
  不拥有会话历史。详见 `docs/11-会话与Token用量及脚本.md`。
- 新增 Token 用量页：顶部“Token 用量”按钮打开，显示总量、输入、输出、
  缓存、按模型、按天、最近记录和蜂巢与非蜂巢分拆。模型层会读取供应商
  返回的用量，没有用量时记为未知、不记为零；测试、占位和模拟调用不计入
  总数；没有配置单价时只显示 token 数，不编造成本。用量存在项目内
  `.zhuli_runtime/usage.db`，不进源码、不含任何密钥。
- 新增脚本功能：安装结束时自动做自检（`zhuli.main --check`）；启动脚本在
  虚拟环境不存在时先自动安装；新增就地升级脚本（Windows 与 Linux/macOS），
  只覆盖代码、脚本、文档和版本文件，绝不改动虚拟环境、浏览器、profile、
  记忆库、用量库、配置文件和前端依赖；新增复用 Chromium 脚本，找到已有
  Chromium 时跳过约 197 MB 的重新下载。详见 `docs/11-会话与Token用量及脚本.md`。
- 新增并行子目标：规划器只把独立子任务分进同一组，组按顺序执行，组内
  思考并行、工具执行加锁串行；浏览器步骤、依赖步骤、共享文件或工具目标
  的步骤永远不与他人同组，执行前第二道防线还会把含浏览器步骤的组拆回
  单步；规划失败或并行组失败都回退为顺序执行。开关默认开，可用配置
  `policy.parallel_enabled`、控制台并行开关（`GET/POST /api/parallel`）
  或 `zhuli --no-parallel` 关闭；Hive 模式下强制顺序，不双重并行。
  实时浏览器主循环仍顺序执行（单页面、步间观察依赖），并行执行器用于
  独立非浏览器子任务单元，详见 `docs/12-并行子目标.md`。
- 新增混沌测试（测试专用、默认关闭）：`src/zhuli/chaos/` 做故障注入
  弹性测试，不是压力测试，也不是自动调参。注入 11 种故障（模型
  401/429/超时、页面崩溃/元素缺失/跳转超时、供应商延迟/中断、
  工具变慢/失败、任务中途服务重启），练的是已有恢复机制（重试、
  回滚、重规划、降级、升级）；运行后只给参数范围建议，绝不改写
  配置。开启必须显式（CLI `--chaos-test` 或控制台测试接口确认串），
  快照与报告只在系统临时目录，正常任务不会触发，详见
  `docs/13-混沌测试.md`。
- 蜂巢面板可拖动、可收起：按住 Hive 面板标题拖动可移动，位置限制在
  视口内、不会拖出屏幕，位置记在浏览器里，刷新后恢复；点“收起”会
  变成约 60px 的圆形悬浮按钮（显示 Hive 开/关），圆按钮也可拖动，
  点一下（拖动小于约 5px 才算点击）展开回原来的位置，双击圆按钮或
  点面板里的“复位”回到默认底部居中位置（v0.3.0 双向开关工作时从
  左下角改过来，因为左下角会盖住任务输入区与双向开关）。拖动、收起、展开不调任何接口，
  不改蜂巢模式、规模、投票与 token 提示。
- 蜂群规模不再限于 1~4：手动可输入大于等于 1 的任意整数（常用快捷
  1、3、5、8，点“应用规模”才生效），应用前会显示约规模倍数的 token
  预估，超过 8 有注意、超过 16 有更强警告，但警告不拦截已确认的规模；
  规模大于 4 时温度在约 0.2~1.2 间均匀铺开，不再重复原来的 4 个温度。
  另有自动模式（`policy.hive_size_mode: auto`，默认仍是手动）：按任务
  启发式在 2~8 间选规模（基础 3，多子任务、验证标准多、含风险/确认、
  长任务加分，简单单步减分），选中的规模与原因显示在 Hive 面板里，
  自动结果绝不覆盖手动规模，切回手动即恢复。投票规则不变
  （批评 +2/+1/−2，风险 +2/0/−2，否决与降级不变），大蜂群本身不免费、
  不一定更好，token、延迟与噪声都会随规模增长。
- 双向开关与派发到 IDE 按钮（代替原来设想的普通派发按钮）：指令台
  里新增一个三段开关，左“IDE → Zhuli”、中“关闭”、右“Zhuli → IDE”，
  同一时刻只有一个位置生效，默认关闭。切到右时，指令台里出现
  “派发到 IDE”按钮与 IDE 选择器（codebuddy / trae / opencode），
  原来的目标工具选择器保留，里面的 IDE 选项在开关不在右位置时
  禁用。按钮在没有任务目标时禁用（提示“先输入任务目标”），任务
  执行中禁用（提示“任务执行中，结束后可派发”），点派发后还要再
  确认一次才提交。两方向绝不同时开启，是为了防止 IDE ↔ Zhuli
  来回循环：切到左时 Zhuli 不能反向派发，切到右时来自 IDE 的 MCP
  派发被阻止，关闭时两方向都关。开关是运行时覆盖（控制台与 MCP
  通过 `.zhuli_runtime/bidirectional.json` 共享同一个值，重启恢复
  为配置 `policy.bidirectional_mode`），普通任务消息也绕不过它：
  后端对控制台任务、派发接口和 orchestrator 提交都查同一个值，
  未知 IDE、未配置、浏览器 IDE 无页面、缺 OpenCode 二进制都返回
  明确错误，绝不伪造成功；执行中的确认仍走原有右侧确认流程。
- 本版本仍未验证浏览器端到端、真实模型决策链、真实蜂巢投票、真实并行
  任务端到端、真实 CodeBuddy/Trae 派发、
  真实 OpenCode 命令行和 Release 资产上传，原因与 v0.2.0 相同：需要真实
  Chromium、真实模型 Key 和真实登录；GitHub 令牌不能代替模型 Key。
  完整说明见 `RELEASE_NOTES_v0.3.0.md`。

## v0.2.0（本地开发中，未推送）

- 新增 MCP 服务器：AI IDE 可作 MCP 客户端操作 Zhuli；
  Zhuli 也可派发任务给 CodeBuddy / Trae / OpenCode，派发前有检查与确认。
  详见 `docs/10-MCP与IDE双向对接.md`，用法示例在该文档中。
- 控制台改为 hacker 主题覆盖层：黑底、荧光绿、等宽字体、绿框、
  胶囊导航、终端风标题、实心绿主按钮、描边绿次按钮；未重建 React 前端。
  新增可折叠右侧栏（任务目标、状态、计划、技能、待确认、事件轨迹），
  开关记在 localStorage，详见 docs/10-MCP与IDE双向对接.md。
  新增蜂巢开关：左下角 Hive 面板可运行时开关蜂巢模式、选蜂群规模（1~4），
  不写回配置文件，重启后恢复配置值，默认关闭。
- 启动检查：`python -m zhuli.main --check` 只打印版本、项目内运行时目录
  与配置文件是否存在，不启动服务、不调用模型。
- 本版本仍未验证浏览器端到端与真实 LLM 决策链，原因与 v0.1.0 相同：
  需要真实 Chromium 与真实模型 Key；GitHub 令牌不能代替模型 Key。
