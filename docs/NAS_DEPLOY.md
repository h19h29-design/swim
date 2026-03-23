# Synology NAS Deployment

이 프로젝트는 Synology Container Manager + DSM Task Scheduler 조합으로 운영하는 것을 권장합니다.

## 권장 구조
- 앱 컨테이너 1개: `swimdash-app`
- 정적 사이트 서빙: `python -m swimdash serve --port 8766`
- 주기 갱신: `python -m swimdash refresh`
- 3월 1일부터 다시 확인하는 보정 갱신: `python -m swimdash refresh-from-floor`
- 기간 지정 보정 갱신: `python -m swimdash refresh-window --start-date YYYY-MM-DD --end-date YYYY-MM-DD`
- 스케줄 담당: DSM Task Scheduler
- 영속 경로:
  - `data/`
  - `docs/data/`
  - `logs/`

## 사용 파일
- `compose.yaml`
- `Dockerfile`
- `.env`
- `data/admin/*.json`
- `docs/`

## 1. NAS 폴더 준비
예시 경로:

```text
/volume1/docker/swimdash
```

이 폴더에 리포지토리 전체를 복사합니다.

## 2. `.env` 생성
`.env.example`을 `.env`로 복사한 뒤 아래 값을 채웁니다.

필수:
- `SWIMDASH_ADMIN_PASSWORD`
- `SWIMDASH_ADMIN_SESSION_SECRET`

선택:
- `SWIMDASH_PUBLIC_PORT`
- `SWIMDASH_SECURE_COOKIES`
- `SWIMDASH_ADMIN_SESSION_TTL_SECONDS`
- `TZ`

랜덤 비밀번호/세션 시크릿 생성:

```powershell
D:\gpt\01project\.venv311\Scripts\python.exe .\scripts\generate_runtime_secrets.py
```

출력 예시:
- `SWIMDASH_ADMIN_PASSWORD=...`
- `SWIMDASH_ADMIN_SESSION_SECRET=...`

## 3. 컨테이너 실행
```bash
docker compose up -d --build
```

대시보드:

```text
http://NAS_IP:8766/
```

관리자 페이지:

```text
http://NAS_IP:8766/admin.html
```

관리자 페이지는 로그인 후에만 접근할 수 있습니다.

## 4. 일일 갱신 명령
공식 갱신 명령:

```bash
docker exec swimdash-app python -m swimdash refresh
```

동작:
1. incremental sync
2. rebuild

수동 재생성만 할 때:

```bash
docker exec swimdash-app python -m swimdash refresh --skip-incremental
```

3월 1일부터 다시 확인하는 보정 갱신:

```bash
docker exec swimdash-app python -m swimdash refresh-from-floor
```

위 명령은 대시보드 집계 시작일인 `2026-03-01` 부터 오늘까지를 다시 확인합니다.
기본 `refresh` 는 최근 수정 가능 창 위주로 가볍게 도는 일상 갱신이고, `refresh-from-floor` 는 3월 1일부터 누적 보정을 다시 반영할 때 쓰는 장거리 점검용 명령입니다.

기간을 직접 지정해서 다시 읽고 싶다면:

```bash
docker exec swimdash-app python -m swimdash refresh-window --start-date 2026-03-10 --end-date 2026-03-17
```

`refresh-window` 는 선택한 날짜 범위 안의 기존 레코드만 최신 수집 결과로 교체하고, 그 밖의 누적 기록은 그대로 유지합니다.

`data/admin/*.json` 또는 `data/manual_review_overrides.csv`만 바꿨다면 `refresh --skip-incremental` 또는 `rebuild`만 써도 됩니다.

## 5. DSM Task Scheduler
DSM에서 아래 2개 기본 작업을 만듭니다.

- `swimdash-refresh-1000`
- `swimdash-refresh-2200`

실행 시각:
- `10:00`
- `22:00`

사용자 정의 스크립트:

```sh
docker exec swimdash-app python -m swimdash refresh
```

DSM에서 `docker`를 못 찾으면 먼저 SSH로 경로를 확인합니다.

```sh
which docker
```

필요하면 절대 경로 사용:

```sh
/usr/bin/docker exec swimdash-app python -m swimdash refresh
```

권장 설정:
- 사용자: `root`
- 필요하면 이메일 알림 사용
- 스케줄러가 컨테이너를 재시작하지 않게 하고, 내부 refresh 명령만 실행

수동 보정 권장:
- 3월 1일부터 다시 확인: `docker exec swimdash-app python -m swimdash refresh-from-floor`
- 특정 기간만 다시 확인: `docker exec swimdash-app python -m swimdash refresh-window --start-date YYYY-MM-DD --end-date YYYY-MM-DD`

이 두 명령은 자동 스케줄이 아니라 필요할 때 수동으로 실행하는 보정 도구로 두는 편이 운영상 안전합니다.

## 6. 관리자 설정 저장 흐름
관리자 페이지는 이제 preview/export only가 아니라 실제 저장까지 지원합니다.

운영 흐름:
1. `/admin.html` 로그인
2. 설정 편집
3. 저장 또는 파싱 실행
4. 기본 저장 버튼은 자동으로 rebuild까지 함께 실행
5. `최근 3일 갱신`, `3월 1일부터 재수집`, `기간 지정 재수집`을 관리자 페이지에서 바로 실행 가능
6. 저장만 하고 싶을 때만 `전체 저장만` 사용

실제 저장 대상은 `data/admin/*.json` 입니다.
공개 페이지가 읽는 `docs/data/*.json`은 rebuild 후 갱신됩니다.

## 7. 리버스 프록시 / HTTPS
권장:
1. 컨테이너는 내부 포트 `8766` 유지
2. Synology Reverse Proxy로 HTTPS 공개
3. HTTPS가 앞단에서 종료되면 `.env`에 아래 설정

```text
SWIMDASH_SECURE_COOKIES=1
```

## 8. 업데이트
코드 변경 후:

```bash
docker compose up -d --build
```

그 다음 필요에 따라:

```bash
docker exec swimdash-app python -m swimdash refresh
docker exec swimdash-app python -m swimdash refresh --skip-incremental
```

## 9. 백업
같이 백업할 것:
- `data/admin/`
- `data/manual_review_overrides.csv`
- `docs/data/`
- `logs/`

최소 복구 세트:
- `data/`
- `docs/data/`
