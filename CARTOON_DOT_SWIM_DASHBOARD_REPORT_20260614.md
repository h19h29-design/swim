# Cartoon Dot Swim Dashboard 작업 보고서

작성일: 2026-06-14
브랜치: feature/cartoon-dot-swim-dashboard-domain-ocr
대상 레포: https://github.com/h19h29-design/swim
기준 시안: C:\Users\user\Downloads\ChatGPT Image 2026년 6월 14일 오전 10_20_04.png
신규 공개 도메인 기준: https://swim.h19h19.com/
롤백 주소: http://swimmingdiary.duckdns.org:8766/

## 1. 변경 요약

- 첨부 시안의 블루/화이트, 물결, 버블, 도트/하프톤, 귀여운 수영 캐릭터, 둥근 카드, 게임형 배지 느낌을 데스크톱/모바일/프로필/배지 갤러리 CSS에 반영했습니다.
- 기존 DCInside 수집, 제목 파싱, records/dashboard_views/review_queue/parse_status, 시즌 랭킹, 개인 프로필, 배지, 관리자 흐름은 유지했습니다.
- Gemini OCR은 최종 확정이 아니라 후보 추출로 유지하고, 자동 후보 우선순위를 `일치 > 제목 > 본문 > 고신뢰 OCR > review_queue`로 보강했습니다.
- `swim.h19h19.com` 기준 NAS reverse proxy 문서와 롤백 체크리스트를 추가했습니다.
- API 키는 코드/문서에 넣지 않았고 `.env.example`에는 빈 값과 비활성 기본값만 추가했습니다.

## 2. 새 파일

```text
D:\gpt\01project\swimming-diary-dashboard\docs\UI_REDESIGN_PLAN.md
D:\gpt\01project\swimming-diary-dashboard\docs\DOMAIN_CUTOVER_ROLLBACK.md
D:\gpt\01project\swimming-diary-dashboard\CARTOON_DOT_SWIM_DASHBOARD_REPORT_20260614.md
```

## 3. 주요 수정 파일

```text
D:\gpt\01project\swimming-diary-dashboard\docs\assets\styles.css
D:\gpt\01project\swimming-diary-dashboard\docs\assets\mobile.css
D:\gpt\01project\swimming-diary-dashboard\docs\assets\profile.css
D:\gpt\01project\swimming-diary-dashboard\docs\assets\badge-gallery.css
D:\gpt\01project\swimming-diary-dashboard\swimdash\record_resolver.py
D:\gpt\01project\swimming-diary-dashboard\swimdash\ocr_gemini.py
D:\gpt\01project\swimming-diary-dashboard\swimdash\pipeline.py
D:\gpt\01project\swimming-diary-dashboard\tests\test_record_resolver.py
D:\gpt\01project\swimming-diary-dashboard\tests\test_pipeline_aggregate.py
D:\gpt\01project\swimming-diary-dashboard\README.md
D:\gpt\01project\swimming-diary-dashboard\docs\NAS_DEPLOY.md
D:\gpt\01project\swimming-diary-dashboard\NAS_BOT_PROMPT.txt
D:\gpt\01project\swimming-diary-dashboard\.env.example
D:\gpt\01project\swimming-diary-dashboard\requirements.txt
```

주의: 작업 시작 시점부터 작업트리에는 이전 UI/OCR/시즌2 변경 파일이 다수 존재했습니다. 이번 보고서는 이번 턴에서 확인/보강한 핵심 변경을 중심으로 정리합니다.

## 4. UI 반영 내용

### 데스크톱

- 좌측 사이드바를 시안처럼 진한 블루 수영장 패널로 변경했습니다.
- 브랜드 영역에 CSS 기반 귀여운 수영 캐릭터 느낌의 마크를 추가했습니다.
- KPI 카드에 도트 배경, 둥근 테두리, 두꺼운 그림자, 원형 아이콘 배지를 적용했습니다.
- 시즌 Hero 카드는 물결/하프톤/버블/캐릭터/진행바 느낌으로 강화했습니다.
- 차트 카드, 랭킹 TOP10, 최근 기록, 검토/OCR 상태, 최근 배지 카드의 컨테이너를 스티커형 카드 스타일로 정리했습니다.
- 긴 한국어 텍스트가 좁은 칸에서 세로로 깨지는 문제를 말줄임 처리로 보정했습니다.

### 모바일

- 기존 `mobile.html` 별도 화면과 하단 탭 구조를 유지했습니다.
- Hero 카드에 캐릭터, 물결, 도트, 진행바 스타일을 적용했습니다.
- KPI, 기록 분석, 주간 차트, 최근 기록, 검토 대기, 최근 배지 카드가 좁은 화면에서 카드형으로 유지되게 조정했습니다.
- 하단 탭은 둥근 floating tab bar 형태로 강화했습니다.

