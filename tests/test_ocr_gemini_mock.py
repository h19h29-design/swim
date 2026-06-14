from __future__ import annotations

from swimdash.ocr_gemini import GeminiOcrClient, GeminiOcrSettings, OCR_NO_API_KEY
from swimdash.ocr_cache import CachedImage


def test_gemini_ocr_returns_no_key_candidate_without_network(tmp_path):
    client = GeminiOcrClient(
        GeminiOcrSettings(
            enabled=True,
            api_key=None,
            model="test-model",
            fallback_model=None,
            cache_dir=tmp_path,
            min_confidence=0.85,
            max_images_per_post=1,
            max_calls_per_run=1,
            dry_run=False,
        )
    )

    result = client.extract_best_candidate(["https://example.com/a.png"])

    assert result["reason"] == OCR_NO_API_KEY
    assert client.calls_made == 0


def test_gemini_ocr_uses_cached_payload_without_calling_api(tmp_path, monkeypatch):
    client = GeminiOcrClient(
        GeminiOcrSettings(
            enabled=True,
            api_key="secret",
            model="test-model",
            fallback_model=None,
            cache_dir=tmp_path,
            min_confidence=0.85,
            max_images_per_post=1,
            max_calls_per_run=1,
            dry_run=False,
        )
    )
    client.cache.write_result(
        "abc",
        {
            "possible_distance_m": 1500,
            "possible_duration_text": "42:30",
            "possible_duration_seconds": 2550,
            "confidence": 0.93,
            "screen_type": "dcinside_image",
            "evidence_lines": ["거리 1.5km", "시간 42:30"],
            "model": "cached-model",
        },
    )

    monkeypatch.setattr(
        client.cache,
        "fetch_image",
        lambda _url: CachedImage("https://example.com/a.png", b"image", "abc", "image/png"),
    )

    result = client.extract_best_candidate(["https://example.com/a.png"])

    assert result["distance_m"] == 1500
    assert result["duration_seconds"] == 2550
    assert result["cache_key"] == "abc"
    assert result["model"] == "cached-model"
    assert client.calls_made == 0
