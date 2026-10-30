"""加密保险库：OS keyring（外层）+ AES-256-GCM 信封（内层）的双层防护。

为什么还要在 keyring 之上再加密一层：
- keyring 的部分后端（如某些文件型后端）本质是明文/弱保护存储；
- 凭据若被同步/备份/迁移到别处，信封层仍然保护它；
- 密文与账户名通过 AAD 绑定，杜绝「把 A 账户的密文搬到 B 账户」的替换攻击。

主口令（master passphrase）来源优先级：
1. 环境变量 `ZHULI_MASTER_KEY`（推荐：口令不落 OS 凭据库，安全性最高）；
2. keyring 中随机生成并保存的口令（开箱即用）；
3. 以上都不可用时 → 仅内存随机会话密钥（进程退出后密文不可解，安全默认）。
"""
from __future__ import annotations

import base64
import logging
import os
import secrets

import keyring
from keyring.errors import KeyringError

from .crypto import (
    _ITERATIONS, CryptoUnavailable, available, derive_key, fingerprint,
    new_salt, seal, unseal,
)

log = logging.getLogger(__name__)

SERVICE = "zhuli"
_MASTER_ACCOUNT = "master"
_SALT_ACCOUNT = "master.salt"


class SecurityVault:
    def __init__(self, service: str = SERVICE) -> None:
        self.service = service
        self._key: bytes | None = None
        self._salt: bytes | None = None
        self._ephemeral = False
        self._env_name = "ZHULI_MASTER_KEY"
        self._iterations = _ITERATIONS
        self._encrypt = True
        self._refresh_key()

    def configure(self, *, env_name: str | None = None, iterations: int | None = None,
                   encrypt: bool | None = None) -> None:
        """按项目配置重配安全参数（在配置就绪后调用）。"""
        if env_name:
            self._env_name = env_name
        if iterations and iterations > 0:
            self._iterations = iterations
        if encrypt is not None:
            self._encrypt = encrypt
        self._refresh_key()

    # ---------- 主密钥 ----------
    def _keyring(self, account: str) -> str | None:
        try:
            return keyring.get_password(self.service, account)
        except KeyringError:
            return None

    def _keyring_set(self, account: str, value: str) -> bool:
        try:
            keyring.set_password(self.service, account, value)
            return True
        except KeyringError:
            return False

    def _refresh_key(self) -> None:
        passphrase = os.environ.get(self._env_name)
        if passphrase:
            salt = self._load_salt()
            self._salt = salt
            self._key = derive_key(passphrase, salt, self._iterations)
            log.info("主密钥已就绪（来源：环境变量 %s，指纹=%s）", self._env_name,
                     fingerprint(self._key))
            return

        stored = self._keyring(_MASTER_ACCOUNT)
        if stored:
            salt = self._load_salt()
            self._salt = salt
            self._key = derive_key(stored, salt, self._iterations)
            log.info("主密钥已就绪（来源：系统凭据库，指纹=%s）", fingerprint(self._key))
            return

        # 开箱即用：生成随机主口令并保存（若 keyring 不可用则退化为仅内存会话密钥）
        passphrase = secrets.token_urlsafe(48)
        salt = new_salt()
        if self._keyring_set(_MASTER_ACCOUNT, passphrase):
            self._keyring_set(_SALT_ACCOUNT, base64.b64encode(salt).decode("ascii"))
            self._salt = salt
            self._key = derive_key(passphrase, salt, self._iterations)
            log.info("已生成并保存新的主密钥（指纹=%s）", fingerprint(self._key))
            return

        self._ephemeral = True
        self._salt = salt
        self._key = derive_key(secrets.token_urlsafe(48), salt, self._iterations)
        log.warning("keyring 不可用，主密钥为仅内存会话密钥（重启后已存密文不可解密）")

    def _load_salt(self) -> bytes:
        raw = self._keyring(_SALT_ACCOUNT)
        if raw:
            try:
                return base64.b64decode(raw)
            except Exception:
                pass
        salt = new_salt()
        self._keyring_set(_SALT_ACCOUNT, base64.b64encode(salt).decode("ascii"))
        return salt

    # ---------- 对外 API ----------
    def save(self, account: str, secret: str) -> bool:
        """保存凭据（先 AES-256-GCM 加密，再存入 keyring）。"""
        if not self._encrypt or self._key is None or not available():
            return self._plaintext_fallback_set(account, secret)
        try:
            envelope = seal(secret, self._key, aad=account.encode("utf-8"))
        except CryptoUnavailable:
            return self._plaintext_fallback_set(account, secret)
        return self._keyring_set(account, envelope)

    def get(self, account: str) -> str | None:
        stored = self._keyring(account)
        if stored is None:
            return None
        if not available() or self._key is None or not stored.startswith("ZH1."):
            return stored  # 兼容历史明文记录
        try:
            return unseal(stored, self._key, aad=account.encode("utf-8"))
        except Exception:
            log.error("凭据解密失败（主密钥不匹配或密文被篡改）：%s", account)
            return None

    def delete(self, account: str) -> None:
        try:
            keyring.delete_password(self.service, account)
        except KeyringError:
            pass

    def _plaintext_fallback_set(self, account: str, secret: str) -> bool:
        log.warning("未启用信封加密（缺少 cryptography），凭据仅依赖系统凭据库保护：%s", account)
        return self._keyring_set(account, secret)

    # ---------- 运维信息 ----------
    @property
    def info(self) -> dict:
        return {
            "crypto_available": available(),
            "encryption_enabled": self._encrypt,
            "cipher": "AES-256-GCM",
            "kdf": f"PBKDF2-HMAC-SHA256 x{self._iterations}",
            "key_fingerprint": fingerprint(self._key) if self._key else None,
            "ephemeral_key": self._ephemeral,
            "master_source": ("env" if os.environ.get(self._env_name)
                              else ("keyring" if not self._ephemeral else "ephemeral")),
        }