### 프로필/배지

- `profile.css`를 블루 카툰/도트 계열로 맞춰 메인 대시보드와 톤을 맞췄습니다.
- `badge-gallery.css`도 배지 스티커북 느낌을 유지하면서 수영장 블루 테마로 맞췄습니다.

## 5. 모바일 반응형 처리

- `index.html`의 기존 모바일 리다이렉트는 유지했습니다.
- 모바일 전용 `mobile.html`은 기존 DOM id와 `data-tab-target` 계약을 유지했습니다.
- 작은 화면에서는 KPI 2열 또는 1열, 카드 단위 스택, 하단 탭 고정 방식이 유지됩니다.
- Playwright local Chrome으로 `390x844` viewport를 확인했습니다.

## 6. 도메인 반영 내용

- 신규 도메인 기준은 `https://swim.h19h19.com/` 입니다.
- `docs/NAS_DEPLOY.md`에 Synology Reverse Proxy 설정을 추가했습니다.
- `docs/DOMAIN_CUTOVER_ROLLBACK.md`에 DNS/reverse proxy/컨테이너/관리자/롤백 확인 매트릭스를 추가했습니다.
- `README.md`에 신규 도메인과 기존 duckdns/8766 롤백 주소를 명시했습니다.
- Docker 내부 포트 `8766`, `compose.yaml`, `Dockerfile`의 기본 포트 구조는 바꾸지 않았습니다.

## 7. OCR/파싱 내용

### 최종 우선순위

```text
manual override
> title/body/ocr agreement
> title
> body
> high-confidence OCR
> review_queue
```

### 구현 내용

- `swimdash/record_resolver.py`에서 후보 간 충돌이 있어도 제목이 완전하면 제목을 우선 반영하고 `CANDIDATE_CONFLICT` 경고를 남기도록 변경했습니다.
- 제목/본문/OCR 중 2개 이상이 같은 후보를 내면 `resolved_source="mixed"`로 기록합니다.
- 제목이 없으면 본문 후보를 우선하고, 본문도 없을 때만 고신뢰 OCR 후보를 사용합니다.
- OCR 후보는 범위와 confidence를 통과해야 하며, 그렇지 않으면 review queue로 갑니다.
- `swimdash/pipeline.py`가 `.env`까지 포함한 Gemini OCR 설정을 읽도록 바꿨습니다.
- `swimdash/ocr_gemini.py`는 `google-genai` SDK, 구조화 JSON schema, 기본 모델 `gemini-2.5-flash-lite`, fallback `gemini-2.5-flash` 기준으로 정리했습니다.
- `data/ocr_cache`는 `.gitignore`에 유지되어 캐시가 Git에 들어가지 않습니다.

### API 키 안전성

- 실제 API 키는 추가하지 않았습니다.
- `.env.example`에는 빈 `GEMINI_API_KEY=`만 추가했습니다.
- 기본값은 `SWIMDASH_ENABLE_GEMINI_OCR=0`입니다.
- `python -m swimdash refresh --skip-ocr`가 성공했습니다.

## 8. 테스트 결과

실행한 테스트:

```powershell
python -m pytest tests/test_record_resolver.py tests/test_body_parser.py tests/test_ocr_gemini_mock.py tests/test_ocr_cache.py tests/test_parser.py tests/test_pipeline_aggregate.py tests/test_runtime_cli.py -q
```

결과:

```text
49 passed in 0.33s
```

전체 테스트:

```powershell
python -m pytest -q
```

결과:

```text
68 passed, 1 warning in 3.22s
```

rebuild:

```powershell
python -m swimdash rebuild
```

결과:

```text
rebuild done records=155
```

refresh without OCR:

```powershell
python -m swimdash refresh --skip-ocr
```

결과:

```text
crawl done mode=incremental pages=2 diary_rows=26 fetched=26 errors=0 total_records=181
rebuild done records=181
```

## 9. 브라우저 검증

Browser/IAB 캡처 도구가 현재 클릭 도구만 노출되어 있어서 Playwright fallback을 사용했습니다.
Playwright 기본 브라우저 바이너리가 없어 로컬 Chrome 실행 파일을 지정해 캡처했습니다.

사용한 Chrome:

```text
C:\Program Files\Google\Chrome\Application\chrome.exe
```

확인 URL:

```text
http://127.0.0.1:8766/index.html?desktop=1&v=20260614
http://127.0.0.1:8766/mobile.html?v=20260614
http://127.0.0.1:8766/profile.html?v=20260614
http://127.0.0.1:8766/badge-gallery.html?v=20260614
http://127.0.0.1:8766/parse-status.html?v=20260614
```

