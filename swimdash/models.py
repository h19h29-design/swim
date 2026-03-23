from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class PostMeta:
    post_id: int
    url: str
    title: str
    subject: str
    author: str
    author_uid: str
    author_ip: str
    post_datetime: str


@dataclass(slots=True)
class SwimRecord:
    post_id: int
    url: str
    title: str
    author: str
    post_datetime: str
    post_date: str
    distance_m: int | None
    total_time_text: str | None
    total_seconds: int | None
    source: str
    include: bool
    score: int | None
    exclude_reason_code: str | None
    warning_codes: list[str]
    evidence_text: str
    review_needed: bool
    review_reason_code: str | None
    metric_bucket: str | None

    def to_dict(self) -> dict:
        payload = asdict(self)
        if payload["distance_m"] is not None:
            payload["distance_m"] = int(payload["distance_m"])
        if payload["total_seconds"] is not None:
            payload["total_seconds"] = int(payload["total_seconds"])
        payload["warning_codes"] = [str(code) for code in payload.get("warning_codes", []) if code]
        payload["review_needed"] = bool(payload.get("review_needed", False))
        return payload


@dataclass(slots=True)
class CrawledPost:
    post_id: int
    url: str
    title: str
    author: str
    post_datetime: str
    content_text: str
    image_urls: list[str]
