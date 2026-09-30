"""USGS 화성 옛 지질도 — 우리 디스크의 파일을 읽어 화성 경위도·극 타일을 굽는다 (devlog 068). 문이 아니다.

달 원도(039, `moonmap.py`)의 짝이다. 화면이 지금 쓰는 전 지구 지질도(SIM 3292, 2014, Trek)보다 먼저 나온
판들이다 — Trek 은 이것들을 주지 않는다(2026-09-30). 원본은 USGS 가 옛 PIGWAD 자리
(`asc-pds-services` 의 `pigpen/mars/geology/`)에 둔 GIS 묶음이다.

| 판 | 덮는 곳 | 축척 | 좌표 |
|---|---|---|---|
| I-1802-A·B·C (1986–87) | 전 지구 — 서쪽 적도·동쪽 적도·극 세 장을 Skinner 외(2006)가 이었다 | 1:1500만 | 화성 경위도(도) |

바이킹 영상으로 그린 첫 전 지구 지질도다. SIM 3292 는 이것을 MOLA·THEMIS 로 다시 그린 것이라, 두 판을 겹쳐
보면 30 년 사이 무엇이 바뀌었는지 보인다(달 원도와 통합판처럼).

**한 번 굽고(`manage.py build_mars_originals`) 그 뒤로는 sqlite 한 장을 읽는다.** 짜임은 달 원도와 같다 —
고리를 `moonmap.pack` 으로 담고 R*Tree 를 딸린다. 굽는 도구(`moonmap` 의 담기·선 읽기, `geomap` 의 칠하기)는
빌려 쓰고 고치지 않는다. 판을 더할 때는 `MAPS` 에 한 줄과 `_read_<판>` 하나를 더한다.

- **시대 열이 없다.** 단위 기호의 앞머리 대문자가 시대다 — `Api`(아마조니스기), `HNu`(헤스페리아기–노아키스기),
  `Nplh`(노아키스기). 크레이터 물질(`c`·`s`·`cs` …)처럼 앞머리가 없는 것은 시대를 매기지 않는다(여러 시대에 걸친다)
- 색은 USGS 가 함께 둔 `i-1802ABC_geo_units_RGBlut.csv`(단위 95 가지)다 — 원도의 색이다. 저장소에 담았다
  (`data/mars_original_styles.json`)
- 어느 장(A·B·C)에서 왔는지는 속성에 없다. 누른 자리로 가른다 — 위도 57° 너머 C, 서경 A, 동경 B.
  세 장의 경계가 그쯤이다(C 는 55° 부터 겹친다)

그리는 법을 고치면 `RENDERER` 를 올린다 — 안 올리면 캐시가 옛 그림을 낸다.
"""
import io
import json
import logging
import sqlite3
import threading
import zipfile
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw

from . import geo3al, geomap, moonmap, trek

log = logging.getLogger(__name__)

RENDERER = "1"
FILENAME = "mars_originals.sqlite"
TILE = 256
SUPERSAMPLE = 2
LAYERS = ("orig-units", "orig-lines")

MAPS = {
    "I-1802": {"title": "Geologic Map of Mars (western equatorial, eastern equatorial and polar regions)",
               "by": "Scott & Tanaka 1986; Greeley & Guest 1987; Tanaka & Scott 1987 (digital: Skinner et al. 2006)",
               "year": "1986–87", "sheets": {"A": "서쪽 적도", "B": "동쪽 적도", "C": "극지"}},
}
#: 원본 묶음 속의 셰이프파일 (소문자 경로 끝)
_FILES = {
    "I-1802": {"units": "i1802abc_mars2000_sphere/geo_units_oc_dd", "lines": "i1802abc_mars2000_sphere/geo_structure_oc_dd"},
}

_PERIODS = {"A": "Amazonian", "H": "Hesperian", "N": "Noachian"}


class MarsMapError(RuntimeError):
    pass


# ── 자리 ────────────────────────────────────────────────────────────

def data_file() -> Path:
    return Path(settings.MARS_DIR) / FILENAME


def available() -> bool:
    return data_file().is_file()


def knows(layer: str) -> bool:
    return layer in LAYERS


_local = threading.local()


