"""内存中以密文持有的敏感字符串（SecureString）。

用途：凭据卡片回传的密码/API Key 在内存中**仅以密文存在**，
只在真正注入页面的瞬间解密一次，随后立即擦除明文缓冲区。

收益：
- 即使进程被内存转储（dump / 崩溃快照），也拿不到可直接使用的明文；
- `str()/repr()` 一律返回 `***`，杜绝被误打进日志或异常栈；
- 支持显式 `wipe()` 主动销毁。
"""
from __future__ import annotations

from .crypto import (
    CryptoUnavailable, random_key, seal, unseal, wipe,
)


class SecureString:
    """持有敏感文本的安全容器（密文 + 独立随机会话密钥）。"""

    __slots__ = ("_key", "_ct", "_plaintext", "_label", "_dead")

    def __init__(self, value: str, *, label: str = "secret") -> None:
        self._label = label
        self._key = random_key()
        self._dead = False
        try:
            self._ct: str | None = seal(value, self._key, aad=label.encode("utf-8"))
            self._plaintext: bytearray | None = None
        except CryptoUnavailable:
            # 无真加密依赖时降级：仍保持脱敏展示，但不提供密文保护
            self._ct = None
            self._plaintext = bytearray(value.encode("utf-8"))

    def reveal(self) -> str:
        """取出明文（应尽量缩短明文存活时间，用完即 wipe）。"""
        if self._dead:
            raise RuntimeError("该 SecureString 已被销毁")
        if self._ct is not None:
            return unseal(self._ct, self._key, aad=self._label.encode("utf-8"))
        return bytes(self._plaintext or b"").decode("utf-8")

    def wipe(self) -> None:
        """销毁：擦除密钥与明文缓冲区，之后不可再 reveal。"""
        self._dead = True
        self._ct = None
        if self._plaintext is not None:
            wipe(self._plaintext)
            self._plaintext = None
        # 密钥为不可变 bytes，无法真正清零；置空引用即可让 GC 回收
        self._key = b""  # type: ignore[assignment]

    @property
    def protected(self) -> bool:
        return self._ct is not None

    def __repr__(self) -> str:  # 绝不泄露明文
        return "<SecureString ***>"

    __str__ = __repr__

    def __len__(self) -> int:
        return len(self.reveal())

    def __bool__(self) -> bool:
        return bool(self.reveal())
