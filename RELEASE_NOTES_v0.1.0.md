# ZHULI v0.1.0 · 首个公开版本

本地模块化 AI 助理首个公开版本。初心：把 AI 助理的控制权还给用户——不依赖任何单一云端账号，跑在你自己的电脑上。

## ✨ 核心能力

- **分层决策链**：Planner（子任务 + 达成标准）→ Orchestrator 主循环（观察→决策→执行→反思）→ 循环/卡死检测 → 快照回滚与重规划 → 升级求助
- **多智能体团队**：规划 / 观察 / 执行 / 批评 / 风险 / 技能挖掘，各角色独立提示词与 JSON Schema，可绑定不同模型供应商
- **🐝 蜂巢思维（可选）**：多提案者并行 + 批评/风险投票 + 加权共识择优（`policy.hive_mode`）
- **🔒 军事级加密**：AES-256-GCM 信封加密 + PBKDF2-HMAC-SHA256（600,000 次迭代）+ AAD 防搬运 + SecureString 内存密文 + keyring 双层保险库
- **四大能力模块**：隔离 headed Chromium 浏览器自动化 / 本地命令执行（参数列表 + 危险命令护栏）/ ffmpeg 视频剪辑 / CodeBuddy·Trae·OpenCode 连接器
- **自进化记忆**：SQLite 技能沉淀、语义检索复用、技能自动升格为专项智能体（用得越多，模块越多）
- **完整 Web 控制台**：对话 / 计划 / 操作视图（截图流 + 高亮）/ 终端回流 / 思维链 / 日志（敏感值 `***` 脱敏）/ 确认弹窗 / 安全凭据卡片——**构建产物随仓库附带，clone 即用，无需 Node 环境**

## 🚀 快速开始

```bat
git clone https://github.com/zzaigc/zhuli.git
cd zhuli
install.bat
copy config\settings.yaml.example config\settings.yaml
run.bat
```

详见 [README](https://github.com/zzaigc/zhuli#readme) 与 [docs/](https://github.com/zzaigc/zhuli/blob/main/docs/README.md) 全套中文开发文档。

## 🤝 欢迎参与

非常欢迎提 Issue / PR 共建！贡献指南见 [CONTRIBUTING.md](https://github.com/zzaigc/zhuli/blob/main/CONTRIBUTING.md)。
