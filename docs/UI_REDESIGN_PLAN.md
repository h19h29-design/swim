# UI Redesign + Domain + OCR Harness Plan

작성일: 2026-06-14
브랜치: feature/cartoon-dot-swim-dashboard-domain-ocr
대상 레포: https://github.com/h19h29-design/swim
기준 시안: C:\Users\user\Downloads\ChatGPT Image 2026년 6월 14일 오전 10_20_04.png

## 1. 목표

- 기존 DCInside 수영일기 미니갤 `일기` 글 수집, 제목 파싱, records/dashboard_views/review_queue/parse_status, 시즌 랭킹, 개인 프로필, 배지, 관리자 기능을 깨지 않는다.
- 첨부 시안의 카툰/도트/블루 수영장 대시보드 느낌으로 데스크톱과 모바일 UI를 전면 개선한다.
- 새 공개 도메인은 `https://swim.h19h19.com/` 기준으로 문서화한다.
- 기존 `duckdns + 8766` 구조는 롤백 경로로 유지한다.
- Gemini OCR은 최종 확정이 아니라 후보 파싱으로만 사용한다.
- API 키는 환경변수로만 사용하며, 키가 없거나 OCR이 꺼져도 `refresh/rebuild`는 실패하지 않아야 한다.

## 2. 현재 구조 분석

### 운영 파이프라인

- `swimdash/crawler.py`: DCInside `swimmingdiary` 목록/상세 수집.
- `swimdash/parser.py`: 제목의 공식 `거리 / 시간` 형식 파싱.
- `swimdash/body_parser.py`: 본문 후보 파싱.
- `swimdash/ocr_gemini.py`: Gemini OCR 후보 추출. 기본 비활성화.
- `swimdash/ocr_cache.py`: 이미지 sha256 기반 OCR 캐시.
- `swimdash/record_resolver.py`: title/body/ocr 후보를 최종 record 후보로 결정.
- `swimdash/pipeline.py`: records 병합, 수동 보정 적용, docs/data JSON 생성.
- `swimdash/aggregate.py`: 시즌/랭킹/프로필/배지용 집계 데이터 생성.
- `swimdash/cli.py`: `incremental`, `refresh`, `rebuild`, `serve` 등 CLI와 관리자 서버.

### 공개 프론트엔드

- `docs/index.html`: 데스크톱 대시보드.
- `docs/mobile.html`: 모바일 대시보드.
- `docs/profile.html`: 개인 프로필.
- `docs/badge-gallery.html`: 배지 갤러리.
- `docs/parse-status.html`: 파싱/검토 상태.
- `docs/assets/app.js`: 데스크톱 화면 렌더링.
- `docs/assets/mobile.js`: 모바일 화면 렌더링.
- `docs/assets/profile.js`: 개인 프로필 렌더링.
- `docs/assets/badge-gallery.js`: 배지 갤러리 렌더링.
- `docs/assets/dashboard-common.js`: JSON 로더, 포맷터, 시즌/프로필/배지 공통 로직.

### 공개 데이터

- `docs/data/records.json`: 게시글별 정규화 기록.
- `docs/data/dashboard_views.json`: 시즌1/시즌2/누적 대시보드 통합 데이터.
- `docs/data/review_queue.json`: 검토 대기.
- `docs/data/parse_status.json`: 파싱 실패/성공 상태.
- `docs/data/author_profiles.json`: 개인 프로필.
- `docs/data/badge_index.json`: 배지/칭호 인덱스.
- `docs/data/site_config.json`: 공개 사이트 설정.

## 3. 작업 범위

### UI

- 데스크톱: 좌측 사이드바, 상단 검색/새로고침/관리자, KPI 카드, 시즌 Hero 진행 카드, 차트 카드, TOP10 랭킹, 최근 기록, 검토/OCR 상태, 최근 배지를 시안처럼 카툰/도트 스타일로 강화한다.
- 모바일: 별도 모바일 화면 유지, 하단 탭 유지, Hero/KPI/랭킹/최근 기록/배지 카드가 작은 화면에서 깨지지 않게 조정한다.
- 기존 DOM id와 JS 데이터 흐름은 최대한 유지한다.
- 시각 요소는 CSS 변수, 물결/버블/하프톤 배경, 둥근 카드, 스티커형 배지, 캐릭터 느낌의 CSS/SVG 일러스트로 구현한다.

### 도메인/배포 문서

