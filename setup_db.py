import sqlite3

def setup_database():
    # 1. DB 파일 연결 및 생성
    conn = sqlite3.connect('shuttle.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 혹시 모를 꼬임을 방지하기 위해 기존 테이블이 있다면 깔끔하게 삭제 후 재성성
    cursor.execute('DROP TABLE IF EXISTS Reservations')
    cursor.execute('DROP TABLE IF EXISTS Schedules')
    cursor.execute('DROP TABLE IF EXISTS Users')

    # ==========================================
    # 2. 테이블 뼈대 생성 (CREATE TABLE)
    # ==========================================
    cursor.execute('''
    CREATE TABLE Users (
        student_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        no_show_count INTEGER DEFAULT 0,
        penalty_until TEXT
    )
    ''')

    cursor.execute('''
    CREATE TABLE Schedules (
        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
        route_name TEXT NOT NULL,
        direction TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        departure_time TEXT NOT NULL,
        bus_count INTEGER DEFAULT 1,
        total_seats INTEGER NOT NULL
    )
    ''')

    cursor.execute('''
    CREATE TABLE Reservations (
        reservation_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        schedule_id INTEGER NOT NULL,
        ride_date TEXT NOT NULL,
        status TEXT DEFAULT 'ACTIVE',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES Users(student_id),
        FOREIGN KEY (schedule_id) REFERENCES Schedules(schedule_id)
    )
    ''')

    # ==========================================
    # 3. 초기 테스트 데이터 삽입 (INSERT)
    # ==========================================
    users = [
        ('20260001', '김경동', 0, None),
        ('20260002', '이소프트', 0, None),
        ('20260003', '박엔진', 0, None),
	('2221002', '고겸',0,None)
    ]
    cursor.executemany('INSERT INTO Users (student_id, name, no_show_count, penalty_until) VALUES (?, ?, ?, ?)', users)

    schedules = [
        # --- 도봉산 등교 ---
        ('도봉산', '등교', '월화수목', '08:50', 4, 180),
        ('도봉산', '등교', '금', '08:50', 1, 45),
        ('도봉산', '등교', '월화수목', '09:50', 3, 135),
        ('도봉산', '등교', '월화수목', '10:50', 2, 90),

        # --- 도봉산 하교 ---
        ('도봉산', '하교', '월화', '16:30', 2, 90),
        ('도봉산', '하교', '수목', '16:30', 1, 45),
        ('도봉산', '하교', '월화', '17:30', 2, 90),
        ('도봉산', '하교', '수목금', '17:30', 1, 45),
        ('도봉산', '하교', '월화수목', '18:30', 1, 45),

        # --- 양주 등교 ---
        ('양주', '등교', '월화수목', '08:00', 1, 45),
        ('양주', '등교', '금', '08:45', 1, 45),
        ('양주', '등교', '월화수목', '08:50', 1, 45),
        ('양주', '등교', '월화수목', '09:10', 1, 45),
        ('양주', '등교', '금', '09:40', 1, 45),
        ('양주', '등교', '월화수목', '09:50', 1, 45),
        ('양주', '등교', '월화수목', '10:30', 1, 45),
        ('양주', '등교', '월화수목', '11:10', 1, 45),

        # --- 양주 하교 ---
        ('양주', '하교', '월화수목', '13:30', 1, 45),
        ('양주', '하교', '월화수목', '14:00', 1, 45),
        ('양주', '하교', '월화수목', '14:30', 1, 45),
        ('양주', '하교', '월화수목', '15:30', 1, 45),
        ('양주', '하교', '월화수목', '16:10', 1, 45),
        ('양주', '하교', '월화수목', '17:00', 1, 45),
        ('양주', '하교', '금', '17:40', 1, 45),
        ('양주', '하교', '월화수목', '17:45', 1, 45),
        ('양주', '하교', '월화수목금', '18:30', 1, 45),

        # --- 의정부 등교 ---
        ('의정부', '등교', '월화수목', '08:50', 1, 45),
        ('의정부', '등교', '월화수목', '09:50', 1, 45),

        # --- 의정부 하교 ---
        ('의정부', '하교', '월화수목', '14:00', 1, 45),
        ('의정부', '하교', '월화수목', '15:00', 1, 45)
    ]
    
    cursor.executemany('''
        INSERT INTO Schedules (route_name, direction, day_of_week, departure_time, bus_count, total_seats)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', schedules)

    # 4. 저장 및 종료
    conn.commit()
    conn.close()
    print("성공: 테이블 생성 및 초기 데이터 삽입이 완벽하게 끝났습니다! (shuttle.db)")

if __name__ == '__main__':
    setup_database()