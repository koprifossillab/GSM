"""다누리 자기장 측정기(KMAG)의 궤적 — 하루치 CSV 를 줄여 sqlite 한 장에 (wetherilli 377). 문이 아니다.

`manage.py fetch_kmag` 이 KPDS(`kpds.py`)에서 Calibrated 하루치(4 초 간격, 21 600 행)를 받아 **32 초마다 한 점**만 남겨
`<KPDS_DIR>/kmag.sqlite` 에 더한다. 화면은 이것만 읽는다.

- 자리는 `X/Y/Z_SEL`(km)에서 푼다. 라벨이 SEL 을 정의하지 않는다 — 달 고정 좌표계(달의 평균 지구 방향이 +X)로 읽었다.
  하루에 궤도 경도가 13° 남짓 서쪽으로 밀려(달의 자전) 그렇게 읽는 것이 맞다. 고도는 1 737.4 km 구 위의 높이다
- 값은 그 자리의 자기장 세기 |B|(nT, SEL 성분에서). **지각 자기 이상이 아니다** — 태양풍·지구 자기권의 바깥 자기장이 섞인 값이라
  화면은 이것으로 궤적을 칠하지 않고 누른 자리에서만 보인다(사용자가 정했다)
- 빈 값(−99999)은 자리만 두고 |B| 를 비운다
- 같은 하루를 두 번 넣지 않는다(`days`). 줄인 간격을 바꾸면 `RENDERER` 를 올리고 다시 모은다
"""
import csv
import io
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

FILE = "kmag.sqlite"
RENDERER = "1"
STEP = 32                        # 초 — 이 간격마다 한 점. 궤도 속도 1.6 km/s 로 50 km 남짓
GAP = 2 * STEP + 1               # 이보다 벌어지면 궤적을 끊는다
RADIUS = 1737.4                  # km
FILL = -99999.0
CITE = "KPLO (Danuri) KMAG calibrated magnetic field — KARI KPDS; instrument: Kyung Hee University"
SCHEMA = """
CREATE TABLE IF NOT EXISTS points (id INTEGER PRIMARY KEY, t INTEGER NOT NULL, lon REAL NOT NULL, lat REAL NOT NULL,
                                   alt REAL NOT NULL, b REAL);
CREATE VIRTUAL TABLE IF NOT EXISTS points_idx USING rtree(id, lon0, lon1, lat0, lat1);
CREATE TABLE IF NOT EXISTS days (name TEXT PRIMARY KEY, n INTEGER NOT NULL, added TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
CREATE INDEX IF NOT EXISTS points_t ON points (t);
"""


def path() -> Path:
    return Path(settings.KPDS_DIR) / FILE


def connect(write: bool = False):
    """sqlite 하나. 읽기만 할 때 파일이 없으면 None."""
    p = path()
    if not write and not p.exists():
        return None
    if write:
        p.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(p)
        conn.executescript(SCHEMA)
        return conn
    return sqlite3.connect(f"file:{p}?mode=ro", uri=True, check_same_thread=False)


def available() -> bool:
    return path().exists()


def parse(text: str) -> list:
    """하루치 CSV → `[(유닉스 초, 경도, 위도, 고도 km, |B| 또는 None)…]`, `STEP` 초마다 하나."""
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        try:
            t = datetime.strptime(row["UTC"].strip()[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError):
            continue
        sec = int(t.timestamp())
        if sec % STEP:
            continue
        try:
            x, y, z = (float(row[k]) for k in ("X_SEL", "Y_SEL", "Z_SEL"))
            bx, by, bz = (float(row[k]) for k in ("Bx_SEL", "By_SEL", "Bz_SEL"))
        except (KeyError, ValueError):
            continue
        r = math.sqrt(x * x + y * y + z * z)
        if not RADIUS < r < RADIUS + 3000:
            continue
        b = None if FILL in (bx, by, bz) else round(math.sqrt(bx * bx + by * by + bz * bz), 2)
        out.append((sec, round(math.degrees(math.atan2(y, x)), 4), round(math.degrees(math.asin(z / r)), 4),
                    round(r - RADIUS, 1), b))
    return out


def add_day(conn, name: str, points: list) -> int:
    """하루치를 더한다. 이미 있으면 0."""
    if conn.execute("SELECT 1 FROM days WHERE name = ?", (name,)).fetchone():
        return 0
    with conn:
        for sec, lon, lat, alt, b in points:
            cur = conn.execute("INSERT INTO points (t, lon, lat, alt, b) VALUES (?, ?, ?, ?, ?)", (sec, lon, lat, alt, b))
            conn.execute("INSERT INTO points_idx VALUES (?, ?, ?, ?, ?)", (cur.lastrowid, lon, lon, lat, lat))
        conn.execute("INSERT INTO days VALUES (?, ?, ?)", (name, len(points), datetime.now(timezone.utc).isoformat()))
        conn.execute("INSERT OR REPLACE INTO meta VALUES ('built', ?)", (datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),))
    return len(points)


