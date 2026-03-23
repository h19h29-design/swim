# CHANGELOG

## 2026-03-06

### Fixed
- 대시보드 제외 여부 매핑 보강 (`docs/assets/app.js`)
  - `is_excluded` 필드명 fallback(`is_excluded`/`excluded`/`isExcluded`) 추가
  - 문자열 boolean coercion 강화 (`"true"/"false"`)
  - 제외 배지 렌더에서 bool 강제 사용
- 기존 records 재정규화 시 포함 정책 재강제 (`swimdash/pipeline.py`)
  - 포함은 `text_strict_pair` 또는 `image_ocr_template_sum`만 허용
  - 그 외는 자동으로 `is_excluded=true` + 사유 보정

### Changed
- 포함 정책 강제 (`swimdash/parser.py`)
  - 포함은 `text_strict_pair` 또는 `image_ocr_template_sum`만 허용
  - 그 외는 모두 제외
  - strict 콜론 양식(`거리:` + `시간:`)만 strict pair로 인정
  - 점수 규칙 고정: strict=90, image=80, strict+image=100, image 거리 out-of-range(<400/>2500)=70
- 제외 사유 정리
  - `distance_le_500_weak_evidence`
  - `distance_ge_2000_weak_evidence`
  - `image_parse_failed_or_incomplete`
  - `missing_distance` / `missing_duration` / `missing_both`
  - `no_strict_pair_and_no_image_pair`
- 이미지 OCR 구조 개편 (`swimdash/ocr.py`)
  - template extractor 분리: apple/samsung/generic
  - 이미지별 pair 파싱 후 게시글 단위 합산
  - Apple: 괄호 거리 합산 fallback, HH:MM:SS 우선, 시간범위 제외
  - Samsung: 상단 거리 crop + 카드 시간 crop, psm7/6 whitelist
  - threshold 멀티패스/숫자 정규화/품질 게이트(distance<100)
- debug-ocr 개선 (`swimdash/cli.py`)
  - template 판정/점수 출력
  - 파일명 expected(`_<distance>_<time>`) 자동 계산 및 match 출력
  - cp949 콘솔 안전 출력
- 대시보드 표시 버그 방어 강화 (`docs/assets/app.js`)
  - `is_excluded` 필드명/문자열 bool coercion 보강
  - source/exclude reason 매핑 확장
- OCR 템플릿 추출 개선 (`swimdash/ocr.py`)
  - samsung/apple 전용 crop 확장(상단/카드/패널 + threshold/invert/RGB 보강)
  - `image_to_data` 기반 단어 confidence/height 후보 반영
  - 애플 duration에서 HH:MM:SS 우선/시간범위 배제 강화
  - 애플 괄호합산 중복 누적 방지(패스별 합산)
  - 거리 score에 25m 배수 가중치 반영
  - 게시글 다중 이미지에서 URL/바이너리 해시 중복 제거 후 합산

### Added
- 테스트 강화
  - strict pair 포함 강제 테스트
  - strict/image 점수(90/80/100/70) 테스트
  - weak evidence(50/2550/2800) 제외 테스트
  - Apple OCR 텍스트(괄호 합산/시간범위 제외/HH:MM:SS 우선) 테스트
  - 다중 이미지 합산 + 중복 이미지 payload 미합산 테스트

### Verification
- `python -m pytest -q` -> `27 passed, 1 skipped`
- `python -m swimdash debug-ocr --dir local_samples/images` 실행 완료
- `python -m swimdash incremental --lookback-days 3 --recent-pages 20 --rate-limit 0.55 --timeout 20` 실행 완료
- `python -m swimdash rebuild` 실행 완료
