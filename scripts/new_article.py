#!/usr/bin/env python3
"""新建一篇只有调研笔记的文章目录。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from writing_dashboard.paths import vault_root
from writing_dashboard.scaffold import create_article


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    title = " ".join(args).strip()
    if not title:
        print("用法：python3 scripts/new_article.py 标题", file=sys.stderr)
        return 2
    try:
        folder = create_article(vault_root(), title)
    except FileExistsError as exc:
        print(f"目录已经在了：{exc}", file=sys.stderr)
        return 1
    print(folder.relative_to(vault_root()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
