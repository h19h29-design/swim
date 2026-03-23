# Swimming Diary Dashboard - Latest Project Context

## 목적
DCInside 수영일기 갤러리 게시글을 수집하고, 게시글 텍스트와 이미지 OCR을 이용해 수영 기록 대시보드를 자동 생성한다.

## 현재 구현 상태
- 크롤링/리빌드/서버 파이프라인 존재
- 결과 스키마는 백엔드 단일 결정
- include/exclude/review_needed 는 백엔드가 결정하고 프론트는 그대로 표시
- strict format-first 파서 적용 완료
- legacy text 파서와 text+image field merge 적용 완료
- OCR fallback 은 상세화면 템플릿만 고신뢰로 취급
- manual override 워크플로는 구현되어 있지만 현재 운영에서는 사용하지 않음

## 현재 운영 정책
### 우선순위
1. 텍스트 양식 파싱
2. 레거시 라벨 기반 텍스트 파싱
3. 이미지 OCR fallback

### canonical format
- 총거리 000
- 시간 1시간10분

### 텍스트 우선 원칙
- 동일 필드에 대해 텍스트가 있으면 이미지보다 텍스트를 우선
- 이미지 OCR 은 필요한 필드가 빠진 경우에만 보조적으로 사용

## 테스트 운영 정책(현재)
- 테스트 기간은 2026-03-01부터 현재까지 전체 재수집
- 하루 4회 자동 실행
- 사람이 review queue 를 수동 처리하지 않음
- 작성자가 3월 게시글을 수정하면 다음 자동 실행 시 재반영되도록 운영

## 테스트 종료 후 운영 정책
- 최근 3일(72시간) 재수집으로 전환
- switch_to_rolling_3d.ps1 실행으로 모드 전환

## 운영 명령
### 첫 설치/실행
- START_HERE.bat
또는
- powershell -ExecutionPolicy Bypass -File .\setup_everything.ps1

### 수동 1회 실행
- powershell -ExecutionPolicy Bypass -File .\run_cycle.ps1

### 서버 시작
- powershell -ExecutionPolicy Bypass -File .\start_server.ps1

### 서버 상태 확인
- powershell -ExecutionPolicy Bypass -File .\check_status.ps1

### 테스트 종료 후 3일 모드 전환
- powershell -ExecutionPolicy Bypass -File .\switch_to_rolling_3d.ps1

## 다음에 Codex가 먼저 읽을 파일
- PROJECT_CONTEXT_LATEST.md
- pilot_config.json
- logs/last_cycle_status.json
- docs/data/summary.json
- docs/data/review_queue.json
