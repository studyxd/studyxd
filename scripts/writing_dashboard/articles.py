from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .frontmatter import render_note, split_note
from .paths import ARCHIVE_FILENAMES, BODY_FILENAMES, IMAGE_EXTENSIONS, RESEARCH_HINTS, is_hidden_name, relative_wikilink

_DATE_IN_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})")
_MD_IMAGE = re.compile(r"!\[[^\]]*]\(([^)]+)\)")
_WIKI_IMAGE = re.compile(r"!\[\[([^\]|#]+)")

ARTICLE_ORDER = ["title", "date", "year", "stage", "summary", "cover", "source", "kind"]


@dataclass(frozen=True)
class ArticleRecord:
    folder: Path
    title: str
    stage: str
    date: str
    summary: str
    cover: Path | None
    source: Path | None


def scan_articles(vault: Path) -> list[ArticleRecord]:
    root = vault / "articles"
    if not root.exists():
        return []
    records = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir() and not path.is_symlink() and not is_hidden_name(path.name)):
        record = inspect_article(folder)
        if record:
            records.append(record)
    return records


def inspect_article(folder: Path) -> ArticleRecord | None:
    markdown = [path for path in folder.rglob("*.md") if path.is_file() and not is_hidden_name(path.name)]
    if not markdown:
        return None
    research = [path for path in markdown if _is_research(path)]
    bodies = [path for path in markdown if path.name in BODY_FILENAMES]
    archives = [path for path in markdown if path.name in ARCHIVE_FILENAMES]
    meta_path = archives[0] if archives else (bodies[0] if bodies else None)
    meta = _read_meta(meta_path) if meta_path else {}
    body_text = _body_text(bodies[0]) if bodies else ""
    meta_title = _clean(meta.get("title", ""))
    meta_date = _normalize_date(meta.get("date", ""))
    meta_summary = _clean(meta.get("summary", ""))
    title = meta_title or _title_from_folder(folder.name)
    date = meta_date or _date_from_folder(folder.name)
    summary = meta_summary
    archived = bool(meta_title and meta_date and meta_summary)
    if archived:
        stage = "已完稿"
    elif body_text:
        stage = "写作中"
    elif research:
        stage = "调研中"
    else:
        return None
    source = bodies[0] if bodies else (research[0] if research else meta_path)
    return ArticleRecord(
        folder=folder,
        title=title,
        stage=stage,
        date=date,
        summary=summary,
        cover=_find_cover(folder, bodies[0] if bodies else None),
        source=source,
    )


def write_article_index(vault: Path, record: ArticleRecord) -> Path:
    destination = vault / "indexes" / "articles" / f"{record.folder.name}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "title": record.title,
        "date": record.date,
        "year": record.date[:4] if len(record.date) >= 4 else "",
        "stage": record.stage,
        "summary": record.summary,
        "cover": relative_wikilink(vault, record.cover) if record.cover else "",
        "source": relative_wikilink(vault, record.source) if record.source else "",
        "kind": "article",
    }
    lines = [f"进度由 `articles/{record.folder.name}` 里的文件决定，下次同步会按文件重算。"]
    if record.source:
        lines.append("")
        lines.append(f"原稿：{relative_wikilink(vault, record.source)}")
    destination.write_text(render_note(data, "\n".join(lines), ARTICLE_ORDER), encoding="utf-8")
    return destination


def _is_research(path: Path) -> bool:
    lowered = path.name.lower()
    return any(hint in lowered or hint in path.name for hint in RESEARCH_HINTS)


def _read_meta(path: Path) -> dict:
    data, _ = split_note(path.read_text(encoding="utf-8"))
    return data


def _body_text(path: Path) -> str:
    _, body = split_note(path.read_text(encoding="utf-8"))
    return body.strip()


def _clean(value) -> str:
    return str(value or "").strip()


def _title_from_folder(name: str) -> str:
    match = _DATE_IN_NAME.match(name)
    if match:
        name = name[match.end() :]
    return name.lstrip("-_ ").strip() or name


def _date_from_folder(name: str) -> str:
    match = _DATE_IN_NAME.search(name)
    return match.group(1) if match else ""


def _normalize_date(value) -> str:
    text = _clean(value)
    match = _DATE_IN_NAME.search(text)
    return match.group(1) if match else ""


def _find_cover(folder: Path, body: Path | None) -> Path | None:
    if body:
        text = body.read_text(encoding="utf-8")
        for pattern in (_WIKI_IMAGE, _MD_IMAGE):
            for match in pattern.finditer(text):
                resolved = _resolve_image(folder, match.group(1).strip())
                if resolved:
                    return resolved
    images = sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and not is_hidden_name(path.name)
    )
    return images[0] if images else None


def _resolve_image(folder: Path, raw: str) -> Path | None:
    raw = raw.split("|", 1)[0].strip().strip("<>")
    if not raw or "://" in raw:
        return None
    candidates = [folder / raw, folder.parent / raw]
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix.lower() in IMAGE_EXTENSIONS:
            return candidate
    return None
