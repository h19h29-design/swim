from __future__ import annotations

from swimdash.ocr_cache import OcrCache, sha256_bytes


def test_ocr_cache_round_trips_result_payload(tmp_path):
    cache = OcrCache(tmp_path / "ocr")
    payload = {"possible_distance_m": 1500, "confidence": 0.91}

    cache.write_result("abc123", payload)

    assert cache.read_result("abc123") == payload
    assert cache.read_result("missing") is None


def test_sha256_bytes_is_stable():
    assert sha256_bytes(b"same-image") == sha256_bytes(b"same-image")
    assert sha256_bytes(b"same-image") != sha256_bytes(b"other-image")
