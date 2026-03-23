# Final Hardening Plan

## 목표
"슬슬 사용할 수 있게" 만드는 최종 단계는 다음 순서가 가장 안전합니다.

## P1-C (필수)
### 1. review queue 추가
이 단계가 핵심입니다.
현재 시스템은 **정확성은 보수적으로 좋지만 회수율이 낮은 상태**라서,
살릴 수 있는 글을 검토 큐로 빼야 실사용성이 올라갑니다.

#### 새 필드 권장
- `review_required: boolean`
- `review_reason_codes: string[]`
- `confidence_band: high | medium | low`

#### 규칙
- include=true and no warnings -> high
- include=true with mismatch warning -> medium + review
- exclude with recoverable reason -> low + review
- exclude with NO_DATA -> terminal, no review

### 2. labeled total-time near-miss만 좁게 확장
다음 alias는 허용해도 안전합니다.
- `시간`
- `총시간`
- `총 시간`
- `운동시간`
- `운동 시간`
- `소요시간`

허용 포맷:
- `47분`
- `47분54초`
- `1시간10분`
- `1시간 10분`
- `1시간42분02초`
- label이 있을 때만 `47:54`, `1:42:02`

금지:
- `/100m`
- `평균 페이스`
- `페이스`
- `랩`
- `구간`

### 3. OCR 운영 가드
- image hash cache
- 상세화면만 고신뢰 OCR
- feed/home card는 skip 또는 low-confidence review
- post별 OCR 이미지 cap 설정 가능

## P1-D (권장)
### 운영 리포트 생성
실행마다 아래를 자동 산출.
- source_counts
- include/exclude counts
- review queue counts
- top exclude reasons
- top warnings
- OCR cache hit rate
- posts with multiple images and timeout risk

## P1-E (선택)
### free-form total time 추정
이건 마지막 단계입니다.
지금은 추천하지 않습니다.
잘못된 총 시간 채택 위험이 큽니다.

## Go/No-Go
### Go 조건
- false include가 낮음
- review queue가 recoverable 실패를 흡수함
- dashboard/UI에서 include/review/exclude가 명확함
- data rebuild가 안정적으로 완료됨

### No-Go 조건
- review queue 없이 바로 완전자동 수집을 하려는 경우
- OCR-only 결과를 넓게 자동 포함하려는 경우
