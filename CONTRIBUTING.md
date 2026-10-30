# 参与贡献 ZHULI

感谢你有兴趣参与开发！这份文档告诉你如何快速上手、提交什么、以及哪些红线不能碰。

## 快速上手

```bash
git clone https://github.com/zzaigc/zhuli.git
cd zhuli
# Windows 一键安装（Python 依赖 + 项目内 Chromium）
install.bat
# 准备配置
copy config\settings.yaml.example config\settings.yaml
# 填入你自己的模型 API（环境变量方式，如 set DEEPSEEK_API_KEY=...）
run.bat
```

动手写代码前，请按顺序阅读：

1. [`docs/README.md`](docs/README.md) —— 文档索引与 5 分钟上手
2. [`docs/01-产品与架构总览.md`](docs/01-产品与架构总览.md) —— 整体架构
3. [`docs/08-二次开发指引.md`](docs/08-二次开发指引.md) —— 如何加模块/连接器/智能体
4. [`docs/05-事件契约.md`](docs/05-事件契约.md) —— 前后端事件契约（改事件必读）

## 提交流程

1. 从 `main` 拉特性分支：`feat/xxx`（新功能）、`fix/xxx`（修复）、`docs/xxx`（文档）；
2. 保持每个 PR 聚焦一件事，附带「动机 + 改动点 + 验证方式」；
3. 提交信息用英文或中文均可，建议格式：`type(scope): 摘要`，例如 `feat(integrations): 新增 Windsurf 连接器`；
4. 前端改动请一并提交 `src/zhuli/console/static/` 的重建产物（`cd frontend && npm run build`），保证 clone 即用；
5. 每个保持可运行的合入都会随下一个版本 tag 发布。

## 架构红线（合并前自查）

这些是项目的安全与架构底线，PR 触碰任意一条会被要求修改：

- **命令执行必须用 subprocess 参数列表**，禁止 shell 字符串拼接；
- **危险命令必经护栏**（`computer/guard.py` 分级），不得绕过或默认放行；
- **凭据明文绝不进入**：LLM 上下文、日志、配置文件、git 历史；日志敏感值一律脱敏为 `***`；
- **连接器只依赖 browser/computer 公开接口**，不得直接调用其内部实现；
- **加密相关改动**（`security/`、`credential/`）请在 PR 中写明威胁模型与自测用例；
- 浏览器一律使用独立 `user_data_dir`（项目内 `.zhuli_runtime/profile/`），禁止指向用户日常 profile；
- 新增 WebSocket 事件需同步 `core/events.py`（后端）与 `frontend/src/ws.ts`（前端）。

## 报告 Issue

请附上：复现步骤、日志片段（**先脱敏**）、预期 vs 实际行为、运行环境（OS / Python 版本）。
涉及安全漏洞请勿公开 issue，优先联系仓库维护者私下披露。

## 行为准则

保持友善、就事论事。这里的项目初心是「把 AI 助理的控制权还给用户」——欢迎所有认同这个方向的人。
