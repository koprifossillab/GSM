"""그때 그 자리 — PALEOMAP 2016 판 회전으로 오늘의 한 자리를 옛 연대로 옮긴다 (wetherilli P06 §3·087).

`data/paleomap2016.json`(`manage.py build_paleomap <zip>`)을 읽는다. 상류가 아니라 저장소의 파일이라 문이 아니다.

- **계산이지 관측이 아니다.** 판을 굳은 것으로 보고 그 판의 회전을 그대로 태운다. 판 안의 변형·해수면은 없다
- 모델은 **PALEOMAP 2016**(Scotese, CC BY 4.0)이다. EarthThruTime3D(ETT)가 핀과 기본 화면을 이 모델로 그렸다 —
  같은 모델이어야 ETT 로 건너갔을 때 같은 자리에 핀이 선다(P06 §4). 다른 모델은 100 Ma 에 4–10° 갈린다(ETT wwolf 014)
- 셈법은 ETT 의 `scripts/rotation_model.py`·`static/core/pins.js`(MIT, © 2026 PaleoBytes — 허가 문구는
  `docs/licenses/EarthThruTime3D-MIT.txt`)를 옮겼다. 오늘의 자리를 담는
  대륙 다각형을 고르고(구면 위의 감김 — 날짜변경선·극을 넘어도 맞다), 그 판의 회전을 판 사슬을 따라 쿼터니언으로
  잇는다. 두 표본 사이는 slerp 다
- **닿는 곳은 대륙 위, 그 다각형이 생긴 때와 판의 극이 끝나는 때 가운데 가까운 쪽까지다.** 바다 밑은 다각형이 없다 —
  섭입으로 대부분 사라졌다. 모델이 덮는 것은 1 100 Ma 까지다
"""
import functools
import json
import math
from collections import defaultdict

from django.conf import settings

IDENTITY = (1.0, 0.0, 0.0, 0.0)
ANCHOR = 0


def _quaternion(pole_lat, pole_lon, angle):
    """축(극)과 각 → 단위 쿼터니언. 잇고 사이를 채우기 좋은 꼴이다."""
    lat, lon = math.radians(pole_lat), math.radians(pole_lon)
    half = math.radians(angle) / 2.0
    s = math.sin(half)
    return (math.cos(half), math.cos(lat) * math.cos(lon) * s, math.cos(lat) * math.sin(lon) * s, math.sin(lat) * s)


def _multiply(a, b):
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return (w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
            w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
            w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
            w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2)


def _conjugate(q):
    return (q[0], -q[1], -q[2], -q[3])


def _slerp(a, b, f):
    dot = sum(x * y for x, y in zip(a, b))
    if dot < 0.0:
        b, dot = tuple(-v for v in b), -dot
    if dot > 0.9999995:
        out = tuple(x + (y - x) * f for x, y in zip(a, b))
    else:
        theta = math.acos(max(-1.0, min(1.0, dot)))
        s = math.sin(theta)
        p, q = math.sin((1.0 - f) * theta) / s, math.sin(f * theta) / s
        out = tuple(x * p + y * q for x, y in zip(a, b))
    norm = math.sqrt(sum(v * v for v in out)) or 1.0
    return tuple(v / norm for v in out)


def turn(q, lon, lat):
    """점(도)을 회전 `q` 로 옮긴다."""
    lo, la = math.radians(lon), math.radians(lat)
    p = (0.0, math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))
    _, x, y, z = _multiply(_multiply(q, p), _conjugate(q))
    return math.degrees(math.atan2(y, x)), math.degrees(math.asin(max(-1.0, min(1.0, z))))