- `docs/NAS_DEPLOY.md`에 `swim.h19h19.com` reverse proxy 기준을 추가한다.
- README에도 신규 도메인 기준과 기존 duckdns/8766 롤백 경로를 정리한다.
- `compose.yaml`과 Docker 기본 포트 8766은 유지한다.

### OCR/파싱

- 기존 구현된 `record_resolver.py`, `ocr_gemini.py`, `ocr_cache.py`를 검토하고 필요한 경우 안전성만 보강한다.
- 최종 우선순위는 `manual override > title/body/ocr 일치 > title > body > 고신뢰 OCR > review_queue`로 문서화하고 테스트로 보호한다.
- `--skip-ocr`가 `refresh`, `incremental`, `refresh-from-floor`, `refresh-window`에서 동작하는지 확인한다.
- `SWIMDASH_ENABLE_GEMINI_OCR=0` 또는 API 키 없음 상태에서 실패하지 않아야 한다.

## 4. 건드리지 않을 것

- 운영 데이터 삭제/초기화.
- `git reset`, 강제 checkout, destructive cleanup.
- API 키 커밋.
- Docker 내부 포트 8766 변경.
- 기존 duckdns 운영 경로 제거.
- 관리자 API 동작 방식의 불필요한 변경.

## 5. 오픈소스 참고 원칙

- 참고 대상은 라이선스가 명확한 대시보드/반응형/차트/접근성 패턴으로 제한한다.
- 코드를 그대로 복사하지 않고, CSS 변수 구조, 반응형 카드 레이아웃, 모바일 하단 탭의 접근성 패턴, 차트 컨테이너 반응형 원칙만 반영한다.
- 과도한 새 패키지는 추가하지 않는다.

참고 후보:

- Tabler: MIT, responsive dashboard layout/card/table 패턴 참고.
- Chart.js: MIT, responsive chart container 개념 참고. 현재는 의존성 추가 없이 기존 SVG/CSS 차트를 유지한다.
- Bootstrap examples/admin patterns: MIT, spacing/accessibility 구조 참고. 의존성 추가 없음.

## 6. 위험 요소

- `docs/assets/app.js`, `mobile.js`의 DOM id와 HTML id가 어긋나면 화면이 비어 보일 수 있다.
- `dashboard_views.json` 필드 구조와 렌더러 기대값이 어긋나면 랭킹/프로필이 깨질 수 있다.
- 모바일에서 과한 장식 배경이 성능/가독성을 떨어뜨릴 수 있다.
- OCR을 기본 활성화하면 API 키 없는 환경에서 운영 refresh가 실패할 수 있으므로 기본은 비활성화해야 한다.
- `docs/data/*.json`은 생성 산출물이지만 실제 공개 화면 입력이므로 rebuild 후 변경량이 커질 수 있다.

## 7. 테스트 계획

필수:

```powershell
python -m pytest -q
python -m swimdash rebuild
python -m swimdash refresh --skip-ocr
```

가능하면:

```powershell
python -m swimdash serve --port 8766
```

브라우저 확인:

- 데스크톱: `http://127.0.0.1:8766/index.html?desktop=1`
- 모바일: `http://127.0.0.1:8766/mobile.html`
- 프로필: `http://127.0.0.1:8766/profile.html`
- 파싱 상태: `http://127.0.0.1:8766/parse-status.html`

## 8. 롤백 방법

### UI만 롤백

- 변경 전 브랜치 또는 Git diff에서 아래 파일만 되돌린다.
  - `docs/index.html`
  - `docs/mobile.html`
  - `docs/profile.html`
  - `docs/assets/styles.css`
  - `docs/assets/mobile.css`
  - `docs/assets/profile.css`
  - 필요 시 `docs/assets/app.js`, `docs/assets/mobile.js`, `docs/assets/profile.js`

### OCR 비활성 롤백

- 환경변수를 비활성 상태로 둔다.

```powershell
$env:SWIMDASH_ENABLE_GEMINI_OCR = "0"
python -m swimdash refresh --skip-ocr
```

### 도메인 롤백

- Synology reverse proxy에서 `swim.h19h19.com` 규칙을 비활성화한다.
- 기존 `http://swimmingdiary.duckdns.org:8766/` 또는 NAS IP:8766 접근을 유지한다.
- Docker/compose의 내부 포트 `8766`은 그대로 유지한다.

## 9. 완료 보고 항목

- 변경 파일/새 파일 목록.
- UI 반영 내용.
- 모바일 반응형 처리.
- `swim.h19h19.com` 반영 내용.
- OCR/파싱 내용.
- 테스트 결과.
- 남은 TODO.
- 롤백 방법.
