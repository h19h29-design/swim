from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from swimdash.ocr_cache import OcrCache
from swimdash.record_resolver import (
    OCR_DISABLED,
    OCR_DISTANCE_ONLY,
    OCR_DURATION_ONLY,
    OCR_LOW_CONFIDENCE,
)

OCR_NO_API_KEY = "OCR_NO_API_KEY"
OCR_API_ERROR = "OCR_API_ERROR"
OCR_IMAGE_UNREADABLE = "OCR_IMAGE_UNREADABLE"

DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_FALLBACK_MODEL = "gemini-2.5-flash"
DEFAULT_CACHE_DIR = "data/ocr_cache"
DEFAULT_MAX_IMAGES_PER_POST = 3
DEFAULT_MAX_CALLS_PER_RUN = 30

OCR_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "raw_ocr_text": {"type": "string"},
        "possible_distance_m": {"type": "integer", "nullable": True},
        "possible_duration_text": {"type": "string", "nullable": True},
        "possible_duration_seconds": {"type": "integer", "nullable": True},
        "possible_pace_text": {"type": "string", "nullable": True},
        "screen_type": {"type": "string", "nullable": True},
        "evidence_lines": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "string"},
    },
    "required": [
        "raw_ocr_text",
        "possible_distance_m",
        "possible_duration_text",
        "possible_duration_seconds",
        "evidence_lines",
        "confidence",
        "notes",
    ],
}


@dataclass(slots=True)
class GeminiOcrSettings:
    enabled: bool
    api_key: str | None
    model: str
    fallback_model: str | None
    cache_dir: Path
    min_confidence: float
    max_images_per_post: int
    max_calls_per_run: int
    dry_run: bool


class GeminiOcrClient:
    def __init__(self, settings: GeminiOcrSettings | None = None):
        self.settings = settings or load_gemini_ocr_settings()
        self.cache = OcrCache(self.settings.cache_dir)
        self.calls_made = 0

    def extract_best_candidate(self, image_urls: Iterable[str]) -> dict:
        urls = [str(url) for url in image_urls if str(url or "").strip()]
        if not self.settings.enabled:
            return skipped_candidate(OCR_DISABLED)
        if not urls:
            return skipped_candidate(OCR_IMAGE_UNREADABLE)
        if not self.settings.api_key:
            return skipped_candidate(OCR_NO_API_KEY)
        if self.settings.dry_run:
            return skipped_candidate(OCR_DISABLED, warnings=["GEMINI_OCR_DRY_RUN"])

        candidates: list[dict] = []
        for url in urls[: self.settings.max_images_per_post]:
            candidate = self._extract_one(url)
            candidates.append(candidate)

        return _choose_best_candidate(candidates, self.settings.min_confidence)

    def _extract_one(self, url: str) -> dict:
        try:
            image = self.cache.fetch_image(url)
        except Exception as exc:  # noqa: BLE001
            return skipped_candidate(OCR_API_ERROR, warnings=[_safe_error(exc)])

        cached = self.cache.read_result(image.sha256)
        if cached is not None:
            return _candidate_from_payload(cached, cache_key=image.sha256, model=cached.get("model") or self.settings.model)

        if self.calls_made >= self.settings.max_calls_per_run:
            return skipped_candidate(OCR_API_ERROR, cache_key=image.sha256, warnings=["OCR_CALL_LIMIT_REACHED"])

        for model in _model_chain(self.settings.model, self.settings.fallback_model):
            self.calls_made += 1
            try:
                payload = _call_gemini(
                    model=model,
                    api_key=self.settings.api_key or "",
                    image_bytes=image.content,
                    mime_type=image.mime_type,
                )
            except Exception as exc:  # noqa: BLE001
                last_error = _safe_error(exc)
                continue

            payload["model"] = model
            payload["cache_key"] = image.sha256
            self.cache.write_result(image.sha256, payload)
            return _candidate_from_payload(payload, cache_key=image.sha256, model=model)

        return skipped_candidate(OCR_API_ERROR, cache_key=image.sha256, warnings=[locals().get("last_error", "unknown_error")])


def load_gemini_ocr_settings() -> GeminiOcrSettings:
    env_file = _read_dotenv(Path(".env"))
    return GeminiOcrSettings(
        enabled=_truthy(_env("SWIMDASH_ENABLE_GEMINI_OCR", "0", env_file)),
        api_key=_env("GEMINI_API_KEY", None, env_file),
        model=_env("GEMINI_MODEL", DEFAULT_MODEL, env_file) or DEFAULT_MODEL,
        fallback_model=_env("GEMINI_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL, env_file),
        cache_dir=Path(_env("GEMINI_OCR_CACHE_DIR", DEFAULT_CACHE_DIR, env_file) or DEFAULT_CACHE_DIR),
        min_confidence=_float_env("GEMINI_OCR_MIN_CONFIDENCE", 0.85, env_file),
        max_images_per_post=_int_env("GEMINI_OCR_MAX_IMAGES_PER_POST", DEFAULT_MAX_IMAGES_PER_POST, env_file),
        max_calls_per_run=_int_env("GEMINI_OCR_MAX_CALLS_PER_RUN", DEFAULT_MAX_CALLS_PER_RUN, env_file),
        dry_run=_truthy(_env("GEMINI_OCR_DRY_RUN", "0", env_file)),
    )


def skipped_candidate(reason: str, *, cache_key: str | None = None, warnings: list[str] | None = None) -> dict:
    return {
        "distance_m": None,
        "duration_seconds": None,
        "total_time_text": None,
        "confidence": 0.0,
        "reason": reason,
        "model": None,
        "cache_key": cache_key,
        "screen_type": None,
        "evidence_lines": [],
        "warnings": list(warnings or []),
    }


def _call_gemini(*, model: str, api_key: str, image_bytes: bytes, mime_type: str) -> dict:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError("google-genai package is required when Gemini OCR is enabled") from exc

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=[
            _ocr_prompt(),
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        ],
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=OCR_RESPONSE_SCHEMA,
        ),
    )
    text = getattr(response, "text", None) or _extract_response_text(response)
    parsed = _parse_json_text(text)
    parsed["raw_provider_response"] = _serializable_response(response, fallback_text=text)
    return parsed


