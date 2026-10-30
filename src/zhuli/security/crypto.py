"""军事级加密原语：AES-256-GCM（AEAD）+ PBKDF2-HMAC-SHA256。

安全设计（对齐现代密码工程实践）：
- **密钥派生**：PBKDF2-HMAC-SHA256，600,000 次迭代（OWASP 2023 建议量级），32 字节随机盐，派生 256 位密钥。
- **数据加密**：AES-256-GCM（AEAD）—— 256 位密钥、96 位随机 nonce、128 位认证标签；
  同时提供机密性、完整性、抗篡改（密文被篡改会直接解密失败）。
- **每条记录独立随机 nonce**，杜绝 nonce 复用导致的结构性风险。
- **AAD（附加认证数据）**：可把账户名等上下文绑定进密文，防止密文在不同账户间搬运替换。
- **常数时间比较**：涉及秘密比较时一律使用 HMAC 的常数时间比较，抵御时序侧信道。
- **尽力而为的内存擦除**：`wipe()` 用于清零承载密钥/明文的 bytearray。

无 `cryptography` 依赖时本模块自动降级（抛出 CryptoUnavailable），
调用方（vault / SecureString）会回退到「仅依赖 OS keyring」的既有保护，不会崩溃。
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from typing import Union

try:  # 真加密依赖；缺失时优雅降级
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception:  # pragma: no cover
    AESGCM = None  # type: ignore[assignment]

_MAGIC = "ZH1"
_SALT_LEN = 32
_NONCE_LEN = 12
_KEY_LEN = 32
_ITERATIONS = 600_000
_TAG_LEN = 16  # GCM 认证标签长度（字节）


class CryptoUnavailable(RuntimeError):
    """未安装 cryptography，无法执行真加密。"""


def available() -> bool:
    """是否可用真加密（安装 cryptography 后为 True）。"""
    return AESGCM is not None


def _require() -> None:
    if AESGCM is None:
        raise CryptoUnavailable(
            "未安装 cryptography，无法使用 AES-256-GCM；"
            "请执行 pip install cryptography（或运行 install.bat）以启用军事级加密。"
        )


# ---------- 密钥材料 ----------
def new_salt() -> bytes:
    return secrets.token_bytes(_SALT_LEN)


def derive_key(passphrase: str, salt: bytes, iterations: int = _ITERATIONS) -> bytes:
    """由口令派生 256 位密钥（PBKDF2-HMAC-SHA256）。"""
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, iterations, dklen=_KEY_LEN
    )


def random_key() -> bytes:
    """生成一次性随机会话密钥（未持久化，进程退出即失效）。"""
    return secrets.token_bytes(_KEY_LEN)


# ---------- 加解密（信封格式：ZH1.<base64(nonce||ciphertext||tag)>）----------
def seal(plaintext: Union[str, bytes], key: bytes, aad: bytes | None = None) -> str:
    """加密，返回信封字符串。每条记录使用独立随机 nonce。"""
    _require()
    data = plaintext.encode("utf-8") if isinstance(plaintext, str) else plaintext
    nonce = secrets.token_bytes(_NONCE_LEN)
    blob = AESGCM(key).encrypt(nonce, bytes(data), aad)
    return f"{_MAGIC}." + base64.b64encode(nonce + blob).decode("ascii")


def unseal(envelope: str, key: bytes, aad: bytes | None = None) -> str:
    """解密信封；密文被篡改/密钥错误时抛异常（GCM 认证失败）。"""
    _require()
    prefix, _, payload = envelope.partition(".")
    if prefix != _MAGIC or not payload:
        raise ValueError("信封格式非法")
    raw = base64.b64decode(payload)
    if len(raw) <= _NONCE_LEN + _TAG_LEN:
        raise ValueError("信封长度非法")
    nonce, blob = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
    return AESGCM(key).decrypt(nonce, blob, aad).decode("utf-8")


def rotate(envelope: str, old_key: bytes, new_key: bytes,
           aad: bytes | None = None) -> str:
    """密钥轮换：用新密钥重新封装既有密文（无需暴露明文到磁盘）。"""
    return seal(unseal(envelope, old_key, aad), new_key, aad)


# ---------- 辅助 ----------
def ct_equal(a: Union[str, bytes], b: Union[str, bytes]) -> bool:
    """常数时间比较，避免时序侧信道。"""
    if isinstance(a, str):
        a = a.encode("utf-8")
    if isinstance(b, str):
        b = b.encode("utf-8")
    return hmac.compare_digest(a, b)


def wipe(buf: bytearray) -> None:
    """尽力而为地把承载秘密的缓冲区清零。"""
    try:
        for i in range(len(buf)):
            buf[i] = 0
    except Exception:
        pass


def fingerprint(key: bytes) -> str:
    """密钥指纹（SHA-256 前 16 位十六进制），便于日志核对而不泄露密钥。"""
    return hashlib.sha256(key).hexdigest()[:16]
