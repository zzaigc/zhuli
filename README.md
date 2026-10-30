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
install.bat      :: 安装 Python 依赖 + 把 Chromium 下载到项目目录（仅首次）
run.bat          :: 启动本地服务（默认 http://127.0.0.1:8000）
```

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

> 控制台由 `frontend/`（React + TypeScript + Vite）构建，**构建产物已随仓库提交在 `src/zhuli/console/static/`**——clone 后无需安装 Node 环境即可直接使用完整控制台。想改前端再进入 `frontend/` 执行 `npm install && npm run build`。

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
