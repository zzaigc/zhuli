"""安全与加密子系统（军事级）。

- `crypto`       ：AES-256-GCM（AEAD）+ PBKDF2-HMAC-SHA256 原语
- `secure_string`：内存中仅以密文持有的敏感字符串
- `vault`        ：OS keyring + AES-256-GCM 信封的双层加密保险库
"""
from __future__ import annotations

from .crypto import (
    CryptoUnavailable, available, ct_equal, derive_key, fingerprint,
    new_salt, random_key, rotate, seal, unseal, wipe,
)
from .secure_string import SecureString
from .vault import SecurityVault

__all__ = [
    "CryptoUnavailable", "available", "seal", "unseal", "rotate",
    "derive_key", "new_salt", "random_key", "ct_equal", "wipe", "fingerprint",
    "SecureString", "SecurityVault",
]
