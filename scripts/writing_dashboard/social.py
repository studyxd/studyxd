from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .frontmatter import render_note, split_note
from .paths import IMAGE_EXTENSIONS, SOCIAL_COPY_FILENAMES, SOCIAL_STATUSES, is_hidden_name, relative_wikilink

SOCIAL_ORDER = ["title", "pages", "status", "auto_status", "cover", "source", "kind"]


@dataclass(frozen=True)
class SocialRecord:
    folder: Path
    title: str
    pages: int
    status: str
    auto_status: str
    cover: Path | None
    source: str
    copy_path: Path | None


def scan_social(vault: Path) -> list[SocialRecord]:
    root = vault / "social-cards"
    if not root.exists():
        return []
    records = []
    for folder in sorted(path for path in root.iterdir() if path.is_dir() and not path.is_symlink() and not is_hidden_name(path.name)):
        record = inspect_social(vault, folder)
        if record:
            records.append(record)
    return records


def inspect_social(vault: Path, folder: Path) -> SocialRecord | None:
    images = sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS and not is_hidden_name(path.name)
    )
    copy_path = next((folder / name for name in SOCIAL_COPY_FILENAMES if (folder / name).is_file()), None)
    meta: dict = {}
    copy_body = ""
    if copy_path:
        meta, copy_body = split_note(copy_path.read_text(encoding="utf-8"))
    if not images and not copy_body.strip() and not meta:
        return None
    explicit = str(meta.get("status", "") or "").strip()
    if explicit not in SOCIAL_STATUSES:
        explicit = ""
    inferred = _infer_status(images, copy_body)
    index_path = vault / "indexes" / "social" / f"{folder.name}.md"
    existing: dict = {}
    if index_path.is_file():
        existing, _ = split_note(index_path.read_text(encoding="utf-8"))
    status, auto_status = _resolve_status(explicit, inferred, existing)
    title = str(meta.get("title", "") or "").strip() or folder.name
    source = str(meta.get("source", "") or "").strip()
    return SocialRecord(
        folder=folder,
        title=title,
        pages=len(images),
        status=status,
        auto_status=auto_status,
        cover=images[0] if images else None,
        source=source,
        copy_path=copy_path,
    )


def write_social_index(vault: Path, record: SocialRecord) -> Path:
    destination = vault / "indexes" / "social" / f"{record.folder.name}.md"
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "title": record.title,
        "pages": record.pages,
        "status": record.status,
        "auto_status": record.auto_status,
        "cover": relative_wikilink(vault, record.cover) if record.cover else "",
        "source": record.source,
        "kind": "social",
    }
    lines = [f"原文件在 `social-cards/{record.folder.name}`，同步不会改那里。"]
    if record.copy_path:
        lines.extend(["", f"文案：{relative_wikilink(vault, record.copy_path)}"])
    lines.extend(["", f"共 {record.pages} 页。发布状态可以在看板上拖；`文案.md` 里如果写了 status，以文件为准。"])
    destination.write_text(render_note(data, "\n".join(lines), SOCIAL_ORDER), encoding="utf-8")
    return destination


def _infer_status(images: list[Path], copy_body: str) -> str:
    if images and copy_body.strip():
        return "待发布"
    return "制作中"


def _resolve_status(explicit: str, inferred: str, existing: dict) -> tuple[str, str]:
    if explicit:
        return explicit, explicit
    previous = str(existing.get("status", "") or "").strip()
    previous_auto = str(existing.get("auto_status", "") or "").strip()
    if previous and previous_auto and previous != previous_auto:
        return previous, inferred
    return inferred, inferred
