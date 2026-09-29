"""NASA Moon Trek 으로 나가는 문 — 달의 지질도·표고·지명.

`kigam.py`·`npolar.py` 와 나란한 문이다 (CLAUDE.md "상류마다 문이 하나"). 달의 자료는
여기로만 나간다. 계획은 devlog P05, 고른 까닭은 devlog 036.

주소는 셋이고 모두 `settings.TREK_URL`(`trek.nasa.gov/moon`) 밑이다.

- `trekarcgis3/rest/services/<지질도>/MapServer` — USGS 달 통합 지질도 1:500만(2020)을
  Trek 이 올려 둔 것. 타일(`export`)·속성(`identify`)·범례(`legend`)
- `trekarcgis/rest/services/LRO_LOLA_DEM_Global_128ppd_v04/ImageServer` — LOLA 표고.
  값(F32)을 TIFF 로 받아 Terrarium PNG 로 옮긴다 — 둥근 달의 지형이다
- `TrekServices/ws/index/…` — 색인. 지명(IAU 행성 지명 사전을 옮긴 것)을 받는다.
  사람이 `manage.py fetch_moon_places` 를 부를 때만 간다

**경위도 격자로 받는다.** Trek 의 달 경위도는 ESRI 코드 `104903`(GCS_Moon_2000)이고, 격자는
Cesium 의 `GeographicTilingScheme` 과 같다 — 줌 0 이 가로 2 장·세로 1 장, 한 장이
`180 / 2^z` 도. 우리 이름은 PSDI 표준의 `IAU_2015:30100` 이고(P05 §3), 상류에 물을 때만
`104903` 이라 적는다. 그 바꿈은 이 파일에만 있다.

**표고는 `elevation.py` 가 아니라 여기다.** 그쪽은 지구의 표고로 나가는 문이고, 이것은 Trek 이
주는 것이다 — 상류 하나에 문 하나다. Terrarium 부호화만 같다.

영상 배경(LRO WAC·LOLA 음영 WMTS)은 이 문을 타지 않는다 — 브라우저가 곧장 부른다(EOX 와 같다).
"""
import io
import json
import logging
import math

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

ATTRIBUTION = ("Unified Geologic Map of the Moon 1:5M (Fortezzo et al., 2020, USGS) · "
               "LRO LOLA (NASA/GSFC) · via NASA Moon Trek")
#: 상류에 적는 달 경위도의 코드 (ESRI GCS_Moon_2000)
SR = 104903
#: 달 반지름 (IAU 2015, 구)
RADIUS = 1737400.0

TILE = 256
#: 표고 격자 한 장의 한 변 — Cesium 의 높이 격자 기본값(65×65)
DEM_SIZE = 65
#: 지질도는 1:500만이라 줌 9(한 픽셀 약 130 m) 너머는 같은 선을 크게 그릴 뿐이다.
#: 그래도 가까이 가면 선이 흐려지지 않게 12 까지 받는다
MAX_ZOOM = 12
#: LOLA 128 ppd — 한 픽셀 0.0078°. 줌 8 에서 한 칸(0.7° ÷ 64)이 0.011° 로 그쯤이다
DEM_MAX_ZOOM = 8

#: 우리 이름 → Trek 의 MapServer. `units` 만 속성·범례가 있다
LAYERS = {
    "units": "Unified_Global_Geologic_Map_of_the_Moon_Geologic_Units",
    "contacts": "Unified_Global_Geologic_Map_of_the_Moon_Geologic_Contacts",
    "linear": "Unified_Global_Geologic_Map_of_the_Moon_Linear_Features",
}
DEM_SERVICE = "LRO_LOLA_DEM_Global_128ppd_v04"

#: `identify` 가 주는 열 → 팝업의 이름 (한국어 원문. 영어는 `i18n.PROP_EN`)
FIELDS = (("FIRST_Unit", "단위"), ("FIRST_Un_1", "시대"), ("FIRST_Un_2", "이름"),
          ("UnitDescri", "설명"), ("Interpreta", "해석"))

