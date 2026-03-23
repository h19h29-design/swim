# TODO_NEXT

## 운영 직전 남은 일
1. Synology NAS에 Docker compose로 올리고 실제 스케줄 10:00 / 22:00 연결
2. 관리자 페이지 저장 후 diff 미리보기 추가
3. 관리자 변경 이력 화면 추가
4. 배지/칭호 수동 override UI 추가
5. 백업/복구 스크립트 정리 (`data/admin`, `docs/data`, `logs`)
6. 갤 공지문을 실제 제목 양식 기준으로 최종 고정

## 현재 완료된 것
- OCR 제품 흐름 제거
- 제목 양식 파서 적용
- March floor / rolling 3-day 수정 반영 정책 적용
- stickerbook + game 구조 대시보드 적용
- 배지/칭호 config 체계 적용
- 관리자 로그인/저장 API 적용
- Synology Docker 배포 자산 추가

## 공식 제목 양식
- 권장 표준: `1500 / 42:30`
- 허용 형식은 5개까지만 유지
- 파서는 모호한 제목을 추측하지 않고 review queue로 보냄
