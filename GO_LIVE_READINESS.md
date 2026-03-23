# Swimming Dashboard - Go Live Readiness

## 현재 판단
현재 상태는 **판정 일관성은 안정화되었지만, 추출 회수율(recall)은 아직 보수적**입니다.

즉:
- **안정성 측면**: 이전보다 훨씬 좋아짐
  - backend가 include/exclude를 단일 판정
  - UI가 backend include만 사용
  - text 우선, image는 fallback으로 동작
- **회수율 측면**: 아직 부족함
  - 실데이터에서 strict 양식 매칭이 거의 없음
  - legacy distance는 회복되기 시작했지만, total time 미추출이 여전히 큼
  - 최근 지표상 `TEXT_TIME_MISSING`과 `IMAGE_PARSE_FAILED`가 핵심 병목

## 결론
- **바로 써도 되는가?**
  - **예, 단 "고신뢰 자동집계 + 검토 큐" 모드로는 가능**
  - **아니오, "완전 자동 수집" 모드로는 아직 이름을 붙이기 어려움**

## 권장 운영 모드
### 1) 지금 당장 사용 가능한 모드
- 자동 포함 대상:
  - `text_format`
  - `text_legacy` 중 거리+시간 모두 충족
  - `text_image_merge` 중 경고가 치명적이지 않은 경우
  - `image_ocr`는 상세화면 + guardrail 통과 케이스만
- 자동 제외 대상:
  - `NO_DATA`
  - diary/free-form only
  - OCR-only outlier
- 검토 큐 대상:
  - `TEXT_TIME_MISSING`
  - `IMAGE_PARSE_FAILED`인데 텍스트에서 거리만 회복된 경우
  - `TEXT_IMAGE_MISMATCH`

### 2) 지금 당장 추천하지 않는 모드
- 모든 OCR 결과 자동 포함
- free-form 숫자를 광범위하게 추정해서 자동 채택
- UI에서 다시 include/exclude를 재판정

## 운영 안정성 점검
### 이미 안정적인 것
- 결과 스키마 정규화
- 집계가 backend include를 신뢰
- text > image 우선순위
- OCR-only 이상치 일부 차단

### 아직 불안정한 것
- total time이 없는 레거시 텍스트 처리
- 여러 이미지가 있는 글의 OCR fan-out 비용
- free-form set log에서 total time을 어디까지 허용할지 기준
- recoverable 실패와 terminal 실패의 구분 UX

## 지금부터의 목표
자동 정확도를 무리하게 끌어올리기보다,
**"잘못 포함하지 않는 것" + "살릴 수 있는 글을 검토 큐로 보내는 것"** 이 더 중요합니다.

## 출시 전 필수 3개
1. **검토 큐(review queue)** 추가
2. **운영 지표 페이지/로그** 추가
3. **재처리 안전장치(cache/runtime cap)** 추가

## 검토 큐 규칙
### review_required = true
다음 조건 중 하나면 검토 큐로 보냄.
- `exclude_reason_code == TEXT_TIME_MISSING`
- `exclude_reason_code == IMAGE_PARSE_FAILED` AND `distance_m != null`
- `warning_codes` includes `TEXT_IMAGE_MISMATCH`
- `source == image_ocr` AND confidence/guardrail borderline

### review UI에 보여줄 최소 필드
- post_id
- title / date
- source
- distance_m
- total_time_text
- include
- exclude_reason_code
- warning_codes
- image_count
- text preview

## 런타임/성능 안정화
### 지금 꼭 필요한 가드
- OCR cache by image hash
- post당 OCR 최대 이미지 수 제한 (운영값 분리)
- 상세화면이 아닌 레이아웃은 조기 skip
- verification script와 production runtime 설정 분리

## 운영 지표
다음 카운트는 매 실행마다 남기는 것이 좋습니다.
- total_record_count
- included_record_count
- excluded_record_count
- review_required_count
- source_counts
- exclude_reason_counts
- warning_code_counts
- avg_images_per_post
- OCR_processed_images
- OCR_skipped_images
- OCR_cache_hit_rate

## 출시 판단 기준
### 바로 사용 가능 (권장)
- high-confidence auto include + review queue 운영
- 최근 검증 샘플에서 잘못 포함(false include)이 매우 낮음
- review queue가 주요 recoverable 실패를 흡수함

### 완전 자동 출시 전 추가 필요
- labeled total-time near-miss 규칙 확장
- review queue 감소
- OCR runtime 최적화
- 최근 50~100 posts 재검증