#: 달의 지질시대 — 값은 다섯 가지다(2026-09-29 `returnDistinctValues` 로 셌다). ICS 밖이라
#: 한글판 표가 없다. 한국어판만 옮긴다 — 영어판은 받은 그대로 (P05 §8, 사람이 다시 본다)
AGES_KO = {
    "Copernican": "코페르니쿠스기",
    "Eratosthenian": "에라토스테네스기",
    "Imbrian": "임브리움기",
    "Nectarian": "넥타리스기",
    "Pre-Nectarian": "선넥타리스기",
}


class TrekError(RuntimeError):
    pass


# ── 격자 ────────────────────────────────────────────────────────────

def valid_tile(z: int, x: int, y: int, max_zoom: int = MAX_ZOOM) -> bool:
    return 0 <= z <= max_zoom and 0 <= x < 2 ** (z + 1) and 0 <= y < 2 ** z


def tile_bbox(z: int, x: int, y: int) -> tuple:
    """경위도 격자 한 장의 (서, 남, 동, 북). y 는 북쪽부터 센다."""
    step = 180.0 / 2 ** z
    west = -180.0 + x * step
    north = 90.0 - y * step
    return west, north - step, west + step, north


# ── 부르기 ──────────────────────────────────────────────────────────

def _get(path: str, params: dict):
    url = f"{settings.TREK_URL.rstrip('/')}/{path.lstrip('/')}"
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("trek", ok=False)
        raise TrekError(f"Moon Trek 에 닿지 못했다: {exc}") from exc
    log.info("trek %s -> %s", r.url, r.status_code)
    usage.record("trek", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _json(r) -> dict:
    if r.status_code != 200:
        raise TrekError(f"Moon Trek 이 받지 않았다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise TrekError("Moon Trek 이 JSON 이 아닌 것을 주었다") from exc
    # ArcGIS 는 잘못된 요청에도 200 에 {"error": …} 를 싣는다
    if isinstance(data, dict) and "error" in data:
        raise TrekError(f"Moon Trek 의 오류: {data['error'].get('message', '')}")
    return data


def _map(layer: str, op: str) -> str:
    if layer not in LAYERS:
        raise TrekError("달 지질 레이어가 아니다")
    return f"trekarcgis3/rest/services/{LAYERS[layer]}/MapServer/{op}"


def _image(r) -> bytes:
    kind = r.headers.get("Content-Type") or r.headers.get("content-type") or ""
    if r.status_code != 200 or not kind.startswith("image/"):
        raise TrekError(f"Moon Trek 이 그림을 주지 않았다 (status={r.status_code}, {kind})")
    return r.content


# ── 지질도 ──────────────────────────────────────────────────────────

def get_tile(layer: str, z: int, x: int, y: int) -> bytes:
    """지질도 타일 한 장 (256 px PNG). Trek 이 공식 색으로 칠한다."""
    w, s, e, n = tile_bbox(z, x, y)
    return _image(_get(_map(layer, "export"), {
        "bbox": f"{w},{s},{e},{n}", "bboxSR": SR, "imageSR": SR, "size": f"{TILE},{TILE}",
        "format": "png32", "transparent": "true", "f": "image",
    }))


def identify(lon: float, lat: float) -> dict | None:
    """한 점이 드는 지질 단위. 없으면 None.

    돌려주는 것은 `{"unit": "Im2", "age": "Imbrian", "rows": [(한국어 이름, 값), …]}` —
    값은 옮기지 않는다(CLAUDE.md "영어판"). 시대만 부르는 쪽이 옮긴다."""
    d = 0.5
    data = _json(_get(_map("units", "identify"), {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": SR,
        "layers": "all", "tolerance": 1, "returnGeometry": "false", "f": "json",
        "mapExtent": f"{lon - d},{lat - d},{lon + d},{lat + d}", "imageDisplay": "200,200,96",
    }))
    hits = data.get("results") or []
    if not hits:
        return None
    attrs = hits[0].get("attributes") or {}
    rows = [(label, str(attrs[key]).strip()) for key, label in FIELDS
            if str(attrs.get(key) or "").strip()]
    return {"unit": attrs.get("FIRST_Unit") or "", "age": attrs.get("FIRST_Un_1") or "", "rows": rows}


def legend() -> list:
    """단위 49 가지의 범례 — `[{"label": "Copernican Crater (Cc)", "image": "data:image/png;base64,…"}]`."""
    data = _json(_get(_map("units", "legend"), {"f": "json"}))
    out = []
    for layer in data.get("layers") or []:
        for item in layer.get("legend") or []:
            image = item.get("imageData")
            if not image:
                continue
            out.append({"label": item.get("label") or "",
                        "image": f"data:{item.get('contentType') or 'image/png'};base64,{image}"})
    return out


# ── 표고 ────────────────────────────────────────────────────────────

def _terrarium_rgb(value: float) -> tuple:
    v = value + 32768
    r, rem = divmod(v, 256)
    g = int(rem)
    b = int(round((rem - g) * 256))
    if b == 256:
        g, b = g + 1, 0
    return (max(0, min(255, int(r))), g, b)


def dem_tile(z: int, x: int, y: int) -> bytes:
    """표고 격자 한 장 — 65×65 Terrarium PNG. 가장자리 점이 이웃 장과 겹치게 받는다.

    ImageServer 의 `exportImage` 는 픽셀의 **가운데**를 잰다. 격자의 첫 점과 끝 점이 장의
    가장자리에 오도록 네모를 반 칸씩 넓혀 묻는다 — 안 그러면 장과 장 사이에 금이 간다."""
    from PIL import Image

    w, s, e, n = tile_bbox(z, x, y)
    half = (e - w) / (DEM_SIZE - 1) / 2
    r = _get(f"trekarcgis/rest/services/{DEM_SERVICE}/ImageServer/exportImage", {
        "bbox": f"{w - half},{s - half},{e + half},{n + half}", "bboxSR": SR, "imageSR": SR,
        "size": f"{DEM_SIZE},{DEM_SIZE}", "format": "tiff", "pixelType": "F32",
        "interpolation": "RSP_BilinearInterpolation", "f": "image",
    })
    try:
        image = Image.open(io.BytesIO(_image(r)))
        image.load()
    except (OSError, ValueError) as exc:
        raise TrekError(f"표고 TIFF 를 읽지 못했다: {exc}") from exc
    if image.mode != "F" or image.size != (DEM_SIZE, DEM_SIZE):
        raise TrekError(f"표고의 꼴이 다르다 ({image.mode}, {image.size})")
    values = list(image.getdata())
    out = Image.new("RGB", (DEM_SIZE, DEM_SIZE))
    # 자료 밖(아주 큰 음수)은 0 m 로 둔다 — 구멍보다 평평한 것이 낫다
    out.putdata([_terrarium_rgb(v if -20000 < v < 20000 and not math.isnan(v) else 0.0) for v in values])
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


# ── 점의 표고 (037) ──────────────────────────────────────────────────
#
# 달 점묶음의 ⛰. 지구의 `elevation.elevations` 와 같은 자리다. `getSamples` 가 여러 점을 한 번에
# 받는다. **POST 는 403 이다**(2026-09-29 — Trek 앞의 방화벽) — GET 으로, 주소가 길어지지 않게
# 한 번에 `SAMPLE_CHUNK` 점씩(100 점이 3 KB 남짓).

#: 출처 이름과 높이 기준. `pointsets.ELEV_DATUMS` 에도 적는다
ELEV_SOURCE = "lola-128ppd"
ELEV_DATUM = "moon-sphere"
SAMPLE_CHUNK = 100


def lola_values(points: dict) -> dict:
    """`{id: (lat, lon)}` → `{id: 표고 m}`. 반지름 1 737.4 km 구에서 잰 높이다. 못 읽은 점은 빠진다."""
    ids = list(points)
    out = {}
    for start in range(0, len(ids), SAMPLE_CHUNK):
        chunk = ids[start:start + SAMPLE_CHUNK]
        geometry = {"points": [[round(points[i][1], 6), round(points[i][0], 6)] for i in chunk],
                    "spatialReference": {"wkid": SR}}
        data = _json(_get(f"trekarcgis/rest/services/{DEM_SERVICE}/ImageServer/getSamples", {
            "geometry": json.dumps(geometry), "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true", "interpolation": "RSP_BilinearInterpolation", "f": "json",
        }))
        for sample in data.get("samples") or []:
            try:
                value = float(sample.get("value"))
                index = int(sample.get("locationId"))
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(chunk) and -20000 < value < 20000:
                out[chunk[index]] = value
    return out


# ── 지명 ────────────────────────────────────────────────────────────

def fetch_places() -> list:
    """색인의 지명과 착륙지 — `[[이름, 갈래, 경도, 위도], …]`. 사람이 부를 때만 간다.

    지명은 `itemType: nomenclature`(IAU 행성 지명 사전을 옮긴 것), 착륙지는 `bookmark`
    (아폴로·루나·창어 …)다. 경도는 −180–180 으로 맞춘다."""
    r = _get("TrekServices/ws/index/eq/searchItems", {
        "proj": "urn:ogc:def:crs:EPSG::104903", "start": 0, "rows": 100000,
    })
    docs = (_json(r).get("response") or {}).get("docs") or []
    out, seen = [], set()
    for doc in docs:
        kind = doc.get("itemType")
        if kind not in ("nomenclature", "bookmark"):
            continue
        name = str(doc.get("title") or "").strip()
        point = _center(doc)
        if not name or point is None:
            continue
        # 갈래는 "Lacus, lacūs" 처럼 단수·복수를 적는데, 복수 쪽이 상류에서 글자가 깨져 온다
        # ("lac?à?½s", 2026-09-29). 쉼표 앞의 단수만 쓴다
        group = ("Landing site" if kind == "bookmark"
                 else str(doc.get("productType") or "Feature").split(",")[0].strip())
        key = (name.lower(), group)
        if key in seen:
            continue
        seen.add(key)
        lon, lat = point
        out.append([name, group, round(lon, 4), round(lat, 4)])
    out.sort(key=lambda row: row[0].lower())
    return out


def _center(doc: dict):
    bbox = str(doc.get("bbox") or "")
    try:
        w, s, e, n = (float(v) for v in bbox.split(","))
    except ValueError:
        return None
    lon, lat = (w + e) / 2, (s + n) / 2
    if lon > 180:
        lon -= 360
    if not (-180 <= lon <= 180 and -90 <= lat <= 90):
        return None
    return lon, lat


def search_places(places: list, query: str, limit: int = 12) -> list:
    """이름으로 찾는다. 앞이 맞는 것이 먼저, 그다음 들어 있는 것. 대소문자를 가리지 않는다."""
    q = query.strip().lower()
    if not q:
        return []
    head = [p for p in places if p[0].lower().startswith(q)]
    rest = [p for p in places if q in p[0].lower() and not p[0].lower().startswith(q)]
    # 착륙지는 앞에 — "Apollo" 를 치면 크레이터 Apollo 보다 착륙지가 먼저다
    head.sort(key=lambda p: (p[1] != "Landing site", len(p[0])))
    return [{"name": p[0], "kind": p[1], "lon": p[2], "lat": p[3]} for p in (head + rest)[:limit]]


def load_places(path) -> list:
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return []
    return data.get("places") or []
