#!/usr/bin/env python3
"""拉取同行公众号，并给自己的文章、小红书图文生成索引。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from writing_dashboard.paths import vault_root
from writing_dashboard.sync import format_report, sync_vault


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="同步写作工作台。原文件不会被修改。")
    parser.add_argument("--vault", type=Path, default=None, help="库根目录，默认是仓库根目录")
    parser.add_argument("--index-only", action="store_true", help="只重建文章和图文索引")
    parser.add_argument("--collect-only", action="store_true", help="只拉取公众号")
    parser.add_argument("--limit", type=int, default=None, help="每个号最多写入几篇")
    parser.add_argument("--since-days", type=int, default=None, help="只收录最近多少天")
    parser.add_argument("--skip-covers", action="store_true", help="不下载封面，封面留远程地址")
    args = parser.parse_args(argv)
    if args.index_only and args.collect_only:
        parser.error("--index-only 和 --collect-only 不能一起用")
    vault = (args.vault or vault_root()).resolve()
    report, article_count, social_count = sync_vault(
        vault,
        limit=args.limit,
        since_days=args.since_days,
        skip_covers=args.skip_covers,
        index_only=args.index_only,
        collect_only=args.collect_only,
    )
    print(format_report(report, article_count, social_count))
    if report and report.failed:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
