"""在网页进程内导入 MassOmics-Agent-B 的 ``src.*`` 模块。

工作区根自己也有一个 ``src`` 包，网页后端多处会先 import 它；一旦 ``src`` 绑定到
工作区版本，再往 ``sys.path`` 插 B 根就不再生效，``src.output_layout`` /
``src.tools._artifact_resolve`` 这类 B 独有模块会 ModuleNotFoundError。

这里把 B 的 ``src`` 与 ``src/tools`` 目录追加到已导入包的 ``__path__``：
两边同名的模块仍优先解析工作区版本，只有工作区缺失的名字才会落到 B。
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType

# B 的 src 下需要一并扩展搜索路径的子包
_SUBPACKAGES = ("tools",)


def _extend_path(module: ModuleType, directory: Path) -> None:
    paths = getattr(module, "__path__", None)
    if paths is None or not directory.is_dir():
        return
    entry = str(directory)
    if entry not in list(paths):
        paths.append(entry)


def ensure_b_importable(project_root: Path | None = None) -> Path:
    """让 ``import src.<B 独有模块>`` 在当前进程可用，返回 B 仓库根。"""
    from web_frontend.backend.agent_backends import massomics_b_root

    root = massomics_b_root(project_root)
    b_src = root / "src"
    if not b_src.is_dir():
        raise ModuleNotFoundError(f"未找到 MassOmics-Agent-B 的 src 目录：{b_src}")

    package = sys.modules.get("src")
    if package is None:
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        package = importlib.import_module("src")
    _extend_path(package, b_src)

    for name in _SUBPACKAGES:
        target = b_src / name
        if not target.is_dir():
            continue
        sub = sys.modules.get(f"src.{name}")
        if sub is None:
            try:
                sub = importlib.import_module(f"src.{name}")
            except ImportError:
                continue
        _extend_path(sub, target)

    importlib.invalidate_caches()
    return root
