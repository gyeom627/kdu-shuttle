"""Flask 앱의 /reserve 라우트를 실제로 두 스레드에서 동시에 호출하는 테스트.
서버를 별도로 띄울 필요가 없다.
"""
import os
import concurrent.futures
import threading
from datetime import date, timedelta

os.environ['SHUTTLE_DB'] = 'test_shuttle.db'
os.environ['SHUTTLE_TEST_MODE'] = '1'

from app import app

SCHEDULE_ID = 1

def next_saturday(from_date=None):
    today = from_date or date.today()
    days = (5 - today.weekday()) % 7
    return today + timedelta(days=days)

RIDE_DATE = next_saturday().isoformat()
BARRIER = threading.Barrier(2)


def reserve(student_id):
    client = app.test_client()

    with client.session_transaction() as sess:
        sess['student_id'] = student_id
        sess['name'] = f'테스트 {student_id}'

    BARRIER.wait()
    response = client.post(
        '/reserve',
        json={'schedule_id': SCHEDULE_ID, 'ride_date': RIDE_DATE}
    )

    return student_id, response.status_code, response.get_json()


def main():
    print(f'테스트 날짜: {RIDE_DATE} (토요일)')
    print('정원: 1명')
    print('두 사용자가 동시에 /reserve 요청을 시작합니다.\n')

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(reserve, 'TEST001'), executor.submit(reserve, 'TEST002')]
        results = [future.result() for future in futures]

    for result in results:
        print(result)

    success = sum(status == 201 for _, status, _ in results)
    conflict = sum(status == 409 for _, status, _ in results)

    print('\n===== 결과 =====')
    print('201 성공:', success)
    print('409 충돌/마감:', conflict)

    if success == 1 and conflict == 1:
        print('PASS: 오버부킹이 발생하지 않았습니다. 정확히 1명만 예약되었습니다.')
    else:
        print('FAIL: 예상 결과(201 1개 + 409 1개)가 아닙니다.')
        raise SystemExit(1)


if __name__ == '__main__':
    main()