def _conn():
    path = str(data_file())
    conn = getattr(_local, "conn", None)
    if conn is None or getattr(_local, "path", None) != path:
        if not Path(path).is_file():
            raise MarsMapError("옛 지질도 파일이 없다 — manage.py build_mars_originals 를 부른다")
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        _local.conn, _local.path = conn, path
    return conn


# ── 색·이름 ─────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def styles() -> dict:
    return json.loads(Path(settings.MARS_ORIGINAL_STYLES_FILE).read_text(encoding="utf-8"))


def unit_color(symbol: str) -> str:
    return styles()["units"].get(symbol, "#b0b0b0")


def line_style(kind: str) -> dict:
    for rule in styles()["lines"]:
        if kind in rule["kinds"]:
            return rule
    return styles()["lines"][-1]


def age_of(symbol: str) -> str:
    """단위 기호 앞머리 → 시대. `HNu` → "Hesperian and Noachian", `Api` → "Amazonian", `cs` → ""."""
    head = ""
    for ch in symbol:
        if ch in _PERIODS and ch not in head:
            head += ch
        else:
            break
    return " and ".join(_PERIODS[c] for c in head)


def sheet_of(map_id: str, lon: float, lat: float) -> str:
    if map_id != "I-1802":
        return ""
    return "C" if abs(lat) >= 57 else "A" if lon < 0 else "B"


# ── 굽기 (한 번) ────────────────────────────────────────────────────

