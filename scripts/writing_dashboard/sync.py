from __future__ import annotations

from pathlib import Path

from .articles import scan_articles, write_article_index
from .collect import CollectReport, collect_accounts
from .paths import load_accounts
from .social import scan_social, write_social_index

_START = "<!-- sync:start -->"
_END = "<!-- sync:end -->"


def sync_vault(vault: Path, limit: int | None = None, since_days: int | None = None, skip_covers: bool = False, index_only: bool = False, collect_only: bool = False) -> tuple[CollectReport | None, int, int]:
    report = None
    article_count = 0
    social_count = 0
    if not index_only:
        config = load_accounts(vault)
        report = collect_accounts(vault, config, limit=limit, since_days=since_days, skip_covers=skip_covers)
        _write_follow_list(vault, config, report)
    if not collect_only:
        for record in scan_articles(vault):
            write_article_index(vault, record)
            article_count += 1
        for record in scan_social(vault):
            write_social_index(vault, record)
            social_count += 1
        _remove_stale_indexes(vault / "indexes" / "articles", {record.folder.name + ".md" for record in scan_articles(vault)})
        _remove_stale_indexes(vault / "indexes" / "social", {record.folder.name + ".md" for record in scan_social(vault)})
    return report, article_count, social_count


def format_report(report: CollectReport | None, article_count: int, social_count: int) -> str:
    lines = []
    if report:
        for item in report.results:
            if item.error:
                lines.append(f"{item.name}：失败，{item.error}")
            elif item.notice:
                lines.append(f"{item.name}：{item.notice}")
            else:
                lines.append(f"{item.name}：新增 {item.created}，更新 {item.updated}，更早的跳过 {item.skipped}")
    lines.append(f"文章索引 {article_count} 篇，小红书图文索引 {social_count} 套")
    return "\n".join(lines)


def _write_follow_list(vault: Path, config: dict, report: CollectReport) -> None:
    path = vault / "topic-radar" / "关注列表.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["| 公众号 | 这次同步 |", "| --- | --- |"]
    by_name = {item.name: item for item in report.results}
    for account in config.get("accounts", []):
        name = account.get("name", "")
        item = by_name.get(name)
        if item is None:
            detail = "未跑"
        elif item.error:
            detail = f"失败：{item.error}"
        elif item.notice:
            detail = item.notice
        else:
            detail = f"新增 {item.created}，更新 {item.updated}"
        rows.append(f"| {name} | {detail} |")
    block = "\n".join(rows)
    if path.exists() and _START in path.read_text(encoding="utf-8") and _END in path.read_text(encoding="utf-8"):
        text = path.read_text(encoding="utf-8")
        before, rest = text.split(_START, 1)
        _, after = rest.split(_END, 1)
        path.write_text(f"{before}{_START}\n{block}\n{_END}{after}", encoding="utf-8")
        return
    path.write_text(
        "\n".join(
            [
                "# 关注列表",
                "",
                "选题池盯着这几个公众号。订阅地址写在 `scripts/accounts.json` 的 `feeds` 里，同步脚本每次只改下面的表格。",
                "",
                _START,
                block,
                _END,
                "",
                "阅读进度在看板上拖。已经拖过的文章，下次同步还会留在原来的那一列。",
                "",
            ]
        ),
        encoding="utf-8",
    )


def _remove_stale_indexes(directory: Path, expected: set[str]) -> None:
    if not directory.exists():
        return
    for path in directory.glob("*.md"):
        if path.name not in expected:
            path.unlink()