class Rotations:
    """회전 목록 — `{"움직이는 판:기준 판": [때, 극 위도, 극 경도, 각, …]}` (ETT 의 `rotations.json` 과 같은 꼴)."""

    def __init__(self, sequences: dict):
        self.samples = {}
        self.by_moving = defaultdict(list)
        for key, flat in sequences.items():
            moving, fixed = (int(v) for v in key.split(":"))
            rows = [tuple(flat[i:i + 4]) for i in range(0, len(flat), 4)]
            self.samples[(moving, fixed)] = rows
            self.by_moving[moving].append((fixed, rows[0][0], rows[-1][0]))

    @staticmethod
    def _relative(rows, t):
        if not rows or t < rows[0][0] - 1e-9 or t > rows[-1][0] + 1e-9:
            return None
        prev = rows[0]
        for row in rows:
            if row[0] >= t - 1e-9:
                if abs(row[0] - prev[0]) < 1e-9 or abs(row[0] - t) < 1e-9:
                    return _quaternion(row[1], row[2], row[3])
                # 극을 섞지 않고 앞 표본에서 뒤 표본으로 가는 회전을 나눈다 — 단계 회전을 나누는 법이다
                start, end = _quaternion(prev[1], prev[2], prev[3]), _quaternion(row[1], row[2], row[3])
                stage = _multiply(_conjugate(start), end)
                return _multiply(start, _slerp(IDENTITY, stage, (t - prev[0]) / (row[0] - prev[0])))
            prev = row
        return _quaternion(rows[-1][1], rows[-1][2], rows[-1][3])

    def rotation(self, plate: int, t: float, _seen=frozenset()):
        """판 `plate` 의 `t` Ma 때 기준(판 0)에 대한 온 회전. 극이 없으면 None."""
        if plate == ANCHOR:
            return IDENTITY
        if plate in _seen:
            return None                                   # 사슬이 돈다 — 모델의 흠이다
        # 서른 남짓한 판은 넓은 줄 위에 좁은 줄을 겹쳐 "이 동안은 다른 이웃에 대어 잰다" 고 적었다.
        # 늦게 시작하는 좁은 줄이 하려는 말이라 겹친 곳에서는 그것이 이긴다 (ETT 와 같다)
        for fixed, start, end in sorted(self.by_moving.get(plate, []), key=lambda e: e[1], reverse=True):
            if not start - 1e-9 <= t <= end + 1e-9:
                continue
            relative = self._relative(self.samples[(plate, fixed)], t)
            if relative is None:
                continue
            upstream = self.rotation(fixed, t, _seen | {plate})
            if upstream is not None:
                return _multiply(upstream, relative)
        return None


def _unit(lon, lat):
    lo, la = math.radians(lon), math.radians(lat)
    return (math.cos(la) * math.cos(lo), math.cos(la) * math.sin(lo), math.sin(la))


def inside(lon, lat, ring) -> bool:
    """구면 위의 고리(`[경도, 위도, …]`) 안인가. 안에서 보면 꼭짓점의 방위가 한 바퀴 돌고, 밖에서 보면 제자리로
    돌아온다 — 날짜변경선·극을 넘어도 맞는다. 대척점과는 못 가른다(`_facing`)."""
    x, y, z = _unit(lon, lat)
    flat = max(math.hypot(x, y), 1e-12)
    east = (-y / flat, x / flat, 0.0)
    north = (y * east[2] - z * east[1], z * east[0] - x * east[2], x * east[1] - y * east[0])
    turned, first, prev = 0.0, None, None
    for i in range(0, len(ring) + 1, 2):
        v = first if i == len(ring) else _unit(ring[i], ring[i + 1])
        bearing = math.atan2(v[0] * east[0] + v[1] * east[1],
                             v[0] * north[0] + v[1] * north[1] + v[2] * north[2])
        if prev is not None:
            step = bearing - prev
            turned += step - 2 * math.pi * round(step / (2 * math.pi))
        if first is None:
            first = v
        prev = bearing
    return abs(turned) > math.pi


def _facing(feature, lon, lat) -> bool:
    """대륙은 반구보다 좁다 — 안에 든 자리는 그 가운데를 바라본다."""
    c = feature.get("_centre")
    if c is None:
        c = [0.0, 0.0, 0.0]
        for ring in feature["rings"]:
            for i in range(0, len(ring), 2):
                for axis, v in enumerate(_unit(ring[i], ring[i + 1])):
                    c[axis] += v
        feature["_centre"] = c
    p = _unit(lon, lat)
    return p[0] * c[0] + p[1] * c[1] + p[2] * c[2] > 0


