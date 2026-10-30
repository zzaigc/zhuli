"""凭据保险库：对外 API 保持不变，底层为「OS keyring + AES-256-GCM 信封」双层防护。

- 明文绝不写入配置文件或日志；
- 单次任务填卡的值默认只存内存（进程退出即清除），仅用户明确要求持久化时才落库；
- 落库时先做 AES-256-GCM 信封加密（AAD 绑定账户名），再交给 OS 凭据管理器。
"""
from __future__ import annotations

from ..security.vault import SecurityVault

SERVICE = "zhuli"
_vault = SecurityVault(SERVICE)


def save(account: str, secret: str) -> bool:
    """持久化保存凭据（加密）。返回是否成功。"""
    return _vault.save(account, secret)


def get(account: str) -> str | None:
    """读取凭据（自动解密）。"""
    return _vault.get(account)


def delete(account: str) -> None:
    _vault.delete(account)


def security_info() -> dict:
    """返回当前加密状态（供控制台/运维核对，不含任何秘密）。"""
    return _vault.info


def configure_security() -> None:
    """按项目配置重配安全参数（配置缺失时保持默认值，绝不因缺配置而崩）。"""
    try:
        from ..config.settings import get_settings

        sec = get_settings().security
    except Exception:
        return
    _vault.configure(
        env_name=sec.master_key_env,
        iterations=sec.pbkdf2_iterations,
        encrypt=sec.encrypt_credentials,
    )
