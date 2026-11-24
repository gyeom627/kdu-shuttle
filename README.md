# 경동대 셔틀버스 예약 시스템

경동대학교 무료 셔틀버스(도봉산·양주·의정부 노선)의 시간표 조회와 좌석 예약을 웹으로 처리하는 서비스입니다.
소프트웨어 개발 교과목 1회차 개인 과제 (2221002 고겸, 2026.09).

## 주요 기능
- 노선·방향·요일별 시간표 조회, 좌석 예약과 취소 (출발 10분 전까지 취소)
- 정원 관리, 같은 방향 중복 예약 방지, 노쇼 페널티
- 내일 예약은 전날 18:30에 열림, 2026년 공휴일·방학 기간 예약 차단
- 동시 예약 오버부킹 방지: `BEGIN IMMEDIATE` 쓰기 잠금 + 트랜잭션 안에서 정원 재검증

## 기술 스택
Python · Flask · SQLite · Jinja2 · JavaScript(Fetch API)

## 실행 방법
```bash
pip install -r requirements.txt
python setup_db.py        # shuttle.db 생성 + 시간표·테스트 사용자 데이터
python app.py             # http://127.0.0.1:5000
```
로그인은 학번만 입력합니다 (테스트 학번: 20260001).

동시성 테스트:
```bash
python init_test_db.py            # 정원 1명짜리 테스트 배차가 있는 test_shuttle.db
python test_concurrency_local.py  # 2명이 동시에 예약 → 1명 201, 1명 409
```
