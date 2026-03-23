# TEXT_FORMAT_SPEC

## 현재 우선 양식
다음 2개 필드를 1순위로 파싱한다.

총거리 000
시간 1시간10분

## 필드 정의
### 1) 총거리
- canonical key: `distance_m`
- required: true
- label: `총거리`
- accepted value examples:
  - `925`
  - `1600`
  - `1,600`

### 2) 시간
- canonical key: `total_time`
- required: true
- label: `시간`
- accepted value examples:
  - `1시간10분`
  - `1시간 10분`
  - `39분35초`
  - `47분`
  - `1시간42분02초`

## 권장 파서 동작
- exact label 우선: `총거리`, `시간`
- label 뒤 공백/콜론은 허용:
  - `총거리 925`
  - `총거리: 925`
  - `시간 1시간10분`
  - `시간: 1시간10분`

## 정규화
- `distance_m`: int
- `total_time_text`: 원문 유지
- `total_seconds`: int
- `total_time_canonical`: `H:MM:SS` 또는 `MM:SS`

## 나중 확장 대비
이 스펙은 field config 배열로 관리하는 것이 좋다.
필드가 바뀌면 parser rule만 바꾸고 파이프라인은 유지한다.