def _candidate_from_payload(payload: dict, *, cache_key: str, model: str) -> dict:
    distance = payload.get("possible_distance_m")
    duration = payload.get("possible_duration_seconds")
    warnings = [str(item) for item in (payload.get("warnings") or []) if item]
    reason = payload.get("reason")
    if reason is None:
        if distance is not None and duration is None:
            reason = OCR_DISTANCE_ONLY
        elif distance is None and duration is not None:
            reason = OCR_DURATION_ONLY
        elif float(payload.get("confidence") or 0.0) <= 0:
            reason = OCR_IMAGE_UNREADABLE
        elif float(payload.get("confidence") or 0.0) < 0.01:
            reason = OCR_LOW_CONFIDENCE

    return {
        "distance_m": distance,
        "duration_seconds": duration,
        "total_time_text": payload.get("possible_duration_text"),
        "confidence": float(payload.get("confidence") or 0.0),
        "reason": reason,
        "model": model,
        "cache_key": cache_key,
        "screen_type": payload.get("screen_type"),
        "raw_ocr_text": payload.get("raw_ocr_text"),
        "evidence_lines": list(payload.get("evidence_lines") or []),
        "notes": payload.get("notes"),
        "warnings": warnings,
    }


def _choose_best_candidate(candidates: list[dict], min_confidence: float) -> dict:
    if not candidates:
        return skipped_candidate(OCR_IMAGE_UNREADABLE)

    complete = [
        item
        for item in candidates
        if item.get("distance_m") is not None and item.get("duration_seconds") is not None
    ]
    pool = complete or candidates
    best = max(pool, key=lambda item: float(item.get("confidence") or 0.0))
    if complete and float(best.get("confidence") or 0.0) < min_confidence:
        best = dict(best)
        best["reason"] = OCR_LOW_CONFIDENCE
    return best


def _extract_response_text(response) -> str:  # noqa: ANN001
    payload = _serializable_response(response, fallback_text="")
    candidates = payload.get("candidates") if isinstance(payload, dict) else []
    for candidate in candidates:
        parts = candidate.get("content", {}).get("parts") or []
        for part in parts:
            if isinstance(part.get("text"), str):
                return part["text"]
    raise RuntimeError("Gemini response did not include text")


def _parse_json_text(text: str) -> dict:
    cleaned = text.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    payload = json.loads(cleaned)
    if not isinstance(payload, dict):
        raise ValueError("Gemini OCR response must be a JSON object")
    return payload


def _serializable_response(response, *, fallback_text: str) -> dict:  # noqa: ANN001
    for method_name in ("model_dump", "to_json_dict"):
        method = getattr(response, method_name, None)
        if not callable(method):
            continue
        try:
            if method_name == "model_dump":
                payload = method(mode="json")
            else:
                payload = method()
            if isinstance(payload, dict):
                return payload
        except Exception:  # noqa: BLE001
            continue
    return {"text": fallback_text}


def _ocr_prompt() -> str:
    return (
        "수영 기록 이미지에서 총거리와 총운동시간만 추출하세요. "
        "페이스, 평균 페이스, /100m 기록, 심박수, 칼로리, 시작시각, 종료시각을 총시간으로 착각하지 마세요. "
        "km는 meter 정수로 변환하고 시간은 seconds 정수로 변환하세요. "
        "불확실하면 null과 낮은 confidence를 쓰세요. JSON만 반환하세요. "
        "필드: raw_ocr_text, possible_distance_m, possible_duration_text, possible_duration_seconds, "
        "possible_pace_text, screen_type, evidence_lines, confidence, warnings, notes."
    )


def _model_chain(primary: str, fallback: str | None) -> list[str]:
    rows = [primary]
    if fallback and fallback not in rows:
        rows.append(fallback)
    return rows


def _env(key: str, default: str | None, dotenv: dict[str, str]) -> str | None:
    return os.environ.get(key) or dotenv.get(key) or default


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _float_env(key: str, default: float, dotenv: dict[str, str]) -> float:
    try:
        return float(_env(key, str(default), dotenv) or default)
    except ValueError:
        return default


def _int_env(key: str, default: int, dotenv: dict[str, str]) -> int:
    try:
        return max(0, int(_env(key, str(default), dotenv) or default))
    except ValueError:
        return default


def _safe_error(exc: Exception) -> str:
    message = f"{type(exc).__name__}: {exc}"
    key = os.environ.get("GEMINI_API_KEY")
    if key:
        message = message.replace(key, "***")
    return message[:220]
