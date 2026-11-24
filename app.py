from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import os
import sqlite3
from datetime import datetime, timedelta, date

# Flask 애플리케이션 객체를 생성합니다.
app = Flask(__name__)
# 세션을 암호화하기 위한 비밀 키를 설정합니다. 환경 변수에서 가져옵니다.
# [GitHub 공개 시 수정] 고정 기본 키가 공개되지 않도록, 환경변수가 없으면 실행할 때마다 임시 키를 만든다
app.secret_key = os.environ.get('FLASK_SECRET_KEY') or os.urandom(24)

# 사용할 SQLite 데이터베이스 파일의 경로를 설정합니다. 환경 변수에서 가져오거나 기본값을 사용합니다.
DB_PATH = os.environ.get('SHUTTLE_DB', 'shuttle.db')
# 테스트 모드 여부를 확인합니다. '1'이면 True로 설정됩니다.
TEST_MODE = os.environ.get('SHUTTLE_TEST_MODE', '0') == '1'
# 요일 비교를 위해 0부터 6까지의 요일을 한글 문자열로 정의합니다.
WEEKDAYS = ['월', '화', '수', '목', '금', '토', '일']

# ==========================================
# 💡 [추가] 2026년 공휴일 지정 세트
# 2026년의 법정 공휴일 및 대체 공휴일을 정의합니다.
# ==========================================
HOLIDAYS_2026 = {
    date(2026, 1, 1),   # 신정
    date(2026, 2, 16), date(2026, 2, 17), date(2026, 2, 18), # 설날
    date(2026, 3, 1), date(2026, 3, 2), # 삼일절 & 대체공휴일
    date(2026, 5, 5),   # 어린이날
    date(2026, 5, 24), date(2026, 5, 25), # 부처님오신날 & 대체공휴일
    date(2026, 6, 3),   # 전국동시지방선거
    date(2026, 6, 6),   # 현충일
    date(2026, 8, 15), date(2026, 8, 17), # 광복절 & 대체공휴일
    date(2026, 9, 24), date(2026, 9, 25), date(2026, 9, 26), # 추석
    date(2026, 10, 3), date(2026, 10, 5), # 개천절 & 대체공휴일
    date(2026, 10, 9),  # 한글날
    date(2026, 12, 25)  # 기독탄신일
}

def is_no_operation_day(target_date):
    """
    지정된 날짜가 주말, 공휴일 또는 방학인지 확인하여 운행 여부를 판별합니다.
    """
    # 1. 주말 체크 (5: 토요일, 6: 일요일)
    if target_date.weekday() >= 5:
        return True, "주말은 셔틀버스를 운행하지 않습니다."

    # 2. 공휴일 체크 (미리 정의된 HOLIDAYS_2026 집합에 포함되는지 확인)
    if target_date in HOLIDAYS_2026:
        return True, "공휴일은 셔틀버스를 운행하지 않습니다."

    # 3. 방학 기간 체크 (학사일정 기준)
    # 하계 방학 (1학기 종강 6.22 다음날 ~ 2학기 개강 8.31 전날)
    if date(2026, 6, 23) <= target_date <= date(2026, 8, 30):
        return True, "하계 방학 기간에는 셔틀버스를 운행하지 않습니다."
    
    # 동계 방학 (2학기 종강 12.18 다음날 ~ )
    if target_date >= date(2026, 12, 19):
        return True, "동계 방학 기간에는 셔틀버스를 운행하지 않습니다."

    # 위 조건에 모두 해당하지 않으면 평일 운행일입니다.
    return False, ""


