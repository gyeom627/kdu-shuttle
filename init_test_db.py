"""오버부킹 동시성 테스트 전용 SQLite DB 생성 스크립트.

생성 파일: test_shuttle.db
테스트 날짜: 가장 가까운 토요일
테스트 버스: 정원 1명
테스트 사용자: 2명
"""
from datetime import date, timedelta
import sqlite3

DB_PATH = 'test_shuttle.db'


def next_saturday(from_date=None):
    today = from_date or date.today()
    days = (5 - today.weekday()) % 7
    return today + timedelta(days=days)


conn = sqlite3.connect(DB_PATH)
try:
    conn.executescript('''
    DROP TABLE IF EXISTS Reservations;
    DROP TABLE IF EXISTS Schedules;
    DROP TABLE IF EXISTS Users;

    CREATE TABLE Users (
        student_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        penalty_until TEXT
    );

    CREATE TABLE Schedules (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        route_name TEXT NOT NULL,
        direction TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        departure_time TEXT NOT NULL,
        total_seats INTEGER NOT NULL CHECK(total_seats > 0)
    );

    CREATE TABLE Reservations (
        reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        schedule_id INTEGER NOT NULL,
        ride_date TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'ACTIVE',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES Users(student_id),
        FOREIGN KEY(schedule_id) REFERENCES Schedules(schedule_id)
    );

    CREATE INDEX idx_reservation_schedule_date
    ON Reservations(schedule_id, ride_date, status);

    CREATE INDEX idx_reservation_student_date
    ON Reservations(student_id, ride_date, status);
    ''')

    target = next_saturday()

    conn.executemany(
        'INSERT INTO Users(student_id, name) VALUES (?, ?)',
        [('TEST001', '동시성 테스트 학생 1'), ('TEST002', '동시성 테스트 학생 2')]
    )

    cursor = conn.execute(
        '''
        INSERT INTO Schedules(route_name, direction, day_of_week, departure_time, total_seats)
        VALUES (?, ?, ?, ?, ?)
        ''',
        ('동시성 테스트 노선', '학교 → 터미널', '토', '23:59', 1)
    )

    conn.commit()

    print('테스트 DB 생성 완료')
    print(f'파일: {DB_PATH}')
    print(f'테스트 날짜: {target.isoformat()} (토요일)')
    print(f'schedule_id: {cursor.lastrowid}')
    print('학생: TEST001 / TEST002')
finally:
    conn.close()
