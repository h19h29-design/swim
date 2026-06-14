# swim.h19h19.com 도메인 전환 및 롤백 체크리스트

작성일: 2026-06-14
대상 서비스: swimming-diary-dashboard / swimdash-app
신규 도메인: https://swim.h19h19.com/
롤백 주소: http://swimmingdiary.duckdns.org:8766/

## 1. 절대 바꾸지 않는 것

- Docker 내부 포트 `8766`
- `compose.yaml`의 기본 포트 구조 `${SWIMDASH_PUBLIC_PORT:-8766}:8766`
- 컨테이너 이름 `swimdash-app`
- DSM 스케줄 명령 `docker exec swimdash-app python -m swimdash refresh`
- DCInside 수집 원천 `https://gall.dcinside.com`
- 기존 duckdns/8766 접근 경로

## 2. 신규 도메인 구성

Synology Reverse Proxy 권장값:

```text
Source protocol: HTTPS
Source hostname: swim.h19h19.com
Source port: 443
Destination protocol: HTTP
Destination hostname: 127.0.0.1 또는 NAS 내부 IP
Destination port: 8766
```

DNS:

```text
swim.h19h19.com -> NAS 공인 IP 또는 사용 중인 프록시 대상
```

`.env` 권장값:

```text
SWIMDASH_PUBLIC_PORT=8766
SWIMDASH_SECURE_COOKIES=1
TZ=Asia/Seoul
```

관리자 필수값:

```text
SWIMDASH_ADMIN_PASSWORD=...
SWIMDASH_ADMIN_SESSION_SECRET=...
```

OCR은 기본 비활성입니다.

```text
SWIMDASH_ENABLE_GEMINI_OCR=0
```

OCR 후보를 켤 때만 NAS 환경 변수에 실제 키를 넣습니다. Git, README, docs/data에는 절대 넣지 않습니다.

```text
SWIMDASH_ENABLE_GEMINI_OCR=1
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash-lite
GEMINI_FALLBACK_MODEL=gemini-2.5-flash
```

## 3. 전환 전 확인

```bash
docker compose ps
docker logs swimdash-app --tail 200
curl -I http://127.0.0.1:8766/
docker exec swimdash-app python -m swimdash refresh --skip-ocr
```

브라우저 확인:

```text
http://swimmingdiary.duckdns.org:8766/?desktop=1
http://swimmingdiary.duckdns.org:8766/mobile.html
http://swimmingdiary.duckdns.org:8766/profile.html
http://swimmingdiary.duckdns.org:8766/badge-gallery.html
http://swimmingdiary.duckdns.org:8766/parse-status.html
http://swimmingdiary.duckdns.org:8766/admin-login.html
```

## 4. 전환 후 확인

```text
https://swim.h19h19.com/?desktop=1
https://swim.h19h19.com/mobile.html
https://swim.h19h19.com/profile.html
https://swim.h19h19.com/badge-gallery.html
https://swim.h19h19.com/parse-status.html
https://swim.h19h19.com/admin-login.html
```

관리자 확인:

1. `https://swim.h19h19.com/admin-login.html` 로그인
2. `/admin.html` 진입
3. 설정 bundle 로딩 확인
4. 저장 또는 rebuild 실행 확인
5. 저장 후 `docs/data/*.json` 갱신 확인

## 5. 문제 분리

### 컨테이너 자체 문제

증상:
- `curl http://127.0.0.1:8766/` 실패
- `docker compose ps`에서 컨테이너 비정상

확인:

```bash
docker compose ps
docker logs swimdash-app --tail 200
docker compose up -d --build
```

### Reverse Proxy/DNS 문제

증상:
- `http://127.0.0.1:8766/` 정상
- `https://swim.h19h19.com/` 실패

조치:
- DNS A/CNAME 확인
- Synology Reverse Proxy 목적지 `127.0.0.1:8766` 확인
- SSL 인증서 연결 확인
- Host 헤더 보존 확인

### 관리자 로그인/저장 문제

증상:
- 페이지는 열리지만 admin 저장 실패

확인:
- `SWIMDASH_ADMIN_PASSWORD`
- `SWIMDASH_ADMIN_SESSION_SECRET`
- `SWIMDASH_SECURE_COOKIES=1`
- reverse proxy의 `X-Forwarded-Proto: https`
- 브라우저 Origin과 Host가 `swim.h19h19.com`으로 일치하는지

## 6. 롤백

새 도메인만 문제가 있으면 앱 컨테이너를 내리지 않습니다.

1. Synology Reverse Proxy에서 `swim.h19h19.com` 규칙 비활성화 또는 이전 설정 복구
2. 기존 주소로 접속 확인

```text
http://swimmingdiary.duckdns.org:8766/
http://swimmingdiary.duckdns.org:8766/admin.html
```

3. 필요하면 `.env`를 기존 plain HTTP 기준으로 복구

```text
SWIMDASH_PUBLIC_PORT=8766
SWIMDASH_SECURE_COOKIES=0
SWIMDASH_ENABLE_GEMINI_OCR=0
```

4. 컨테이너 재시작

```bash
docker compose up -d
```

5. 데이터 안전 확인

```bash
docker exec swimdash-app python -m swimdash refresh --skip-ocr
docker exec swimdash-app python -m swimdash rebuild
```

## 7. 최종 확인 매트릭스

| 경로 | 신규 도메인 | 롤백 주소 |
|---|---|---|
| 데스크톱 | `https://swim.h19h19.com/?desktop=1` | `http://swimmingdiary.duckdns.org:8766/?desktop=1` |
| 모바일 | `https://swim.h19h19.com/mobile.html` | `http://swimmingdiary.duckdns.org:8766/mobile.html` |
| 프로필 | `https://swim.h19h19.com/profile.html` | `http://swimmingdiary.duckdns.org:8766/profile.html` |
| 배지 | `https://swim.h19h19.com/badge-gallery.html` | `http://swimmingdiary.duckdns.org:8766/badge-gallery.html` |
| 파싱 상태 | `https://swim.h19h19.com/parse-status.html` | `http://swimmingdiary.duckdns.org:8766/parse-status.html` |
| 관리자 로그인 | `https://swim.h19h19.com/admin-login.html` | `http://swimmingdiary.duckdns.org:8766/admin-login.html` |
