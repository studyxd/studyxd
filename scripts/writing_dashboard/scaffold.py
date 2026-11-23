from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from .articles import inspect_article, write_article_index
from .rss import SHANGHAI
from .social import inspect_social, write_social_index

_UNSAFE = re.compile(r'[\\/:*?"<>|\n\r]+')


def create_article(vault: Path, title: str, day: str | None = None) -> Path:
    title = title.strip()
    if not title:
        raise ValueError("需要一个标题")
    day = day or datetime.now(SHANGHAI).strftime("%Y-%m-%d")
    folder = vault / "articles" / f"{day}-{sanitize(title)}"
    if folder.exists():
        raise FileExistsError(folder)
    folder.mkdir(parents=True)
    (folder / "调研.md").write_text(_fill(vault, "调研.md", _RESEARCH, title, day), encoding="utf-8")
    record = inspect_article(folder)
    if record:
        write_article_index(vault, record)
    return folder


def create_social(vault: Path, title: str) -> Path:
    title = title.strip()
    if not title:
        raise ValueError("需要一个标题")
    folder = vault / "social-cards" / sanitize(title)
    if folder.exists():
        raise FileExistsError(folder)
    folder.mkdir(parents=True)
    (folder / "文案.md").write_text(_fill(vault, "文案.md", _COPY, title, ""), encoding="utf-8")
    record = inspect_social(vault, folder)
    if record:
        write_social_index(vault, record)
    return folder


def sanitize(title: str) -> str:
    text = _UNSAFE.sub("", title).strip()
    text = re.sub(r"\s+", "-", text)
    return text[:40] or "未命名"


def _fill(vault: Path, name: str, fallback: str, title: str, day: str) -> str:
    path = vault / "templates" / name
    template = path.read_text(encoding="utf-8") if path.is_file() else fallback
    return template.replace("{{title}}", title).replace("{{date:YYYY-MM-DD}}", day).replace("{{date}}", day)


_RESEARCH = """# {{title}}

还在收集材料。这篇目前只有调研笔记，看板会放在「调研中」。

- 
"""

_COPY = """---
title: "{{title}}"
status:
source:
---

发布文案写在这里。想固定状态就写「制作中」「待发布」或「已发布」。留空时，有图也有文案会先放在「待发布」。
"""
