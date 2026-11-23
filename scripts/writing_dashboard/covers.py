from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlparse
from urllib.request import Request, urlopen

_MAX_BYTES = 4 * 1024 * 1024
_TYPES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def candidate_urls(url: str) -> list[str]:
    """Prefer the original WeChat image when a feed wraps it in an image proxy."""
    found: list[str] = []
    query = parse_qs(urlparse(url).query)
    wrapped = query.get("u", [])
    if wrapped:
        found.append(unquote(wrapped[0]))
    if url not in found:
        found.append(url)
    return found


def download_cover(url: str, directory: Path, timeout: int = 25) -> Path | None:
    if not url or not url.startswith(("http://", "https://")):
        return None
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
    existing = list(directory.glob(f"{digest}.*"))
    if existing:
        return existing[0]
    for candidate in candidate_urls(url):
        for referer in ("https://mp.weixin.qq.com/", ""):
            payload, content_type = _fetch(candidate, referer, timeout)
            if payload:
                suffix = _TYPES.get(content_type) or _suffix_from_url(candidate)
                path = directory / f"{digest}{suffix}"
                path.write_bytes(payload)
                return path
    return None


def _fetch(url: str, referer: str, timeout: int) -> tuple[bytes, str]:
    headers = {"User-Agent": "Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
    request = Request(url, headers=headers)
    try:
        with urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
            payload = response.read(_MAX_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        return b"", ""
    if not _is_image(payload):
        return b"", ""
    return payload, content_type


def _is_image(payload: bytes) -> bool:
    if len(payload) < 32 or len(payload) > _MAX_BYTES:
        return False
    return payload.startswith((b"\xff\xd8", b"\x89PNG", b"RIFF", b"GIF8"))


def _suffix_from_url(url: str) -> str:
    lowered = url.lower().split("?", 1)[0]
    for suffix in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
        if lowered.endswith(suffix):
            return ".jpg" if suffix == ".jpeg" else suffix
    return ".jpg"
