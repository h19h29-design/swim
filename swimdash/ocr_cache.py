from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import requests


@dataclass(slots=True)
class CachedImage:
    url: str
    content: bytes
    sha256: str
    mime_type: str


class OcrCache:
    def __init__(self, cache_dir: str | Path):
        self.cache_dir = Path(cache_dir)
        self.image_dir = self.cache_dir / "images"
        self.result_dir = self.cache_dir / "results"
        self.image_dir.mkdir(parents=True, exist_ok=True)
        self.result_dir.mkdir(parents=True, exist_ok=True)

    def fetch_image(self, url: str, *, timeout: int = 20) -> CachedImage:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": _user_agent()})
        response.raise_for_status()
        content = response.content
        digest = sha256_bytes(content)
        mime_type = _mime_type(response.headers.get("Content-Type"), content)
        image_path = self.image_dir / f"{digest}{_extension_for_mime(mime_type)}"
        if not image_path.exists():
            image_path.write_bytes(content)
        return CachedImage(url=url, content=content, sha256=digest, mime_type=mime_type)

    def read_result(self, cache_key: str) -> dict | None:
        path = self._result_path(cache_key)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def write_result(self, cache_key: str, payload: dict) -> None:
        path = self._result_path(cache_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _result_path(self, cache_key: str) -> Path:
        safe_key = "".join(ch for ch in cache_key if ch.isalnum() or ch in {"-", "_"})
        return self.result_dir / f"{safe_key}.json"


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _mime_type(content_type: str | None, content: bytes) -> str:
    raw = (content_type or "").split(";", 1)[0].strip().lower()
    if raw in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        return raw
    if content.startswith(b"\x89PNG"):
        return "image/png"
    if content.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def _extension_for_mime(mime_type: str) -> str:
    return {
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/jpeg": ".jpg",
    }.get(mime_type, ".jpg")


def _user_agent() -> str:
    return (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )
