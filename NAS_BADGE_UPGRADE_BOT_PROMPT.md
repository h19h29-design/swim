# SwimDash NAS Bot 지시서

목표:
- 기존 데이터, 집계 결과, 파싱 로직, 스케줄 정책은 건드리지 않는다.
- 배지 모양만 업그레이드 개념으로 바꾼다.
- 기존 badge/category/tier 데이터를 그대로 사용하고, 프론트에서만 단계별 SVG 배지로 렌더한다.
- 메인, 모바일, 프로필, 배지 갤러리에서 앞으로 같은 규칙으로 보이게 적용한다.

이번 작업에서 절대 수정하지 말 것:
- `swimdash/cli.py`
- `swimdash/admin_api.py`
- `data/**`
- `docs/data/**`
- cron, DSM Task Scheduler, `/etc/crontab`, wrapper shell
- 파싱/집계/관리자 동작 의미

이번 변경 파일만 배포 대상:
- `docs/assets/dashboard-common.js`
- `docs/assets/app.js`
- `docs/assets/mobile.js`
- `docs/assets/profile.js`
- `docs/assets/badge-gallery.js`
- `docs/index.html`
- `docs/mobile.html`
- `docs/profile.html`
- `docs/badge-gallery.html`
- `docs/badge-evolution.html`
- `docs/badge-stage-system.html`

변경 내용 요약:
- `dashboard-common.js`
  - `renderBadgeIcon()`이 badge 객체의 `badge_id/category/tier/icon_key`를 받아 단계형 SVG 배지를 렌더한다.
  - badge 객체 메타데이터가 없을 때만 기존 정적 아이콘 asset을 그대로 사용한다.
- `app.js`, `mobile.js`, `profile.js`, `badge-gallery.js`
  - 기존 `icon_key` 문자열만 넘기던 호출을 badge 객체 전체 전달로 바꿨다.
  - 기존 데이터 구조는 그대로 쓰고, 시각 표현만 바뀐다.
- HTML
  - `?v=20260323a`로 스크립트 버전을 올려 브라우저 캐시를 무효화했다.
- 참고 페이지
  - `badge-stage-system.html`: 단계별 배지 진화 시안
  - `badge-evolution.html`: 위 페이지로 연결되는 별칭 주소

권장 적용 방법:
1. 저장소 루트로 이동한다.
2. `git fetch origin`
3. `git checkout main`
4. `git pull --ff-only origin main`
5. `docker compose up -d --build swimdash`
6. `docker ps --filter name=swimdash-app`
7. 아래 URL들을 확인한다.

검증 URL:
- `http://swimmingdiary.duckdns.org:8766/`
- `http://swimmingdiary.duckdns.org:8766/mobile.html`
- `http://swimmingdiary.duckdns.org:8766/profile.html?author=NTHNG`
- `http://swimmingdiary.duckdns.org:8766/badge-gallery.html`
- `http://swimmingdiary.duckdns.org:8766/badge-evolution.html`

검증 포인트:
- 메인:
  - 갤 대표 칭호, 상위 랭킹 카드, 최근 해금 배지가 기존 파일 아이콘이 아니라 단계형 SVG 배지로 보여야 한다.
- 모바일:
  - 상단 랭킹 카드 배지가 단계형 SVG로 보여야 한다.
- 프로필:
  - 대표 칭호, 다음 해금, 최근 해금 배지가 단계형 SVG로 보여야 한다.
- 배지 갤러리:
  - `아이콘 가족`과 `공용 리소스`는 기존 asset 미리보기여야 한다.
  - 실제 `카테고리별 배지 카드`는 단계형 SVG 배지로 보여야 한다.

긴급 대안:
- 정식 rebuild가 어려우면 아래 파일만 running container의 `/app/docs/`에 덮어쓴다.
- 그 뒤 `docker restart swimdash-app`까지 수행한다.

긴급 동기화 대상:
- `/app/docs/assets/dashboard-common.js`
- `/app/docs/assets/app.js`
- `/app/docs/assets/mobile.js`
- `/app/docs/assets/profile.js`
- `/app/docs/assets/badge-gallery.js`
- `/app/docs/index.html`
- `/app/docs/mobile.html`
- `/app/docs/profile.html`
- `/app/docs/badge-gallery.html`
- `/app/docs/badge-evolution.html`
- `/app/docs/badge-stage-system.html`

긴급 동기화 예시:
```bash
docker cp docs/assets/dashboard-common.js swimdash-app:/app/docs/assets/dashboard-common.js
docker cp docs/assets/app.js swimdash-app:/app/docs/assets/app.js
docker cp docs/assets/mobile.js swimdash-app:/app/docs/assets/mobile.js
docker cp docs/assets/profile.js swimdash-app:/app/docs/assets/profile.js
docker cp docs/assets/badge-gallery.js swimdash-app:/app/docs/assets/badge-gallery.js
docker cp docs/index.html swimdash-app:/app/docs/index.html
docker cp docs/mobile.html swimdash-app:/app/docs/mobile.html
docker cp docs/profile.html swimdash-app:/app/docs/profile.html
docker cp docs/badge-gallery.html swimdash-app:/app/docs/badge-gallery.html
docker cp docs/badge-evolution.html swimdash-app:/app/docs/badge-evolution.html
docker cp docs/badge-stage-system.html swimdash-app:/app/docs/badge-stage-system.html
docker restart swimdash-app
```

주의:
- 이번 배포는 프론트 배지 모양 변경만 포함한다.
- 기존 집계 수치, 해금 상태, 파싱 결과, 스케줄 정책은 절대 재해석하지 않는다.
- 브라우저에 예전 모양이 남아 있으면 강력 새로고침을 먼저 시도한다.
