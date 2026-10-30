"""配置 Pydantic 模型定义。

敏感项（API Key）只存「引用」：要么环境变量名（api_key_env），要么
keyring 服务标识（api_key_service）。绝不在此写入明文。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    name: str
    base_url: str
    api_key_env: str | None = None
    api_key_service: str | None = None  # keyring: "service:account"
    default_model: str = ""             # 默认模型 id（如 deepseek-chat）
    models: dict[str, str] = Field(default_factory=dict)  # 能力 -> 模型 id
    embedding_model: str = ""           # 该 provider 的 embedding 模型（留空则用 default_model）


class RoutingConfig(BaseModel):
    # 将能力路由到具体 provider 名称（provider 内部再按能力选模型）
    vision: str
    reasoning: str
    default: str
    embeddings: str | None = None       # 提供 embedding 的 provider 名称（用于技能语义检索；留空则回退关键词）


class AgentConfig(BaseModel):
    """单个智能体的模型绑定：可指定 provider 与 capability，实现多模型分布式协作。"""

    provider: str | None = None            # 留空则按 capability 走 routing
    capability: Literal["vision", "reasoning", "default"] = "reasoning"


class PolicyConfig(BaseModel):
    max_steps: int = 40
    step_timeout_sec: int = 120
    confirm_dangerous: bool = True
    auto_execute_safe: bool = True
    # ---- 多智能体 / 蜂巢 ----
    multi_agent: bool = True           # 多智能体协作总开关（false = 单脑模式）
    self_critique: bool = True         # 执行前自我批评
    observer_enabled: bool = True      # 观察蒸馏
    skill_promote_threshold: int = 2   # 技能升格为专项智能体的成功次数阈值
    hive_mode: bool = False            # 蜂巢思维：多执行体并行提案 + 共识择优
    hive_size: int = 3                 # 蜂群规模（执行体数量，1~4）
    multi_agent: bool = True               # 多智能体协作总开关（关闭则回退单脑模式）
    self_critique: bool = True             # 执行前自我批评（Critic 智能体）
    observer_enabled: bool = True          # 观察蒸馏（Observer 智能体）
    skill_promote_threshold: int = 2       # 技能成功复用达到此次数即升格为专项智能体


class ViewportConfig(BaseModel):
    width: int = 1280
    height: int = 800


class BrowserConfig(BaseModel):
    headless: bool = False
    user_data_dir: str = "./.zhuli_browser_profile"
    viewport: ViewportConfig = Field(default_factory=ViewportConfig)


class ComputerConfig(BaseModel):
    max_output_chars: int = 20000
    timeout_sec: int = 60
    allowed_dirs: list[str] = Field(default_factory=list)


class IntegrationConfig(BaseModel):
    type: Literal["browser", "computer"]
    url: str | None = None
    command: list[str] | None = None


class SecurityConfig(BaseModel):
    """军事级加密相关配置。"""
    master_key_env: str = "ZHULI_MASTER_KEY"   # 主口令环境变量名（推荐）
    pbkdf2_iterations: int = 600_000           # PBKDF2-HMAC-SHA256 迭代次数
    encrypt_credentials: bool = True           # 凭据落库前是否做 AES-256-GCM 信封加密


class Settings(BaseModel):
    providers: list[ProviderConfig] = Field(default_factory=list)
    routing: RoutingConfig
    agents: dict[str, AgentConfig] = Field(default_factory=dict)  # 智能体名 -> 模型绑定
    policy: PolicyConfig = Field(default_factory=PolicyConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    computer: ComputerConfig = Field(default_factory=ComputerConfig)
    integrations: dict[str, IntegrationConfig] = Field(default_factory=dict)
    security: SecurityConfig = Field(default_factory=SecurityConfig)

    def provider(self, name: str) -> ProviderConfig | None:
        for p in self.providers:
            if p.name == name:
                return p
        return None

    def provider_for(self, capability: Literal["vision", "reasoning", "default"]) -> ProviderConfig | None:
        name = getattr(self.routing, capability)
        return self.provider(name)