def build(source, out_path) -> dict:
    """USGS 묶음(zip 이나 푼 폴더) → sqlite. `manage.py build_mars_originals` 가 부른다."""
    src = Path(source)
    names = {}
    if src.is_file():
        zf = zipfile.ZipFile(src)
        for n in zf.namelist():
            names[n.lower()] = n
        read = lambda n: zf.read(n)                  # noqa: E731
    else:
        for p in src.rglob("*"):
            names[str(p.relative_to(src)).lower()] = p
        read = lambda p: Path(p).read_bytes()       # noqa: E731

    def find(stem, suffix):
        for low, real in names.items():
            if low.endswith(stem + suffix):
                return real
        return None

    out = Path(out_path)
    tmp = out.with_suffix(".part")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript("""
        CREATE TABLE units (id INTEGER PRIMARY KEY, map TEXT, draw INTEGER, symbol TEXT, name TEXT, color TEXT,
                            geom BLOB);
        CREATE VIRTUAL TABLE units_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE lines (id INTEGER PRIMARY KEY, map TEXT, kind TEXT, geom BLOB);
        CREATE VIRTUAL TABLE lines_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
    """)
    counts = {}
    for draw, map_id in enumerate(MAPS):
        files = _FILES[map_id]
        shp, dbf = find(files["units"], ".shp"), find(files["units"], ".dbf")
        if not shp or not dbf:
            raise MarsMapError(f"{map_id} 의 지질 셰이프파일이 없다")
        shapes, rows = geo3al.read_polygons(read(shp)), geo3al.read_dbf(read(dbf))
        if len(shapes) != len(rows):
            raise MarsMapError(f"{map_id}: 셰이프({len(shapes)})와 속성({len(rows)})의 수가 다르다")
        n = 0
        for rings, row in zip(shapes, rows):
            if row is None or not rings:
                continue
            polygons = [[moonmap._unwrap(r) for r in poly] for poly in geo3al.group_rings(rings)]
            polygons = [p for p in polygons if p and len(p[0]) >= 6]
            if not polygons:
                continue
            symbol = (row.get("UnitSymbol") or "").strip()
            cur = db.execute("INSERT INTO units (map, draw, symbol, name, color, geom) VALUES (?,?,?,?,?,?)",
                             (map_id, draw, symbol, (row.get("UnitName") or "").strip(), unit_color(symbol),
                              moonmap.pack(polygons)))
            db.execute("INSERT INTO units_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *moonmap._bbox(polygons)))
            n += 1
        counts[map_id] = n
        lshp, ldbf = find(files["lines"], ".shp"), find(files["lines"], ".dbf")
        if lshp and ldbf:
            for parts, row in zip(moonmap._read_lines(read(lshp)), geo3al.read_dbf(read(ldbf))):
                kind = ((row or {}).get("SrucType") or "").strip()
                flat = [moonmap._unwrap(part) for part in parts if len(part) >= 2]
                if not flat or not kind:
                    continue
                cur = db.execute("INSERT INTO lines (map, kind, geom) VALUES (?,?,?)",
                                 (map_id, kind, moonmap.pack([flat])))
                db.execute("INSERT INTO lines_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *moonmap._bbox([flat])))
    db.execute("INSERT INTO meta VALUES ('renderer', ?)", (RENDERER,))
    db.commit()
    db.execute("VACUUM")
    db.close()
    tmp.replace(out)
    return counts


# ── 그리기 ──────────────────────────────────────────────────────────

def _hex(value: str) -> tuple:
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def _strokes(kind: str) -> list:
    rule = line_style(kind)
    return [{"color": _hex(rule["color"]), "width": rule.get("width", 1), "dash": rule.get("dash")}]


def _draw_rows(img, draw, rows, project, tr, size, ss, outline):
    """행(모양)마다 칠하거나 긋는다. `project` 는 경위도 납작한 목록 → 타일 평면 납작한 목록."""
    w, n, k, _ = tr
    for table, style, blob in rows:
        parts = [[project(list(r)) for r in rings] for rings in moonmap.unpack(blob)]
        xs = [v for rings in parts for r in rings for v in r[0::2]]
        ys = [v for rings in parts for r in rings for v in r[1::2]]
        if not xs:
            continue
        size_px = max(max(xs) - min(xs), max(ys) - min(ys)) * k
        if table == "units":
            color = _hex(style)
            if size_px < 1.5 * ss:
                cx, cy = ((min(xs) + max(xs)) / 2 - w) * k, (n - (min(ys) + max(ys)) / 2) * k
                draw.rectangle((cx - ss / 2, cy - ss / 2, cx + ss / 2 - 1, cy + ss / 2 - 1), fill=color)
                continue
            rule = {"fill": color, "outline": (0, 0, 0, 90) if outline else None, "width": 1}
            for rings in parts:
                geomap._fill_polygon(img, draw, rings, rule, tr, size_px, ss)
        else:
            for lines in parts:
                for flat in lines:
                    for run in geomap._clip_runs(geomap._to_px(flat, tr, size_px), size, size, 8 * ss):
                        geomap._stroke(draw, run, _strokes(style), ss)


def _select(layer, w, e, s, n):
    """네모에 걸친 모양 `[(경도 옮김, (갈래, 색·종류, 모양))]` — 그리는 차례(판, 번호)로.
    경도를 이어 적었으므로 네모를 ±360 옮겨 한 번 더 묻는다(039 와 같다)."""
    table = "units" if layer == "orig-units" else "lines"
    style, draw = ("t.color", "t.draw") if table == "units" else ("t.kind", "0")
    found = {}
    for shift in (0.0, -360.0, 360.0):
        for row_id, st, blob, order in _conn().execute(
                f"SELECT t.id, {style}, t.geom, {draw} FROM {table}_rtree r JOIN {table} t ON t.id = r.id "
                f"WHERE r.maxx >= ? AND r.minx <= ? AND r.maxy >= ? AND r.miny <= ?", (w + shift, e + shift, s, n)):
            found.setdefault(row_id, (order, shift, (table, st, blob)))
    return [(shift, row) for _, (order, shift, row) in sorted(found.items(), key=lambda kv: (kv[1][0], kv[0]))]


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.resize((TILE, TILE), Image.Resampling.BOX).save(buf, format="PNG")
    return buf.getvalue()


def render_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """화성 경위도 격자 한 장(Trek 과 같다) — 256 px 투명 PNG."""
    if layer not in LAYERS:
        raise MarsMapError("옛 지질도 레이어가 아니다")
    w, s, e, n = trek.tile_bbox(z, x, y)
    ss = SUPERSAMPLE
    size = TILE * ss
    k = size / (e - w)
    pad = 3 / k
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for shift, row in _select(layer, w - pad, e + pad, s - pad, n + pad):
        # 경도를 이어 적었으므로 ±360 옮겨 물은 것은 그만큼 되돌려 그린다
        project = (lambda flat, sh=shift: [v - sh if i % 2 == 0 else v for i, v in enumerate(flat)])
        _draw_rows(img, draw, [row], project, (w, n, k, k), size, ss, z >= 5)
    return _png(img)


def render_polar_tile(layer: str, pole: str, z: int, x: int, y: int) -> bytes:
    """화성 극 격자 한 장(`trek.mars_polar_tile_bbox`, 065) — 경위도의 모양을 극 평사도법으로 옮겨 그린다."""
    if layer not in LAYERS or pole not in ("n", "s"):
        raise MarsMapError("옛 지질도 레이어가 아니다")
    w, s, e, n = trek.mars_polar_tile_bbox(z, x, y)
    ss = SUPERSAMPLE
    size = TILE * ss
    k = size / (e - w)
    edge = [(w + (e - w) * i / 16, yy) for i in range(17) for yy in (s, n)] + \
           [(xx, s + (n - s) * i / 16) for i in range(17) for xx in (w, e)]
    lls = [trek.mars_polar_to_lonlat(px, py, pole) for px, py in edge]
    lats = [ll[1] for ll in lls]
    inside = w <= 0 <= e and s <= 0 <= n
    crosses = inside or (w <= 0 <= e and (n > 0 if pole == "n" else s < 0))
    lon_lo, lon_hi = (-180.0, 180.0) if crosses else (min(ll[0] for ll in lls), max(ll[0] for ll in lls))
    lat_lo, lat_hi = (min(lats), 90.0) if pole == "n" else (-90.0, max(lats))
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def project(flat):
        # 경위도의 곧은 변은 극 평면에서 굽는다 — 1° 넘는 변은 쪼개 옮긴다(위도선을 따라 한 바퀴 도는 변이
        # 점 둘뿐이면 고리가 선으로 찌그러진다)
        out = []
        for i in range(0, len(flat), 2):
            lon, lat = flat[i], flat[i + 1]
            if i:
                plon, plat = flat[i - 2], flat[i - 1]
                steps = int(max(abs(lon - plon), abs(lat - plat)))
                for k in range(1, steps):
                    t = k / steps
                    out += trek.mars_lonlat_to_polar(plon + (lon - plon) * t, plat + (lat - plat) * t, pole)
            out += trek.mars_lonlat_to_polar(lon, lat, pole)
        return out

    for _, row in _select(layer, lon_lo, lon_hi, lat_lo, lat_hi):
        _draw_rows(img, draw, [row], project, (w, n, k, k), size, ss, z >= 3)
    return _png(img)


# ── 속성·범례 ───────────────────────────────────────────────────────

def identify(lon: float, lat: float) -> dict | None:
    """한 점이 드는 단위. 겹치면 나중에 그린 판(위)이 이긴다."""
    hits = []
    for shift in (0.0, -360.0, 360.0):
        x = lon + shift
        for row in _conn().execute(
                "SELECT t.id, t.map, t.draw, t.symbol, t.name, t.color, t.geom FROM units_rtree r "
                "JOIN units t ON t.id = r.id WHERE r.minx <= ? AND r.maxx >= ? AND r.miny <= ? AND r.maxy >= ?",
                (x, x, lat, lat)):
            if any(geomap.polygon_contains([list(r) for r in rings], x, lat) for rings in moonmap.unpack(row[6])):
                hits.append(row)
    if not hits:
        return None
    _, map_id, _, symbol, name, color, _ = max(hits, key=lambda r: (r[2], r[0]))
    spec, sheet = MAPS[map_id], sheet_of(map_id, lon, lat)
    return {"map": map_id + (f"-{sheet}" if sheet else ""), "sheet_ko": spec["sheets"].get(sheet, ""),
            "citation": f"{spec['by']} ({spec['year']})", "unit": symbol, "name": name,
            "age": age_of(symbol), "color": color}


def legend(lang: str = "ko") -> dict:
    """단위(기호·이름·색·시대 — 이름은 원문 값이라 옮기지 않는다)와 구조선 갈래."""
    try:
        rows = _conn().execute("SELECT symbol, name, color FROM units GROUP BY symbol ORDER BY symbol").fetchall()
    except (MarsMapError, sqlite3.Error):
        rows = []
    units = []
    for symbol, name, color in rows:
        age = age_of(symbol)
        period = trek.mars_period(age)
        units.append({"unit": symbol, "label": name, "color": color,
                      "age": (period if lang == "en" else trek.MARS_PERIODS_KO.get(period, "")) if period else ""})
    lines = [{"color": r["color"], "dash": bool(r.get("dash")), "label": r["en"] if lang == "en" else r["ko"]}
             for r in styles()["lines"]]
    return {"units": units, "lines": lines}
