# OCR Strategy - Format First

## 핵심 정책
이 프로젝트는 이제 **Text Format First** 전략을 사용한다.

우선순위:
1. 게시글 텍스트 양식 파싱
2. 이미지 OCR fallback
3. 이미지 OCR 교차검증은 선택 사항

## 텍스트 우선 처리 규칙
### 기본 양식
- `총거리 000`
- `시간 1시간10분`

### 권장 파서 구조
- label 기반 파서:
  - `총거리` -> `distance_m`
  - `시간` -> `total_time`
- schema/config 기반 정의:
  - 필드명
  - 허용 라벨
  - 파싱 함수
  - required 여부

### 거리 파서
- 숫자와 콤마 허용
- 예:
  - `총거리 925`
  - `총거리 1,600`
- normalize:
  - 콤마 제거
  - 정수 meters로 저장

### 시간 파서
현재 label은 `시간`
파서는 아래를 허용하는 쪽이 좋다:
- `1시간10분`
- `1시간 10분`
- `39분35초`
- `47분`
- `1시간42분02초`

저장 시:
- 원문 `total_time_text`
- 정규화 `total_seconds`
- 필요하면 UI용 canonical `H:MM:SS` 또는 `MM:SS`

## 최종 우선순위 규칙
### Case A: 텍스트 양식 완전 파싱 성공
- 최종 source = `text_format`
- include = true
- 거리/시간 최종값은 텍스트 기준
- 이미지가 있어도 텍스트가 우선

### Case B: 텍스트 일부만 있음 / 파싱 실패
- 이미지 OCR fallback 시도
- OCR 성공 시 source = `image_fallback`
- include = true 가능
- reason/warning에 텍스트 파싱 실패 기록

### Case C: 텍스트 없음
- 이미지 OCR 시도
- OCR 성공 시 source = `image_ocr`
- 실패 시 exclude

### Case D: 텍스트와 이미지 둘 다 있음 + 값 불일치
- **텍스트를 최종값으로 채택**
- source = `text_format_with_image_mismatch`
- include = true
- warning code 남김
- 필요시 UI에서 mismatch badge 표시

## 이미지 OCR fallback 범위
v1에서는 딱 2개만 뽑는다.
- `distance_m`
- `total_time`

나머지는 나중:
- pace
- heart rate
- calories
- swolf
- strokes

## 이미지 템플릿 family
- `photo_header_detail_light`
- `photo_header_detail_dark`
- `garmin_detail_light`
- `garmin_detail_dark`
- `white_detail_card`
- `dashboard_chart_summary`
- `garmin_home_feed_dark` (manual review only)

## 이미지 auto include 정책
- 상세화면만 auto include 후보
- 홈/피드 카드형은 `MANUAL_REVIEW_ONLY`

## 구현 팁
- 텍스트 파서와 OCR 파서를 완전히 분리한다
- 둘의 출력은 마지막에 `normalized result`로 합친다
- UI는 오직 `include` boolean만 믿는다
