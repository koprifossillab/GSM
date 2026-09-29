"""표고로 나가는 문 — 시료 고도 붙이기(P03)와 3D 의 일본 지형(031).

상류는 셋이고 모두 여기로만 나간다 (CLAUDE.md "상류마다 문이 하나").

| 상류 | 무엇 | 쓰는 곳 | 높이 기준 |
|---|---|---|---|
| AWS Terrain Tiles (Terrarium) | 전 지구 z/x/y PNG, SRTM 약 30 m | 그 밖 전부. 3D 가 브라우저에서 곧장도 부른다 | 해발 (EGM96) |
| 국토지리원 표고 타일 (`dem_png`) | 일본, 기반지도정보 10 m | 일본의 시료, 3D 의 일본 지형 | 해발 (일본 지오이드) |
| PGC ArcticDEM·REMA (ImageServer) | 북위·남위 60° 너머, 2 m 모자이크 | 극지의 시료 | 해발 (`Height Orthometric`) |

**PGC 는 기본값이 타원체고다.** `identify` 에 `Height Orthometric` 을 붙여야 해발이 온다 —
2026-09-29 에 Summit Station 이 3 254 m(타원체고)와 3 210 m(해발, 알려진 값 3 216 m),
McMurdo 가 −39 m 와 14 m 로 갈렸다. `getSamples` 는 여러 점을 한 번에 받지만 이 함수를
듣지 않아 쓰지 않는다. 한 점에 한 번이고, 사이를 둔다.

받은 타일은 `tilecache` 에 담고 스스로 지우지 않는다(007). 자료가 없다는 대답(404)도
담는다 — 한국 자리를 국토지리원에 거듭 묻지 않게.
"""
import io
import logging
import math
import time

import requests
from django.conf import settings
from PIL import Image

from . import tilecache, usage

log = logging.getLogger(__name__)

TERRARIUM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
GSI_DEM_URL = "https://cyberjapandata.gsi.go.jp/xyz/dem_png/{z}/{x}/{y}.png"
PGC_URL = "https://di-pgc.img.arcgis.com/arcgis/rest/services/{service}/ImageServer/identify"

#: 시료에 쓰는 줌. Terrarium z12 는 북위 37° 에서 한 픽셀 30 m 남짓 — SRTM 해상도다.
#: 국토지리원 `dem_png` 는 z14 가 끝이고 10 m 격자다
TERRARIUM_ZOOM = 12
GSI_ZOOM = 14
#: 이 위도 너머는 PGC 에 묻는다
POLAR_LAT = 60.0
#: PGC 에 묻는 사이(초). 한 점에 한 번이라 한도를 재지 않는 빠르기로 간다(010)
PGC_PAUSE = 0.2

#: 출처 → (화면에 적는 이름, 높이 기준). 값은 `Point.elev_source`·`elev_datum` 에 든다
SOURCES = {
    "aws-terrarium-z12": ("AWS Terrain Tiles (SRTM 등, z12)", "egm96"),
    "gsi-dem-10m": ("국토지리원 표고 타일 (10 m)", "gsi-geoid"),
    "pgc-arcticdem-2m": ("PGC ArcticDEM (2 m, 해발)", "pgc-orthometric"),
    "pgc-rema-2m": ("PGC REMA (2 m, 해발)", "pgc-orthometric"),
}


class ElevationError(RuntimeError):
    pass