def holds(feature, lon, lat) -> bool:
    if not _facing(feature, lon, lat):
        return False
    held = False
    for ring in feature["rings"]:                         # 홀짝 — 구멍은 구멍이다
        if inside(lon, lat, ring):
            held = not held
    return held


class Model:
    def __init__(self, data: dict):
        self.meta = {k: data[k] for k in ("title", "citation", "license", "license_url", "covers_ma") if k in data}
        self.deepest = float(data.get("covers_ma", [0, 1100])[1])
        self.rotations = Rotations(data["sequences"])
        self.features = data["features"]

    def reach(self, pid: int, older: float) -> float:
        """판을 어디까지 거슬러 옮길 수 있나 — 다각형이 생긴 때와 극이 끝나는 때 가운데 가까운 쪽."""
        older = min(older, self.deepest)
        if self.rotations.rotation(pid, older) is not None:
            return older
        newer = 0.0
        while older - newer > 0.01:
            mid = (older + newer) / 2
            if self.rotations.rotation(pid, mid) is None:
                older = mid
            else:
                newer = mid
        return round(newer, 1)

    def _now(self, pid: int):
        """판의 0 Ma 회전. PALEOMAP 은 거의 항등이지만 판마다 조금 어긋난다 — 다각형은 그 회전 앞의 좌표다."""
        cache = self.__dict__.setdefault("_now_cache", {})
        if pid not in cache:
            cache[pid] = self.rotations.rotation(pid, 0.0) or IDENTITY
        return cache[pid]

    def plate_at(self, lon: float, lat: float):
        """오늘의 자리를 담는 대륙 다각형의 판. 여럿이 겹치면 가장 멀리 거슬러 가는 것. 바다 밑이면 None.
        `lon`·`lat` 은 판의 0 Ma 회전을 되돌린 좌표다 — 이것을 옛 연대의 회전으로 옮긴다 (ETT `pinAt` 과 같다)."""
        best = None
        for f in self.features:
            if f["to"] > 1e-9 or f["from"] < -1e-9:
                continue                                   # 오늘 있는 다각형만
            here = turn(_conjugate(self._now(f["pid"])), lon, lat)
            if not holds(f, *here):
                continue
            if best is None or f["from"] > best["from"]:
                best = {"pid": f["pid"], "from": f["from"], "lon": here[0], "lat": here[1]}
        if best is not None:
            best["reach"] = self.reach(best["pid"], best["from"])
        return best

    def carry(self, lon: float, lat: float, age: float, plate=None) -> dict:
        """오늘의 (lon, lat) 이 `age` Ma 에 있던 자리. 못 옮기면 `reason` 만 — `ocean`·`beyond`·`future`.
        같은 자리를 여러 연대로 옮길 때는 `plate_at` 을 한 번 불러 `plate` 로 넘긴다."""
        plate = plate or self.plate_at(lon, lat)
        if plate is None:
            return {"age": age, "reason": "ocean"}
        if age < 0:
            return {"age": age, "reason": "future"}
        if age > plate["reach"] + 1e-9:
            return {"age": age, "reason": "beyond", "reach": plate["reach"], "pid": plate["pid"]}
        q = self.rotations.rotation(plate["pid"], age)
        if q is None:
            return {"age": age, "reason": "beyond", "reach": plate["reach"], "pid": plate["pid"]}
        plon, plat = turn(q, plate["lon"], plate["lat"])
        return {"age": age, "lon": round(plon, 2), "lat": round(plat, 2), "pid": plate["pid"], "reach": plate["reach"]}


@functools.lru_cache(maxsize=1)
def model():
    """저장소의 파일을 한 번 읽는다. 없으면 None — 화면은 "옛 위치" 줄을 빼고 돈다."""
    try:
        with open(settings.PALEOMAP_FILE, encoding="utf-8") as fh:
            return Model(json.load(fh))
    except FileNotFoundError:
        return None