스크린샷:

```text
D:\gpt\01project\swimming-diary-dashboard\swim-dashboard-desktop-cartoon-20260614b.png
D:\gpt\01project\swimming-diary-dashboard\swim-dashboard-mobile-cartoon-20260614.png
D:\gpt\01project\swimming-diary-dashboard\swim-dashboard-profile-mobile-cartoon-20260614.png
```

콘솔 확인:

- 데스크톱: 200, console error 없음
- 모바일: 200, console error 없음
- 배지 갤러리: 200, console error 없음
- 파싱 상태: 200, console error 없음
- 프로필: 재확인 시 404 리소스 재현 없음, 화면 정상 렌더링

## 10. 시안 대비 확인 사항

비교 기준:

```text
C:\Users\user\Downloads\ChatGPT Image 2026년 6월 14일 오전 10_20_04.png
```

확인한 포인트:

- 블루/화이트 기반 수영장 톤: 반영
- 도트/하프톤 배경: 반영
- 물결/버블 장식: 반영
- 귀여운 수영 캐릭터 느낌: CSS 기반 캐릭터 마크로 반영
- 좌측 사이드바: 반영
- 상단 검색/새로고침/관리자: 유지 및 스타일 반영
- KPI 카드: 둥근 게임형 카드로 반영
- 시즌 진행 Hero 카드: 반영
- 랭킹 TOP10: 유지 및 카드 스타일 반영
- 최근 기록/OCR 검토 상태: 유지 및 카드 스타일 반영
- 모바일 하단 탭: 반영

남은 차이:

- 첨부 시안의 고품질 캐릭터 일러스트와 배경 파도는 실제 raster asset이 아니라 CSS/SVG 기반으로 근사했습니다.
- 현재 대시보드 데이터의 실제 칭호/닉네임/기록 값이 시안의 예시 값과 다릅니다.
- 완전한 픽셀 단위 일치를 목표로 하려면 별도 캐릭터/파도 일러스트 에셋 제작이 필요합니다.

## 11. 참고한 오픈소스/패턴

코드는 직접 복사하지 않고 패턴만 참고했습니다.

- Tabler dashboard 패턴: https://github.com/tabler/tabler
- Chart.js responsive chart container 개념: https://github.com/chartjs/Chart.js
- Google GenAI Python SDK 패키지 방향: https://github.com/googleapis/python-genai

의존성 추가는 `google-genai`만 명시했습니다. 차트/UI 패키지는 추가하지 않았습니다.

## 12. 남은 TODO

- 실제 `swim.h19h19.com` DNS/SSL/Synology Reverse Proxy는 NAS에서 설정해야 합니다.
- 운영 배포 전 NAS에서 관리자 로그인/저장/rebuild를 실제로 한 번 확인해야 합니다.
- Gemini OCR을 실제로 켤 경우 NAS `.env`에만 API 키를 넣고, 소량 이미지로 먼저 검증해야 합니다.
- 현재 CSS 캐릭터는 코드 기반 근사입니다. 시안 수준의 캐릭터 완성도를 원하면 별도 PNG/SVG 에셋 제작이 좋습니다.
- 작업 시작 전부터 있던 기존 변경들이 많으므로 PR 전에는 변경 파일 범위를 한 번 더 나눠 리뷰하는 것을 권장합니다.

## 13. 롤백 방법

### UI 롤백

아래 파일을 이전 버전으로 되돌리면 UI만 롤백할 수 있습니다.

```text
docs/index.html
docs/mobile.html
docs/profile.html
docs/assets/styles.css
docs/assets/mobile.css
docs/assets/profile.css
docs/assets/badge-gallery.css
docs/assets/app.js
docs/assets/mobile.js
docs/assets/profile.js
```

### OCR 비활성 롤백

```powershell
$env:SWIMDASH_ENABLE_GEMINI_OCR = "0"
python -m swimdash refresh --skip-ocr
python -m swimdash rebuild
```

### 도메인 롤백

- Synology Reverse Proxy에서 `swim.h19h19.com` 규칙을 비활성화합니다.
- 기존 주소를 사용합니다.

```text
http://swimmingdiary.duckdns.org:8766/
http://swimmingdiary.duckdns.org:8766/admin.html
```

- Docker 내부 포트 `8766`은 바꾸지 않습니다.

## 14. 다운로드 폴더 복사본

```text
C:\Users\user\Downloads\CARTOON_DOT_SWIM_DASHBOARD_REPORT_20260614.md
C:\Users\user\Downloads\UI_REDESIGN_PLAN_20260614.md
C:\Users\user\Downloads\DOMAIN_CUTOVER_ROLLBACK_20260614.md
```
