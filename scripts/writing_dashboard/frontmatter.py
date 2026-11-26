from __future__ import annotations

import json
import re
from collections.abc import Mapping

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
_INT = re.compile(r"-?\d+\Z")


def split_note(text: str) -> tuple[dict, str]:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    match = _FRONTMATTER.match(text)
    if not match:
        return {}, text
    return parse_frontmatter(match.group(1)), text[match.end() :]


def parse_frontmatter(block: str) -> dict:
    data: dict = {}
    for raw in block.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        data[key] = _parse_value(value)
    return data


def _parse_value(value: str):
    if value == "" or value in {"null", "~"}:
        return ""
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return json.loads(value)
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if _INT.fullmatch(value):
        return int(value)
    if value in {"true", "false"}:
        return value == "true"
    return value


def dump_frontmatter(data: Mapping, order: list[str] | None = None) -> str:
    keys = list(order or [])
    for key in data:
        if key not in keys:
            keys.append(key)
    lines = ["---"]
    for key in keys:
        if key not in data:
            continue
        value = data[key]
        if value is None or value == "":
            continue
        lines.append(f"{key}: {_format_value(key, value)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _format_value(key: str, value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    text = str(value)
    if key in {"published", "day", "date"} and _is_bare_date(text):
        return text
    return json.dumps(text, ensure_ascii=False)


def _is_bare_date(text: str) -> bool:
    return bool(
        re.fullmatch(r"\d{4}-\d{2}-\d{2}", text)
        or re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", text)
    )


def render_note(data: Mapping, body: str, order: list[str] | None = None) -> str:
    body = body.strip("\n")
    suffix = f"\n\n{body}\n" if body else "\n"
    return dump_frontmatter(data, order) + suffix
