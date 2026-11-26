from __future__ import annotations

import json
from pathlib import Path

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
SHANGHAI_OFFSET_HOURS = 8

BODY_FILENAMES = ("正文.md", "草稿.md", "draft.md", "文章.md")
ARCHIVE_FILENAMES = ("归档.md",)
RESEARCH_HINTS = ("调研", "research")
SOCIAL_COPY_FILENAMES = ("文案.md", "发布文案.md", "caption.md")

READING_STATUSES = ("待看", "可借鉴", "已看")
WRITING_STAGES = ("调研中", "写作中", "已完稿")
SOCIAL_STATUSES = ("制作中", "待发布", "已发布")


def vault_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_accounts(vault: Path) -> dict:
    path = vault / "scripts" / "accounts.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("since_days", 14)
    data.setdefault("per_account", 12)
    data.setdefault("accounts", [])
    return data


def is_hidden_name(name: str) -> bool:
    return name.startswith(".") or name.startswith("_")


def relative_wikilink(vault: Path, path: Path) -> str:
    rel = path.resolve().relative_to(vault.resolve()).as_posix()
    if rel.endswith(".md"):
        rel = rel[:-3]
    return f"[[{rel}]]"
