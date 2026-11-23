from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree.ElementTree import ParseError

from .covers import download_cover
from .frontmatter import render_note, split_note
from .paths import relative_wikilink
from .rss import SHANGHAI, FeedItem, parse_feed

WECHAT_ORDER = ["title", "account", "published", "day", "link", "cover", "reads", "digest", "status", "kind"]


@dataclass
class AccountResult:
    name: str
    created: int = 0
    updated: int = 0
    skipped: int = 0
    error: str = ""
    notice: str = ""


@dataclass
class CollectReport:
    results: list[AccountResult] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(item.error for item in self.results)


def collect_accounts(vault: Path, config: dict, limit: int | None = None, since_days: int | None = None, skip_covers: bool = False) -> CollectReport:
    per_account = limit if limit is not None else int(config.get("per_account", 12))
    window = since_days if since_days is not None else int(config.get("since_days", 14))
    cutoff = datetime.now(SHANGHAI) - timedelta(days=window)
    report = CollectReport()
    for account in config.get("accounts", []):
        report.results.append(_collect_one(vault, account, per_account, cutoff, skip_covers))
    return report


def _collect_one(vault: Path, account: dict, limit: int, cutoff: datetime, skip_covers: bool) -> AccountResult:
    name = str(account.get("name", "")).strip() or "未命名"
    feeds = [str(item).strip() for item in account.get("feeds", []) if str(item).strip()]
    result = AccountResult(name=name)
    if not feeds:
        result.notice = "还没有订阅地址"
        return result
    last_error = "订阅没有返回文章"
    for feed in feeds:
        try:
            payload = _read_feed(feed)
            items = parse_feed(payload)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, ParseError) as exc:
            last_error = f"{feed}：{exc.__class__.__name__}"
            continue
        chosen = []
        for item in items:
            if item.published.astimezone(SHANGHAI) < cutoff:
                result.skipped += 1
                continue
            chosen.append(item)
            if len(chosen) >= limit:
                break
        for item in chosen:
            created = _write_item(vault, name, item, skip_covers)
            if created:
                result.created += 1
            else:
                result.updated += 1
        return result
    result.error = last_error
    return result


def _read_feed(feed: str) -> bytes:
    if feed.startswith("file:"):
        path = Path(feed.removeprefix("file:"))
        return path.read_bytes()
    candidate = Path(feed)
    if candidate.is_file():
        return candidate.read_bytes()
    request = Request(feed, headers={"User-Agent": "writing-dashboard/1.0"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def _write_item(vault: Path, account: str, item: FeedItem, skip_covers: bool) -> bool:
    directory = vault / "topic-radar" / "items"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{item.day}-{account}-{item.key}.md"
    created = not path.exists()
    existing: dict = {}
    body = ""
    if path.exists():
        existing, body = split_note(path.read_text(encoding="utf-8"))
    cover = _cover_value(vault, item, skip_covers)
    data = {
        "title": item.title,
        "account": account,
        "published": item.published_text,
        "day": item.day,
        "link": item.link,
        "cover": cover or str(existing.get("cover", "") or ""),
        "reads": item.reads if item.reads is not None else existing.get("reads", ""),
        "digest": item.digest or str(existing.get("digest", "") or ""),
        "status": existing.get("status") or "待看",
        "kind": "wechat",
    }
    if not body.strip():
        body = _default_body(item)
    path.write_text(render_note(data, body, WECHAT_ORDER), encoding="utf-8")
    return created


def _cover_value(vault: Path, item: FeedItem, skip_covers: bool) -> str:
    if not item.cover_url:
        return ""
    if skip_covers:
        return item.cover_url
    saved = download_cover(item.cover_url, vault / "topic-radar" / "wechat-covers")
    if saved:
        return relative_wikilink(vault, saved)
    return item.cover_url


def _default_body(item: FeedItem) -> str:
    lines = [f"[打开原文]({item.link})"]
    if item.digest:
        lines.extend(["", item.digest])
    return "\n".join(lines)
