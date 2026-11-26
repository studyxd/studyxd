from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from urllib.parse import unquote
from xml.etree import ElementTree

from .paths import SHANGHAI_OFFSET_HOURS

SHANGHAI = timezone(timedelta(hours=SHANGHAI_OFFSET_HOURS))
_TAG = re.compile(r"<[^>]+>")
_IMG = re.compile(r"<img\b[^>]*?\bsrc\s*=\s*([\"'])(.*?)\1", re.IGNORECASE | re.DOTALL)
_READ_KEYS = {"read", "reads", "readcount", "read_count", "viewcount", "view_count"}
_DIGEST_LIMIT = 42


@dataclass(frozen=True)
class FeedItem:
    title: str
    link: str
    published: datetime
    digest: str
    cover_url: str
    reads: int | None

    @property
    def day(self) -> str:
        return self.published.astimezone(SHANGHAI).strftime("%Y-%m-%d")

    @property
    def published_text(self) -> str:
        return self.published.astimezone(SHANGHAI).strftime("%Y-%m-%dT%H:%M:%S")

    @property
    def key(self) -> str:
        return hashlib.sha1(self.link.encode("utf-8")).hexdigest()[:10]


def parse_feed(xml_bytes: bytes) -> list[FeedItem]:
    root = ElementTree.fromstring(xml_bytes)
    items: list[FeedItem] = []
    for node in root.iter():
        if _local(node.tag) not in {"item", "entry"}:
            continue
        item = _parse_entry(node)
        if item:
            items.append(item)
    items.sort(key=lambda item: item.published, reverse=True)
    return items


def _parse_entry(node: ElementTree.Element) -> FeedItem | None:
    title = ""
    link = ""
    published_raw = ""
    description = ""
    content = ""
    cover_url = ""
    reads: int | None = None

    for child in list(node):
        name = _local(child.tag).lower()
        text = (child.text or "").strip()
        if name == "title" and text:
            title = _plain(text)
        elif name == "link":
            href = child.attrib.get("href", "").strip()
            link = link or href or text
        elif name in {"pubdate", "published", "updated", "date"} and text and not published_raw:
            published_raw = text
        elif name == "description" and text:
            description = text
        elif name == "encoded" and text:
            content = text
        elif name in _READ_KEYS and text:
            reads = _parse_reads(text)
        elif name in {"enclosure", "content"} and not cover_url:
            cover_url = child.attrib.get("url", "")

    if not cover_url:
        cover_url = _first_image(content or description)
    published = _parse_datetime(published_raw)
    title = title.strip()
    link = unescape(link).strip()
    if not title or not link or published is None:
        return None
    return FeedItem(
        title=title,
        link=link,
        published=published,
        digest=clean_digest(description),
        cover_url=unescape(unquote(cover_url)).replace("&amp;", "&").strip(),
        reads=reads,
    )


def clean_digest(value: str) -> str:
    text = _plain(value)
    if not text or len(text) > _DIGEST_LIMIT:
        return ""
    return text


def _plain(value: str) -> str:
    text = unescape(value)
    text = _TAG.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def _first_image(html: str) -> str:
    match = _IMG.search(html or "")
    if not match:
        return ""
    return unescape(match.group(2)).strip()


def _parse_reads(value: str) -> int | None:
    digits = re.sub(r"[^\d]", "", value)
    if not digits:
        return None
    return int(digits)


def _parse_datetime(value: str) -> datetime | None:
    value = value.strip()
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        parsed = None
    if parsed is None:
        cleaned = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
