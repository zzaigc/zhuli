"""隔离快照与恢复：只复制，不删除，不触碰真实数据。

快照源与目标都必须通过 guard.ensure_isolated_dir 校验：
源是测试运行里的一份数据副本，目标是快照目录。恢复时把快照
文件复制回测试副本目录，覆盖同名文件；从不删除目标目录里
快照之外的文件，也不删除任何目录本身。
"""
from __future__ import annotations

import shutil
from pathlib import Path

from .guard import ensure_isolated_dir


def take_snapshot(source: str | Path, snapshot_dir: str | Path) -> Path:
    src = ensure_isolated_dir(source)
    dst = ensure_isolated_dir(snapshot_dir)
    if not src.exists():
        raise FileNotFoundError(f"chaos snapshot source missing: {src}")
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)
    return dst


def restore_snapshot(snapshot_dir: str | Path, target: str | Path) -> Path:
    snap = ensure_isolated_dir(snapshot_dir)
    tgt = ensure_isolated_dir(target)
    if not snap.exists():
        raise FileNotFoundError(f"chaos snapshot missing: {snap}")
    tgt.mkdir(parents=True, exist_ok=True)
    for item in snap.iterdir():
        dest = tgt / item.name
        if item.is_dir():
            shutil.copytree(item, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(item, dest)
    return tgt
