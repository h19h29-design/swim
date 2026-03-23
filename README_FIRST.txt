[가장 쉬운 시작 방법]

1) 이 파일들을 프로젝트 폴더(D:\gpt\01project\swimming-diary-dashboard)에 넣는다.
2) START_HERE.bat 를 더블클릭한다.
3) 끝나면 브라우저에서 아래 주소를 연다.
   http://127.0.0.1:8765/

무엇이 자동으로 되나
- 가상환경 찾기 또는 생성
- requirements 설치
- 크롤링 명령 자동 탐지 시도
- 데이터 rebuild
- 대시보드 서버 시작
- 작업 스케줄러 등록(하루 4번)

현재 기본 정책
- 테스트 기간: 2026-03-01부터 현재까지 전체 재수집(march_pilot)
- 테스트 종료 후: switch_to_rolling_3d.ps1 1회 실행 -> 최근 3일 재수집
- 수동 review는 사용하지 않음

주의
- crawl_command 자동 탐지에 실패하면 rebuild만 진행될 수 있다.
- 그 경우 logs\pilot_cycle_*.log 를 확인하고 pilot_config.json 의 crawl_command 를 한 줄만 채우면 된다.