def has_day(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM days WHERE name = ?", (name,)).fetchone() is not None


def stamp() -> str:
    """캐시 열쇠에 넣을 판 — 날이 더해지면 바뀐다."""
    conn = connect()
    if conn is None:
        return ""
    try:
        row = conn.execute("SELECT v FROM meta WHERE k = 'built'").fetchone()
    finally:
        conn.close()
    return f"{RENDERER}-{row[0] if row else ''}"


def summary() -> dict:
    """`{"days", "points", "first", "last"}` — 모은 것이 없으면 빈 dict."""
    conn = connect()
    if conn is None:
        return {}
    try:
        days, = conn.execute("SELECT COUNT(*) FROM days").fetchone()
        n, lo, hi = conn.execute("SELECT COUNT(*), MIN(t), MAX(t) FROM points").fetchone()
    finally:
        conn.close()
    iso = lambda s: datetime.fromtimestamp(s, timezone.utc).strftime("%Y-%m-%d") if s else None   # noqa: E731
    return {"days": days, "points": n, "first": iso(lo), "last": iso(hi)}


def tracks(west: float, south: float, east: float, north: float, every: int = 1) -> list:
    """네모(달 경위도) 안의 궤적 — `[[(경도, 위도)…]…]`. 시각 차례로 잇고, `GAP` 초가 넘게 벌어지거나 날짜변경선을
    넘으면 끊는다. `every` 는 몇 점에 하나만 쓸지(넓게 볼 때)."""
    conn = connect()
    if conn is None:
        return []
    try:
        rows = conn.execute(
            "SELECT p.t, p.lon, p.lat FROM points p JOIN points_idx i ON i.id = p.id "
            "WHERE i.lon1 >= ? AND i.lon0 <= ? AND i.lat1 >= ? AND i.lat0 <= ? AND (p.t / ?) % ? = 0 ORDER BY p.t",
            (west, east, south, north, STEP, max(1, every))).fetchall()
    finally:
        conn.close()
    out, line, last = [], [], None
    gap = GAP * max(1, every)
    for t, lon, lat in rows:
        if line and (t - last > gap or abs(lon - line[-1][0]) > 180):
            if len(line) > 1:
                out.append(line)
            line = []
        line.append((lon, lat))
        last = t
    if len(line) > 1:
        out.append(line)
    return out


def nearest(lon: float, lat: float, reach: float = 0.5):
    """누른 자리에서 가장 가까운 점 — `{"time", "lon", "lat", "alt", "b"}` 또는 None. `reach` 는 도."""
    conn = connect()
    if conn is None:
        return None
    k = max(math.cos(math.radians(lat)), 0.05)
    try:
        rows = conn.execute(
            "SELECT p.t, p.lon, p.lat, p.alt, p.b FROM points p JOIN points_idx i ON i.id = p.id "
            "WHERE i.lon1 >= ? AND i.lon0 <= ? AND i.lat1 >= ? AND i.lat0 <= ?",
            (lon - reach / k, lon + reach / k, lat - reach, lat + reach)).fetchall()
    finally:
        conn.close()
    best = min(rows, key=lambda r: ((r[1] - lon) * k) ** 2 + (r[2] - lat) ** 2, default=None)
    if best is None:
        return None
    t, plon, plat, alt, b = best
    return {"time": datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "lon": plon, "lat": plat, "alt": alt, "b": b}