def _get(url: str, upstream: str, **kwargs):
    left = usage.paused()
    if left:
        raise ElevationError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, timeout=settings.UPSTREAM_TIMEOUT, verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"}, **kwargs)
    except requests.RequestException as exc:
        usage.record(upstream, ok=False)
        raise ElevationError(f"{upstream} 에 닿지 못했다: {exc}") from exc
    usage.record(upstream, ok=r.status_code in (200, 404),
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


# ── 타일 ────────────────────────────────────────────────────────────

#: 자료가 없다는 대답을 담아 두는 표식
_NONE = b"none"


def _tile(kind: str, url: str, upstream: str, z: int, x: int, y: int):
    """타일 한 장(PNG 바이트). 그 자리에 자료가 없으면 None."""
    key = tilecache.key_text("elev", f"{kind}/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return None if hit == _NONE else hit
    r = _get(url.format(z=z, x=x, y=y), upstream)
    if r.status_code == 404:
        tilecache.put(key, _NONE)
        return None
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise ElevationError(f"{upstream} 가 표고 타일을 주지 않았다 (status={r.status_code})")
    tilecache.put(key, r.content)
    return r.content


def terrarium_tile(z, x, y):
    return _tile("terrarium", TERRARIUM_URL, "aws", z, x, y)


def gsi_tile(z, x, y):
    return _tile("gsi-dem", GSI_DEM_URL, "gsi", z, x, y)


def terrarium_value(rgb) -> float:
    r, g, b = rgb[:3]
    return r * 256 + g + b / 256 - 32768


def gsi_value(rgb):
    """국토지리원 `dem_png` 한 픽셀 → m. (128,0,0) 은 자료 없음, 2^23 넘는 것은 음수다."""
    v = rgb[0] * 65536 + rgb[1] * 256 + rgb[2]
    if v == 2 ** 23:
        return None
    if v > 2 ** 23:
        v -= 2 ** 24
    return v * 0.01


def tile_xy(lat: float, lon: float, z: int) -> tuple:
    """위경도 → 줌 z 의 타일 번호(소수까지)."""
    n = 2 ** z
    lat = max(min(lat, 85.0511), -85.0511)
    x = (lon + 180.0) / 360.0 * n
    rad = math.radians(lat)
    y = (1 - math.log(math.tan(rad) + 1 / math.cos(rad)) / math.pi) / 2 * n
    return x, y


def _sample(image, fx: float, fy: float, decode):
    """타일 안의 소수 픽셀 자리를 네 이웃으로 쌍선형 보간. 이웃에 빈 칸이 있으면 가장 가까운 값."""
    w, h = image.size
    px, py = fx * w - 0.5, fy * h - 0.5
    x0, y0 = max(0, min(w - 1, int(math.floor(px)))), max(0, min(h - 1, int(math.floor(py))))
    x1, y1 = min(w - 1, x0 + 1), min(h - 1, y0 + 1)
    tx, ty = min(max(px - x0, 0.0), 1.0), min(max(py - y0, 0.0), 1.0)
    vals = [decode(image.getpixel((x, y))) for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1))]
    if any(v is None for v in vals):
        near = decode(image.getpixel((min(w - 1, max(0, round(px))), min(h - 1, max(0, round(py))))))
        return near
    top = vals[0] * (1 - tx) + vals[1] * tx
    bottom = vals[2] * (1 - tx) + vals[3] * tx
    return top * (1 - ty) + bottom * ty


def _from_tiles(points: dict, z: int, fetch, decode) -> dict:
    """{번호: (위도, 경도)} → {번호: m}. 타일마다 한 번만 받는다."""
    by_tile = {}
    for key, (lat, lon) in points.items():
        fx, fy = tile_xy(lat, lon, z)
        by_tile.setdefault((int(fx), int(fy)), []).append((key, fx % 1, fy % 1))
    out = {}
    for (x, y), items in by_tile.items():
        data = fetch(z, x, y)
        if not data:
            continue
        image = Image.open(io.BytesIO(data)).convert("RGB")
        for key, fx, fy in items:
            value = _sample(image, fx, fy, decode)
            if value is not None:
                out[key] = value
    return out


# ── PGC ─────────────────────────────────────────────────────────────

