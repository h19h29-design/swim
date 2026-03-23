# swimming-diary-dashboard

DCInside `swimmingdiary` 글을 크롤링해 수영 대시보드를 만드는 프로젝트입니다.

## 공식 게시글 제목 양식
대시보드의 공식 입력 경로는 게시글 **제목**입니다.

공식 표준:

```text
1500 / 42:30
```

호환 입력 예시:

```text
1500 / 42:30
1500m / 42:30
1500 / 42분 30초
1500 / 1시간 05분
1500m / 55분
```

규칙:
- 앞 숫자 = 거리
- 뒤 숫자 = 시간
- 거리는 항상 `m` 기준입니다
- `km` 단위는 허용하지 않습니다
- 페이스(`2:05/100m`)는 총시간으로 해석하지 않습니다
- 시작~종료 시각(`09:10~10:05`)은 총시간으로 해석하지 않습니다
- 숫자가 여러 개 섞여 모호하면 추측하지 않고 review queue로 보냅니다

## 포함 정책
자동 포함은 아래 1가지뿐입니다.

1. 게시글 제목이 공식 `거리 / 시간` 양식으로 완전히 파싱되는 경우

그 외에는 review queue로 보냅니다.

주요 사유 코드:
- `TITLE_FORMAT_MISSING`
- `TITLE_FORMAT_INVALID`

## 수정 반영 정책
- 대시보드 집계 시작일은 `2026-03-01`
- `2026-03-15`까지는 `2026-03-01` 이후 글을 수정하면 다시 수집 대상으로 봅니다
- `2026-03-16`부터는 최근 3일 글만 수정 반영 대상으로 봅니다
- routine sync는 전체 크롤링이 아니라 현재 editable window만 다시 가져옵니다

## 로컬 실행
```powershell
python -m pip install -r requirements.txt
python -m pytest -q
python -m swimdash incremental --lookback-days 3 --recent-pages 20 --rate-limit 0.55 --timeout 20
python -m swimdash rebuild
python -m swimdash serve --port 8766
```

공식 refresh 명령:

```powershell
python -m swimdash refresh
```

이 명령은 아래 순서로 동작합니다.
1. incremental sync
2. rebuild

유용한 변형:

```powershell
python -m swimdash refresh --skip-incremental
python -m swimdash refresh-from-floor
python -m swimdash refresh-from-floor --skip-incremental
python -m swimdash refresh-window --start-date 2026-03-01 --end-date 2026-03-17
```

`refresh-from-floor` 는 대시보드 집계 시작일인 `2026-03-01` 부터 오늘까지를 다시 확인하는 전용 경로입니다.
운영상 최근 3일 정책과 별개로, 3월 1일 이후 전체 보정이 필요할 때 이 명령을 스케줄러나 수동 작업에서 사용할 수 있습니다.
`refresh-window` 는 지정한 날짜 범위만 다시 읽고, 그 범위 안의 기존 레코드만 최신 수집 결과로 교체한 뒤 바깥 날짜 누적 기록과 다시 합칩니다.

## pilot operations
일상적인 로컬 작업은 아래 순서를 권장합니다.

1. 데이터 갱신:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\pilot_rebuild.ps1
```

3월 1일부터 다시 확인하는 보정 갱신:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\pilot_rebuild.ps1 -FromDashboardFloor
```

기간 지정 재수집:
```powershell
python -m swimdash refresh-window --start-date 2026-03-10 --end-date 2026-03-17
```

2. 로컬 서버 시작:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\pilot_start.ps1
```

3. 브라우저에서 열기:
```text
http://localhost:8766
```

4. 외부 테스트 링크가 필요하면:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\pilot_share.ps1
```

5. 종료:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\pilot_stop.ps1
```

메모:
- `data/admin/*.json`을 수정한 뒤에는 `pilot_rebuild.ps1` 또는 `python -m swimdash rebuild`를 다시 실행합니다
- `data/manual_review_overrides.csv`를 수정한 뒤에도 rebuild가 필요합니다
- 외부 공유 링크는 Cloudflare Quick Tunnel이라 재시작 시 주소가 바뀔 수 있습니다

## 관리자 페이지
- 관리자 페이지: `/admin.html`
- 로그인 페이지: `/admin-login.html`
- 간단 로그인 방식: 공유 비밀번호 1개
- 실제 저장 대상: `data/admin/*.json`
- 저장 후 공개 데이터(`docs/data/*.json`)는 rebuild로 다시 생성됩니다

필수 환경 변수:
- `SWIMDASH_ADMIN_PASSWORD`
- `SWIMDASH_ADMIN_SESSION_SECRET`

선택 환경 변수:
- `SWIMDASH_ADMIN_SESSION_TTL_SECONDS`
- `SWIMDASH_ADMIN_COOKIE_NAME`

## 관리자 설정 원본
운영자가 직접 수정하는 원본은 아래입니다.

- `data/admin/site_config.json`
- `data/admin/navigation_config.json`
- `data/admin/home_sections.json`
- `data/admin/badge_catalog.json`
- `data/admin/season_badges.json`
- `data/admin/gallery_title_rules.json`
- `data/admin/profile_layout_config.json`
- `data/admin/badge_art_catalog.json`

공개 페이지는 rebuild 후 생성되는 아래 파일을 읽습니다.

- `docs/data/site_config.json`
- `docs/data/dashboard_views.json`
- `docs/data/author_index.json`
- `docs/data/author_profiles.json`
- `docs/data/badge_index.json`
- `docs/data/admin_preview.json`

## Docker / NAS
Docker 런타임과 Synology 배포 방법은 [docs/NAS_DEPLOY.md](./docs/NAS_DEPLOY.md)에 정리되어 있습니다.

핵심:
- 컨테이너 1개로 `docs/`를 그대로 서빙
- 기본 스케줄은 Synology DSM Task Scheduler에서 `10:00`, `22:00`
- 기본 실행 명령은 `docker exec swimdash-app python -m swimdash refresh`
- `refresh-from-floor` 와 `refresh-window` 는 관리자나 DSM에서 필요할 때 수동 실행하는 보정용 명령입니다
