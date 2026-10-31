"""ZHULI - 本地模块化 AI 助理。

能力模块（对 orchestrator 暴露统一接口）：
  - browser   : 隔离 headed Chromium 浏览器操作
  - computer  : 本地命令执行（subprocess 参数列表，危险命令护栏）
  - video     : ffmpeg 视频剪辑
  - integrations: 外部工具连接器（CodeBuddy / Trae / OpenCode），复用 browser/computer

决策核心：
  - core.planner    : 任务分解 + 子任务清单 + 重规划
  - core.reflection : 每步后反思校验（达成/卡死/循环/超时）
  - core.orchestrator: 观察→决策→执行→反思 主循环
"""

__version__ = "0.3.0"