def pgc_value(lat: float, lon: float):
    """PGC 모자이크의 해발 한 점. 자료 밖이면 None."""
    service = "arcticdem_latest" if lat > 0 else "rema_latest"
    r = _get(PGC_URL.format(service=service), "pgc", params={
        "geometry": f'{{"x":{lon},"y":{lat},"spatialReference":{{"wkid":4326}}}}',
        "geometryType": "esriGeometryPoint", "renderingRule": '{"rasterFunction":"Height Orthometric"}',
        "returnGeometry": "false", "returnCatalogItems": "false", "f": "json"})
    if r.status_code != 200:
        raise ElevationError(f"PGC 가 받지 않았다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise ElevationError("PGC 가 JSON 이 아닌 것을 주었다") from exc
    if "error" in data:
        raise ElevationError(f"PGC 의 오류: {data['error'].get('message', '')}")
    try:
        return float(data.get("value"))
    except (TypeError, ValueError):
        return None                                    # "NoData"


# ── 점마다 고른다 ────────────────────────────────────────────────────

def in_japan(lat: float, lon: float) -> bool:
    """국토지리원에 물을 만한 자리. 한국의 동해안·부산·울릉도·독도는 뺀다 — 물어도
    404 라 헛걸음이다. 빼지 못한 것은 404 가 걸러 AWS 로 넘어간다."""
    if not (122.9 <= lon <= 154.0 and 20.0 <= lat <= 45.6):
        return False
    if lon < 129.0:
        return False
    if lat > 35.0 and lon < 129.7:
        return False                                   # 한반도 동남해안
    if 130.7 <= lon <= 131.95 and 37.1 <= lat <= 37.6:
        return False                                   # 울릉도·독도
    return True


def elevations(points: dict, pause: float = PGC_PAUSE) -> dict:
    """{번호: (위도, 경도)} → {번호: (m, 출처)}. 못 읽은 점은 빠진다.

    극지는 PGC, 일본은 국토지리원, 나머지와 앞의 둘이 못 준 것은 AWS 다."""
    out, rest = {}, {}
    polar = {k: p for k, p in points.items() if abs(p[0]) >= POLAR_LAT}
    for index, (key, (lat, lon)) in enumerate(polar.items()):
        if index and pause:
            time.sleep(pause)
        value = pgc_value(lat, lon)
        if value is not None:
            out[key] = (value, "pgc-arcticdem-2m" if lat > 0 else "pgc-rema-2m")
    japan = {k: p for k, p in points.items() if k not in polar and in_japan(*p)}
    for key, value in _from_tiles(japan, GSI_ZOOM, gsi_tile, gsi_value).items():
        out[key] = (value, "gsi-dem-10m")
    rest = {k: p for k, p in points.items() if k not in out}
    for key, value in _from_tiles(rest, TERRARIUM_ZOOM, terrarium_tile, terrarium_value).items():
        out[key] = (value, "aws-terrarium-z12")
    return out


def _pixels(image):
    """픽셀 차례대로. Pillow 14 에서 `getdata` 가 없어진다."""
    flat = getattr(image, "get_flattened_data", None)
    return flat() if flat else image.getdata()


# ── 3D 의 일본 지형 ──────────────────────────────────────────────────

def japan_terrarium(z: int, x: int, y: int):
    """국토지리원 `dem_png` 를 Terrarium 인코딩으로 옮긴 타일. 일본 밖이면 None.

    빈 칸(바다·자료 밖)은 같은 자리의 AWS 값으로 메운다 — 그대로 두면 3D 에서
    (128,0,0) 이 8 만 m 로 솟는다. 담아 두고 다시 만들지 않는다."""
    key = tilecache.key_text("elev", f"gsi-terrarium/{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return None if hit == _NONE else hit
    data = gsi_tile(z, x, y)
    if not data:
        tilecache.put(key, _NONE)
        return None
    gsi = Image.open(io.BytesIO(data)).convert("RGB")
    fill = None
    out = []
    for index, px in enumerate(_pixels(gsi)):
        value = gsi_value(px)
        if value is None:
            if fill is None:
                aws = terrarium_tile(z, x, y)
                fill = list(_pixels(Image.open(io.BytesIO(aws)).convert("RGB"))) if aws else []
            if not fill:
                out.append((128, 0, 0))                # AWS 도 없다 — 해수면(0 m)
                continue
            out.append(fill[index])
            continue
        v = value + 32768
        r, rem = divmod(v, 256)
        g = int(rem)
        b = int(round((rem - g) * 256))
        if b == 256:
            g, b = g + 1, 0
        out.append((int(r), g, b))
    image = Image.new("RGB", gsi.size)
    image.putdata(out)
    buf = io.BytesIO()
    image.save(buf, "PNG")
    png = buf.getvalue()
    tilecache.put(key, png)
    return png