def get_db_connection():
    """
    SQLite 데이터베이스에 연결하고 기본 설정을 구성하는 함수입니다.
    """
    # 데이터베이스에 연결하며, 10초의 타임아웃을 설정하여 락 대기 시간을 줍니다.
    conn = sqlite3.connect(DB_PATH, timeout=10)
    # 결과를 사전(dict) 형태로 접근할 수 있도록 row_factory를 설정합니다.
    conn.row_factory = sqlite3.Row
    # 외래 키 제약 조건을 활성화합니다.
    conn.execute('PRAGMA foreign_keys = ON;')
    # 데이터베이스 락 발생 시 최대 10초까지 대기하도록 설정합니다. (동시성 제어 지원)
    conn.execute('PRAGMA busy_timeout = 10000;')
    return conn


def parse_date(value):
    """
    문자열 형태의 날짜('YYYY-MM-DD')를 파이썬의 date 객체로 변환합니다.
    형식이 잘못된 경우 None을 반환합니다.
    """
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def get_booking_open_status(target_date, now):
    """
    예약하려는 날짜와 현재 시간을 비교하여 예약을 허용할지 결정합니다.
    운행 불가 여부, 과거 여부, 예약 오픈 시간 등을 종합적으로 체크합니다.
    """
    # 💡 [추가] 운행 없는 날인지 먼저 검사합니다.
    is_no_op, no_op_msg = is_no_operation_day(target_date)
    if is_no_op:
        # 운행 불가일 경우 예약 차단
        return False, False, no_op_msg

    # 목표 날짜와 오늘 날짜의 차이를 계산합니다.
    days_diff = (target_date - now.date()).days
    # 목표 날짜가 오늘보다 이전인지 확인합니다.
    is_past = days_diff < 0

    if days_diff < 0:
        # 과거 날짜는 무조건 예약 차단
        return False, is_past, '과거 날짜입니다.'

    if days_diff == 0:
        # 오늘 날짜는 운행 시간 전이라면 예약 가능
        return True, False, None

    # 내일 예약은 전날 18:30부터 오픈하도록 제어합니다.
    if days_diff == 1:
        # 오늘 18시 30분을 나타내는 객체 생성
        open_time = now.replace(hour=18, minute=30, second=0, microsecond=0)
        if now >= open_time:
            # 18시 30분이 지났으면 예약 허용
            return True, False, None
        # 아직 시간이 안 되었으면 예약 차단
        return False, False, '내일 버스 예약은 오늘 18시 30분부터 가능합니다.'

    # 테스트 모드가 켜져 있으면 제한 없이 예약 허용
    if TEST_MODE:
        return True, False, None

    # 모레 이후의 날짜는 아직 예약 불가
    return False, False, '현재는 오늘 또는 내일 예약만 가능합니다.'


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    """
    사용자 회원가입 처리를 담당하는 라우트입니다.
    GET 요청 시 폼을 보여주고, POST 요청 시 DB에 회원 정보를 저장합니다.
    """
    if request.method == 'POST':
        # 폼에서 입력받은 학번과 이름의 앞뒤 공백을 제거합니다.
        student_id = (request.form.get('student_id') or '').strip()
        name = (request.form.get('name') or '').strip()

        # 입력값이 누락되었는지 확인합니다.
        if not student_id or not name:
            return render_template('signup.html', error='학번과 이름을 모두 입력해주세요.')

        conn = get_db_connection()
        try:
            # 이미 가입된 학번인지 DB에서 조회합니다.
            existing = conn.execute('SELECT 1 FROM Users WHERE student_id = ?', (student_id,)).fetchone()
            if existing:
                # 중복 학번일 경우 에러 메시지와 함께 폼을 다시 렌더링합니다.
                return render_template('signup.html', error='이미 가입된 학번입니다.')

            # 새로운 사용자 정보를 DB에 삽입합니다.
            conn.execute('INSERT INTO Users (student_id, name) VALUES (?, ?)', (student_id, name))
            conn.commit()
        finally:
            conn.close()

        # 가입 성공 시 로그인 페이지로 이동시킵니다.
        return redirect(url_for('login'))

    # GET 요청 시 회원가입 화면을 보여줍니다.
    return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    사용자 로그인 처리를 담당하는 라우트입니다.
    학번으로 인증하고 세션을 생성합니다.
    """
    if request.method == 'POST':
        student_id = (request.form.get('student_id') or '').strip()

        conn = get_db_connection()
        try:
            # 학번이 DB에 존재하는지 확인합니다.
            user = conn.execute('SELECT * FROM Users WHERE student_id = ?', (student_id,)).fetchone()
        finally:
            conn.close()

        if user:
            # 존재한다면 세션에 학번과 이름을 저장하여 로그인 상태를 유지합니다.
            session['student_id'] = user['student_id']
            session['name'] = user['name']
            # 로그인 완료 후 메인 화면으로 이동합니다.
            return redirect(url_for('index'))

        # 학번이 없으면 에러 메시지를 표시합니다.
        return render_template('login.html', error='등록되지 않은 학번입니다. 회원가입을 먼저 진행해주세요.')

    # GET 요청 시 로그인 화면을 보여줍니다.
    return render_template('login.html')


@app.route('/logout')
def logout():
    """
    사용자 로그아웃 처리를 담당합니다. 세션을 지우고 로그인 화면으로 보냅니다.
    """
    # 현재 세션의 모든 정보를 삭제합니다.
    session.clear()
    return redirect(url_for('login'))


@app.route('/')
def index():
    """
    메인 예약 화면을 렌더링하는 라우트입니다.
    """
    # 로그인하지 않은 사용자는 로그인 화면으로 튕겨냅니다.
    if 'student_id' not in session:
        return redirect(url_for('login'))
    # 로그인된 사용자에게 이름과 학번 정보를 넘겨주며 메인 화면을 보여줍니다.
    return render_template('index.html', name=session['name'], student_id=session['student_id'])


@app.route('/api/schedules')
def get_schedules():
    """
    선택한 날짜에 해당하는 셔틀버스 시간표와 예약 현황을 JSON으로 반환하는 API입니다.
    프론트엔드에서 날짜를 선택할 때마다 비동기(Fetch)로 호출됩니다.
    """
    # URL 쿼리 스트링에서 날짜를 가져옵니다.
    target_date_str = request.args.get('date')
    target_date = parse_date(target_date_str)
    if not target_date:
        # 날짜 형식이 잘못된 경우 400 에러를 반환합니다.
        return jsonify({'error': '올바른 날짜를 선택해주세요.'}), 400

    now = datetime.now()
    # 선택된 날짜의 요일을 구합니다.
    target_weekday = WEEKDAYS[target_date.weekday()]
    
    # 해당 날짜의 예약 가능 상태(주말, 공휴일, 예약 오픈 시간 등)를 종합 검사합니다.
    can_book_now, is_past, booking_message = get_booking_open_status(target_date, now)
    
    # 운행 불가능한 날짜(휴일/주말/방학)라면 빈 스케줄 배열과 차단 메시지를 반환합니다.
    if not can_book_now and not is_past and booking_message and "운행하지 않습니다" in booking_message:
        return jsonify({
            'date': target_date_str,
            'weekday': target_weekday,
            'booking_message': booking_message,
            'schedules': []
        })

    student_id = session.get('student_id')
    conn = get_db_connection()
    try:
        # DB에서 전체 셔틀버스 시간표를 노선과 시간순으로 가져옵니다.
        schedules = conn.execute('SELECT * FROM Schedules ORDER BY route_name, departure_time').fetchall()

        result = []
        for sch in schedules:
            # 해당 요일에 운행하지 않는 배차는 목록에서 제외합니다.
            if target_weekday not in sch['day_of_week']:
                continue

            # 현재 조회 중인 배차의 활성 예약 수를 카운트하여 잔여 좌석을 계산합니다.
            res_count = conn.execute(
                "SELECT COUNT(*) AS cnt FROM Reservations WHERE schedule_id = ? AND ride_date = ? AND status = 'ACTIVE'",
                (sch['schedule_id'], target_date_str)
            ).fetchone()['cnt']

            my_res_id = None
            # 로그인된 사용자의 경우, 해당 배차에 이미 예약했는지 확인합니다.
            if student_id:
                my_res = conn.execute(
                    "SELECT reservation_id FROM Reservations WHERE student_id = ? AND schedule_id = ? AND ride_date = ? AND status = 'ACTIVE'",
                    (student_id, sch['schedule_id'], target_date_str)
                ).fetchone()
                if my_res:
                    # 예약 내역이 있으면 예약 ID를 저장합니다.
                    my_res_id = my_res['reservation_id']

            # 버스 출발 시간과 현재 시간을 비교합니다.
            departure_dt = datetime.strptime(f"{target_date_str} {sch['departure_time']}", '%Y-%m-%d %H:%M')
            is_departed = now >= departure_dt
            # 남은 좌석 수를 계산합니다. (음수가 되지 않도록 max 사용)
            remaining_seats = max(0, sch['total_seats'] - res_count)

            # 프론트엔드 버튼 렌더링을 위한 상태(status)를 결정합니다.
            if my_res_id:
                status = 'reserved' # 내가 예약함
            elif is_past:
                status = 'past' # 과거 날짜
            elif is_departed:
                status = 'departed' # 이미 출발함
            elif not can_book_now:
                status = 'not_open' # 아직 오픈 안 됨
            elif remaining_seats <= 0:
                status = 'full' # 좌석 꽉 참
            else:
                status = 'available' # 예약 가능

            # 최종적으로 프론트엔드에 전달할 딕셔너리를 구성하여 배열에 추가합니다.
            result.append({
                'schedule_id': sch['schedule_id'],
                'route_name': sch['route_name'],
                'direction': sch['direction'],
                'departure_time': sch['departure_time'],
                'total_seats': sch['total_seats'],
                'reserved_seats': res_count,
                'remaining_seats': remaining_seats,
                'is_departed': is_departed,
                'my_reservation_id': my_res_id,
                'can_book_now': can_book_now,
                'is_past': is_past,
                'status': status,
                'booking_message': booking_message,
                # 출발 10분 전까지만 취소 버튼을 활성화하기 위한 플래그
                'can_cancel': bool(my_res_id and not is_departed and (departure_dt - now) > timedelta(minutes=10))
            })

        # 최종 JSON 응답 반환
        return jsonify({
            'date': target_date_str,
            'weekday': target_weekday,
            'booking_message': booking_message,
            'schedules': result
        })
    finally:
        conn.close()


@app.route('/reserve', methods=['POST'])
def reserve():
    """
    사용자가 '예약하기' 버튼을 눌렀을 때 호출되는 API입니다.
    동시성 제어 및 유효성 검사를 수행한 후 예약을 DB에 등록합니다.
    """
    # 인증 안 된 요청 거부
    if 'student_id' not in session:
        return jsonify({'error': '로그인이 필요합니다.'}), 401

    data = request.get_json(silent=True) or {}
    student_id = session['student_id']
    schedule_id = data.get('schedule_id')
    ride_date = data.get('ride_date')

    # 넘어온 schedule_id가 정수형인지 검증합니다.
    if not isinstance(schedule_id, int):
        try:
            schedule_id = int(schedule_id)
        except (TypeError, ValueError):
            return jsonify({'error': '잘못된 배차 정보입니다.'}), 400

    target_date = parse_date(ride_date)
    if not target_date:
        return jsonify({'error': '잘못된 탑승 날짜입니다.'}), 400

    now = datetime.now()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 트랜잭션을 시작하며 쓰기 락(Lock)을 걸어 여러 사용자가 동시에 예약하는 오버부킹을 방지합니다.
        cursor.execute('BEGIN IMMEDIATE;')

        # 사용자 정보 조회 및 페널티(노쇼) 확인 로직
        user = cursor.execute('SELECT penalty_until FROM Users WHERE student_id = ?', (student_id,)).fetchone()
        if not user:
            conn.rollback()
            return jsonify({'error': '존재하지 않는 사용자입니다.'}), 401

        if user['penalty_until']:
            penalty_until = datetime.strptime(user['penalty_until'], '%Y-%m-%d %H:%M:%S')
            if penalty_until > now:
                conn.rollback()
                return jsonify({'error': '노쇼 페널티로 예약이 차단된 상태입니다.'}), 403

        # 선택한 배차의 상세 정보를 조회합니다.
        schedule = cursor.execute('SELECT schedule_id, route_name, direction, day_of_week, total_seats, departure_time FROM Schedules WHERE schedule_id = ?', (schedule_id,)).fetchone()
        
        if not schedule:
            conn.rollback()
            return jsonify({'error': '존재하지 않는 배차입니다.'}), 404

        target_weekday = WEEKDAYS[target_date.weekday()]
        if target_weekday not in schedule['day_of_week']:
            conn.rollback()
            return jsonify({'error': '선택한 날짜에는 운행하지 않는 배차입니다.'}), 400

        # 백엔드 단에서 공휴일 및 예약 오픈 정책을 다시 검사하여 프론트 우회 요청을 방어합니다.
        can_book_now, is_past, booking_message = get_booking_open_status(target_date, now)
        if is_past:
            conn.rollback()
            return jsonify({'error': '과거 날짜에는 예약할 수 없습니다.'}), 403
        if not can_book_now:
            conn.rollback()
            return jsonify({'error': booking_message or '아직 예약할 수 없습니다.'}), 403

        # 출발 시간 이후인지 검증합니다.
        departure_dt = datetime.strptime(f"{ride_date} {schedule['departure_time']}", '%Y-%m-%d %H:%M')
        if now >= departure_dt:
            conn.rollback()
            return jsonify({'error': '이미 출발 시간이 지난 배차입니다.'}), 403

        # 중복 예약 방지: 같은 방향(등교/하교)으로 이미 예약한 내역이 있는지 확인합니다.
        duplicate = cursor.execute('''
            SELECT 1 FROM Reservations r JOIN Schedules s ON r.schedule_id = s.schedule_id
            WHERE r.student_id = ? AND r.ride_date = ? AND s.direction = ? AND r.status = 'ACTIVE' LIMIT 1
        ''', (student_id, ride_date, schedule['direction'])).fetchone()

        if duplicate:
            conn.rollback()
            return jsonify({'error': f"이미 {schedule['direction']} 방향 예약이 있습니다."}), 409

        # 현재 해당 배차의 총 예약 인원을 계산합니다.
        current_res = cursor.execute("SELECT COUNT(*) AS cnt FROM Reservations WHERE schedule_id = ? AND ride_date = ? AND status = 'ACTIVE'", (schedule_id, ride_date)).fetchone()['cnt']

        # 예약 인원이 총 좌석 수와 같거나 크면 예약을 튕겨냅니다. (동시성 제어의 핵심)
        if current_res >= schedule['total_seats']:
            conn.rollback()
            return jsonify({'error': '죄송합니다. 방금 다른 사용자가 마지막 좌석을 예약했습니다.'}), 409

        # 모든 검증을 통과하면 최종적으로 예약 정보를 DB에 삽입합니다.
        cursor.execute("INSERT INTO Reservations (student_id, schedule_id, ride_date, status) VALUES (?, ?, ?, 'ACTIVE')", (student_id, schedule_id, ride_date))
        # 트랜잭션을 승인하고 락을 풉니다.
        conn.commit()
        return jsonify({'message': '예약이 성공적으로 완료되었습니다.', 'reservation_id': cursor.lastrowid}), 201

    except sqlite3.OperationalError as e:
        # DB 락으로 인한 시간 초과 등의 오류 발생 시 롤백합니다.
        conn.rollback()
        if 'locked' in str(e).lower():
            return jsonify({'error': '동시에 예약 요청이 몰렸습니다. 잠시 후 다시 시도해주세요.'}), 409
        return jsonify({'error': '데이터베이스 처리 중 오류가 발생했습니다.'}), 500
    except Exception:
        # 기타 예상치 못한 에러 발생 시 처리합니다.
        conn.rollback()
        return jsonify({'error': '서버 내부 오류가 발생했습니다.'}), 500
    finally:
        conn.close()


@app.route('/mypage')
def mypage():
    """
    사용자의 '나의 예약 내역' 페이지를 렌더링하는 라우트입니다.
    """
    if 'student_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    try:
        # 💡 UTC로 저장된 예약 시간을 한국 시간(로컬 타임)으로 변환하여 조회합니다.
        my_reservations = conn.execute(
            '''
            SELECT r.reservation_id, r.ride_date, r.status, 
                   datetime(r.created_at, 'localtime') as created_at,
                   s.route_name, s.direction, s.departure_time
            FROM Reservations r
            JOIN Schedules s ON r.schedule_id = s.schedule_id
            WHERE r.student_id = ?
            ORDER BY r.ride_date DESC, s.departure_time DESC
            ''',
            (session['student_id'],)
        ).fetchall()
    finally:
        conn.close()

    # 조회된 내역을 history.html 템플릿에 넘겨줍니다.
    return render_template('history.html', name=session['name'], reservations=my_reservations)


@app.route('/cancel', methods=['POST'])
def cancel():
    """
    사용자가 '예약 취소' 버튼을 눌렀을 때 호출되는 API입니다.
    출발 10분 전까지만 취소를 허용하며 상태를 'CANCELED'로 변경합니다.
    """
    if 'student_id' not in session:
        return jsonify({'error': '로그인이 필요합니다.'}), 401

    data = request.get_json(silent=True) or {}
    reservation_id = data.get('reservation_id')
    student_id = session['student_id']

    try:
        reservation_id = int(reservation_id)
    except (TypeError, ValueError):
        return jsonify({'error': '잘못된 예약 정보입니다.'}), 400

    now = datetime.now()
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 취소하려는 예약 정보를 조회합니다.
        res = cursor.execute('''
            SELECT r.ride_date, s.departure_time, r.status
            FROM Reservations r JOIN Schedules s ON r.schedule_id = s.schedule_id
            WHERE r.reservation_id = ? AND r.student_id = ?
        ''', (reservation_id, student_id)).fetchone()

        # 본인의 예약이 아니거나 이미 취소된 상태면 튕겨냅니다.
        if not res or res['status'] != 'ACTIVE':
            return jsonify({'error': '유효하지 않은 예약이거나 이미 취소되었습니다.'}), 400

        # 버스 출발 10분 전까지만 취소할 수 있도록 유효성을 체크합니다.
        departure_dt = datetime.strptime(f"{res['ride_date']} {res['departure_time']}", '%Y-%m-%d %H:%M')
        if now >= departure_dt - timedelta(minutes=10):
            return jsonify({'error': '예약 취소는 출발 10분 전까지만 가능합니다.'}), 403

        # DB에서 예약 상태를 취소 상태('CANCELED')로 업데이트(소프트 삭제)합니다.
        cursor.execute("UPDATE Reservations SET status = ? WHERE reservation_id = ? AND student_id = ? AND status = ?", ('CANCELED', reservation_id, student_id, 'ACTIVE'))
        if cursor.rowcount != 1:
            conn.rollback()
            return jsonify({'error': '예약 취소에 실패했습니다.'}), 409

        conn.commit()
        return jsonify({'message': '예약이 정상적으로 취소 처리되었습니다.'}), 200
    finally:
        conn.close()


if __name__ == '__main__':
    # 서버를 실행합니다.
    app.run(host='0.0.0.0', port=5000, debug=True)