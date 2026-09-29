"""NASA Trek 으로 나가는 문 — 달·화성의 지질도·표고·지명.

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

**화성도 이 문이다**(058). Mars Trek 은 같은 NASA Trek 의 다른 몸이라(`settings.TREK_MARS_URL`,
`trek.nasa.gov/mars`) 문을 새로 내지 않았다 — 아래 "화성" 마디가 `mars_*` 로 같은 일을 한다.
화성 경위도는 ESRI `104905`(GCS_Mars_2000)이고 격자는 달과 같다.
"""
import io
import json
import logging
import math
import re

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

def _get(path: str, params: dict, base: str = ""):
    url = f"{(base or settings.TREK_URL).rstrip('/')}/{path.lstrip('/')}"
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("trek", ok=False)
        raise TrekError(f"NASA Trek 에 닿지 못했다: {exc}") from exc
    log.info("trek %s -> %s", r.url, r.status_code)
    usage.record("trek", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _json(r) -> dict:
    if r.status_code != 200:
        raise TrekError(f"NASA Trek 이 받지 않았다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise TrekError("NASA Trek 이 JSON 이 아닌 것을 주었다") from exc
    # ArcGIS 는 잘못된 요청에도 200 에 {"error": …} 를 싣는다
    if isinstance(data, dict) and "error" in data:
        raise TrekError(f"NASA Trek 의 오류: {data['error'].get('message', '')}")
    return data


def _map(layer: str, op: str) -> str:
    if layer not in LAYERS:
        raise TrekError("달 지질 레이어가 아니다")
    return f"trekarcgis3/rest/services/{LAYERS[layer]}/MapServer/{op}"


def _image(r) -> bytes:
    kind = r.headers.get("Content-Type") or r.headers.get("content-type") or ""
    if r.status_code != 200 or not kind.startswith("image/"):
        raise TrekError(f"NASA Trek 이 그림을 주지 않았다 (status={r.status_code}, {kind})")
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
            label = item.get("label") or ""
            unit = _unit_of(label)
            out.append({"label": label, "unit": unit, "age": age_of_unit(unit),
                        "image": f"data:{item.get('contentType') or 'image/png'};base64,{image}"})
    return out


_UNIT = re.compile(r"\(([^()]+)\)\s*$")
#: 단위 기호의 머리글자 → 시대. `EIp`·`INt` 처럼 둘에 걸친 것은 앞 글자(더 젊은 쪽)로 묶는다
_AGE_HEAD = {"C": "Copernican", "E": "Eratosthenian", "I": "Imbrian", "N": "Nectarian"}


def _unit_of(label: str) -> str:
    """범례 이름 끝의 기호 — "Copernican Crater (Cc)" → "Cc"."""
    m = _UNIT.search(label)
    return m.group(1).strip() if m else ""


def age_of_unit(unit: str) -> str:
    if unit.startswith("pN"):
        return "Pre-Nectarian"
    return _AGE_HEAD.get(unit[:1], "")


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


# ── 착륙·충돌 지점 (046) ─────────────────────────────────────────────
#
# Trek 의 `Lunar_Landing_Impact_Sites` MapServer — 갈래마다 레이어 하나다(충돌·연착륙·유인 착륙·로버).
# 모두 합쳐 백 곳이 안 된다. 한 번에 통째로 받는다 — 이 서버는 쪽 나누기(`resultRecordCount`)를 받지 않는다.
# 좌표는 달 경위도(GCS_Moon)이고, 속성에 우주선 이름·날짜·NSSDC 링크가 있다

LANDING_SERVICE = "trekarcgis2/rest/services/Lunar_Landing_Impact_Sites/MapServer"
#: 레이어 번호 → 갈래 (화면이 모양·색을 고르고 이름을 옮긴다)
LANDING_KINDS = {0: "impact", 1: "soft", 2: "crewed", 3: "rover"}


def landing_sites() -> list:
    """`[{"name", "kind", "date", "lon", "lat", "link"}]`."""
    out = []
    for layer, kind in LANDING_KINDS.items():
        data = _json(_get(f"{LANDING_SERVICE}/{layer}/query", {
            "where": "1=1", "outFields": "Spacecraft,Date,Link", "returnGeometry": "true", "f": "json"}))
        for feat in data.get("features") or []:
            geom, attrs = feat.get("geometry") or {}, feat.get("attributes") or {}
            try:
                lon, lat = float(geom["x"]), float(geom["y"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append({"name": str(attrs.get("Spacecraft") or "").strip(), "kind": kind,
                        "date": " ".join(str(attrs.get("Date") or "").split()),
                        "lon": round(lon, 5), "lat": round(lat, 5),
                        "link": str(attrs.get("Link") or "").strip()})
    return out


# ── 지명 ────────────────────────────────────────────────────────────

def fetch_places(body: str = "moon") -> list:
    """색인의 지명과 착륙지 — `[[이름, 갈래, 경도, 위도], …]`. 사람이 부를 때만 간다.

    지명은 `itemType: nomenclature`(IAU 행성 지명 사전을 옮긴 것), 착륙지는 `bookmark`
    (아폴로·루나·창어 …, 화성은 바이킹·큐리오시티 …)다. 경도는 −180–180 으로 맞춘다."""
    mars = body == "mars"
    r = _get("TrekServices/ws/index/eq/searchItems", {
        "proj": f"urn:ogc:def:crs:EPSG::{MARS_SR if mars else SR}", "start": 0, "rows": 100000,
    }, base=settings.TREK_MARS_URL if mars else "")
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
        # 화성의 북마크에는 착륙지 말고도 둘러보기("Major Features")·영화("The Martian Path")가 섞여 있다
        if mars and kind == "bookmark" and not _MARS_LANDING.search(name):
            continue
        # 갈래는 "Lacus, lacūs" 처럼 단수·복수를 적는데, 복수 쪽이 상류에서 글자가 깨져 온다
        # ("lac?à?½s", 2026-09-29). 쉼표 앞의 단수만 쓴다
        # 달은 갈래를 `productType` 에, 화성은 `productCat2` 에 적는다 (2026-09-29)
        group = ("Landing site" if kind == "bookmark"
                 else str(doc.get("productType") or doc.get("productCat2") or "Feature").split(",")[0].strip())
        key = (name.lower(), group)
        if key in seen:
            continue
        seen.add(key)
        lon, lat = point
        out.append([name, group, round(lon, 4), round(lat, 4)])
    out.sort(key=lambda row: row[0].lower())
    return out


_MARS_LANDING = re.compile(r"Landing Site|^Viking \d")


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


# ── 화성 (058) ───────────────────────────────────────────────────────
#
# 달과 같은 틀이다 — 지질도는 MapServer `export`·`identify`·`legend`, 표고는 ImageServer, 착륙지는
# MapServer `query`. 주소만 `settings.TREK_MARS_URL` 밑이고 서비스가 모두 `trekarcgis/` 에 있다.
# 영상 배경(Viking·THEMIS·MOLA 음영·HiRISE)은 달처럼 브라우저가 곧장 부른다.

MARS_ATTRIBUTION = ("Geologic Map of Mars 1:20M (Tanaka et al., 2014, USGS SIM 3292) · "
                    "MOLA–HRSC blended DEM (NASA/GSFC, ESA/DLR/FU Berlin) · via NASA Mars Trek")
#: 상류에 적는 화성 경위도의 코드 (ESRI GCS_Mars_2000). 우리 이름은 `IAU_2015:49900`
MARS_SR = 104905
#: 화성 반지름 (IAU 2015 의 평균 적도 반지름, 구로 다룬다 — 화면의 Cesium 도 구다)
MARS_RADIUS = 3396190.0
MARS_GEOLOGY = "SIM3292_Global_Geology"
#: MOLA 와 HRSC 를 섞은 200 m 표고(S16, 화성 기준면 — 아레오이드 — 에서 잰 높이). **줄인 판(피라미드)이 없어**
#: 넓게 물으면 9 초 걸리거나(90° 네모) 400 을 준다(반구, 2026-09-29). 그래서 멀리서는 MOLA 128 ppd(463 m, 같은
#: 기준면)를 쓴다 — 이쪽은 줄인 판이 있어 어느 넓이든 0.8 초다. 점의 표고(`mars_values`)는 한 점씩이라 늘 200 m
MARS_DEM = "Mars_MOLA_blend200ppx_HRSC_DEM_clon0dd_200mpp_lzw"
MARS_DEM_COARSE = "mola128_mola64_merge_90Nto90S_SimpleC_clon0"
#: 이 줌부터 200 m 판 — 줌 8 의 한 장이 0.7° 네모라 곧 온다
MARS_DEM_FINE_ZOOM = 8
#: 지질도는 1:2000만이라 줌 7(한 픽셀 약 460 m)이면 선이 다 보인다. 가까이 가도 흐리지 않게 11 까지
MARS_MAX_ZOOM = 11
#: 200 m 표고 — 줌 9 의 한 칸(0.35° ÷ 64)이 0.0055°(330 m)로 그쯤이다
MARS_DEM_MAX_ZOOM = 9
#: 화성의 표고는 −8.2 km(헬라스)에서 +21.2 km(올림푸스 몬스)다. 자료 밖은 S16 의 −32768
MARS_ELEV_RANGE = (-9000.0, 22000.0)
MARS_ELEV_SOURCE = "mola-hrsc-200m"
MARS_ELEV_DATUM = "mars-areoid"

MARS_FIELDS = (("Unit", "단위"), ("UnitDesc", "이름"))

#: 화성의 지질시대 — 셋이고 앞에 전기·중기·후기가 붙는다. ICS 밖이라 한글판 표가 없다. 이름은 시대를 딴
#: 땅(노아키스 대지·헤스페리아 평원·아마조니스 평원)을 따라 적었다 — 한국어판만 옮긴다(P05 처럼 사람이 다시 본다)
MARS_PERIODS_KO = {"Amazonian": "아마조니스기", "Hesperian": "헤스페리아기", "Noachian": "노아키스기"}
MARS_EPOCHS_KO = {"Early": "전기", "Middle": "중기", "Late": "후기"}


def mars_age(desc: str) -> str:
    """단위 이름 앞머리의 시대 — "Early Hesperian basin unit" → "Early Hesperian",
    "Amazonian and Hesperian impact unit" → "Amazonian and Hesperian"."""
    words = []
    for word in str(desc or "").split():
        if word in MARS_PERIODS_KO or word in MARS_EPOCHS_KO or (word == "and" and words):
            words.append(word)
        else:
            break
    while words and words[-1] == "and":
        words.pop()
    return " ".join(words)


def mars_period(age: str) -> str:
    """범례를 묶는 머리 — 둘에 걸친 것은 앞의 것(더 젊은 쪽)이다. 달의 `age_of_unit` 과 같은 규칙."""
    for word in age.split():
        if word in MARS_PERIODS_KO:
            return word
    return ""


def mars_age_ko(age: str) -> str:
    """"Early Hesperian" → "헤스페리아기 전기", "Amazonian and Hesperian" → "아마조니스기–헤스페리아기"."""
    parts, epoch = [], ""
    for word in age.split():
        if word in MARS_EPOCHS_KO:
            epoch = MARS_EPOCHS_KO[word]
        elif word in MARS_PERIODS_KO:
            parts.append(f"{MARS_PERIODS_KO[word]} {epoch}".strip())
            epoch = ""
    return "–".join(parts) or age


def _mars(path: str, params: dict):
    return _get(f"trekarcgis/rest/services/{path}", params, base=settings.TREK_MARS_URL)


def mars_tile(z: int, x: int, y: int) -> bytes:
    """화성 지질도 타일 한 장 (256 px PNG). Trek 이 USGS 의 색으로 칠한다."""
    w, s, e, n = tile_bbox(z, x, y)
    return _image(_mars(f"{MARS_GEOLOGY}/MapServer/export", {
        "bbox": f"{w},{s},{e},{n}", "bboxSR": MARS_SR, "imageSR": MARS_SR, "size": f"{TILE},{TILE}",
        "format": "png32", "transparent": "true", "f": "image",
    }))


def mars_identify(lon: float, lat: float) -> dict | None:
    """한 점이 드는 지질 단위 — `{"unit": "eHv", "age": "Early Hesperian", "rows": […]}`. 없으면 None."""
    d = 0.5
    data = _json(_mars(f"{MARS_GEOLOGY}/MapServer/identify", {
        "geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "sr": MARS_SR,
        "layers": "all", "tolerance": 1, "returnGeometry": "false", "f": "json",
        "mapExtent": f"{lon - d},{lat - d},{lon + d},{lat + d}", "imageDisplay": "200,200,96",
    }))
    hits = data.get("results") or []
    if not hits:
        return None
    attrs = hits[0].get("attributes") or {}
    rows = [(label, str(attrs[key]).strip()) for key, label in MARS_FIELDS
            if str(attrs.get(key) or "").strip()]
    return {"unit": str(attrs.get("Unit") or ""), "age": mars_age(attrs.get("UnitDesc") or ""), "rows": rows}


def mars_legend() -> list:
    """단위의 범례 — 이름에 기호가 없어(렌더러가 `UnitDesc` 로 칠한다) 기호는 `query` 로 따로 받아 붙인다."""
    data = _json(_mars(f"{MARS_GEOLOGY}/MapServer/legend", {"f": "json"}))
    codes = {}
    try:
        got = _json(_mars(f"{MARS_GEOLOGY}/MapServer/0/query", {
            "where": "1=1", "outFields": "Unit,UnitDesc", "returnDistinctValues": "true",
            "returnGeometry": "false", "f": "json"}))
        for feat in got.get("features") or []:
            a = feat.get("attributes") or {}
            codes[str(a.get("UnitDesc") or "")] = str(a.get("Unit") or "")
    except TrekError:
        pass                        # 기호가 없어도 범례는 선다
    out = []
    for layer in data.get("layers") or []:
        for item in layer.get("legend") or []:
            image = item.get("imageData")
            if not image:
                continue
            label = item.get("label") or ""
            age = mars_age(label)
            out.append({"label": label, "unit": codes.get(label, ""), "age": mars_period(age),
                        "image": f"data:{item.get('contentType') or 'image/png'};base64,{image}"})
    return out


def mars_dem_tile(z: int, x: int, y: int) -> bytes:
    """화성 표고 격자 한 장 — 65×65 Terrarium PNG. 달의 `dem_tile` 과 같은 수(반 칸 넓혀 묻기)다.
    줌 `MARS_DEM_FINE_ZOOM` 밑은 MOLA 128 ppd, 그 위는 MOLA–HRSC 200 m 다."""
    from PIL import Image

    w, s, e, n = tile_bbox(z, x, y)
    half = (e - w) / (DEM_SIZE - 1) / 2
    service = MARS_DEM if z >= MARS_DEM_FINE_ZOOM else MARS_DEM_COARSE
    r = _mars(f"{service}/ImageServer/exportImage", {
        "bbox": f"{w - half},{s - half},{e + half},{n + half}", "bboxSR": MARS_SR, "imageSR": MARS_SR,
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
    lo, hi = MARS_ELEV_RANGE
    out = Image.new("RGB", (DEM_SIZE, DEM_SIZE))
    out.putdata([_terrarium_rgb(v if lo < v < hi and not math.isnan(v) else 0.0) for v in image.getdata()])
    buf = io.BytesIO()
    out.save(buf, "PNG")
    return buf.getvalue()


def mars_values(points: dict) -> dict:
    """`{id: (lat, lon)}` → `{id: 표고 m}` — 화성 기준면(아레오이드)에서 잰 높이. 달의 `lola_values` 와 같은 길(GET)."""
    ids = list(points)
    out = {}
    lo, hi = MARS_ELEV_RANGE
    for start in range(0, len(ids), SAMPLE_CHUNK):
        chunk = ids[start:start + SAMPLE_CHUNK]
        geometry = {"points": [[round(points[i][1], 6), round(points[i][0], 6)] for i in chunk],
                    "spatialReference": {"wkid": MARS_SR}}
        data = _json(_mars(f"{MARS_DEM}/ImageServer/getSamples", {
            "geometry": json.dumps(geometry), "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true", "interpolation": "RSP_BilinearInterpolation", "f": "json",
        }))
        for sample in data.get("samples") or []:
            try:
                value = float(sample.get("value"))
                index = int(sample.get("locationId"))
            except (TypeError, ValueError):
                continue
            if 0 <= index < len(chunk) and lo < value < hi:
                out[chunk[index]] = value
    return out


#: 착륙선·로버마다 Trek 이 이야기 지점(착륙 자리·열 차폐막·낙하산·들른 곳)을 레이어 하나로 둔다.
#: (서비스, 임무, 갈래) — 갈래는 화면이 색을 고른다
MARS_WAYPOINTS = (
    ("viking_waypoints", "Viking 1", "lander"), ("viking2_waypoints", "Viking 2", "lander"),
    ("sojourner_waypoints", "Mars Pathfinder", "rover"), ("spirit_waypoints", "Spirit", "rover"),
    ("opportunity_waypoints", "Opportunity", "rover"), ("phoenix_waypoints", "Phoenix", "lander"),
    ("curiosity_waypoints", "Curiosity", "rover"), ("InSight_waypoints", "InSight", "lander"),
    ("mars2020_waypoints", "Perseverance", "rover"),
)
#: 로버가 달린 길 — (서비스, 임무). 퍼서비어런스는 솔(sol)마다 선이 갈려 있다
MARS_TRAVERSES = (("spirit_path", "Spirit"), ("opportunity_path", "Opportunity"),
                  ("curiosity_path", "Curiosity"), ("Perseverance_Traverse_Path", "Perseverance"))


def mars_landings() -> list:
    """`[{"name", "mission", "kind", "lon", "lat"}]` — 착륙선·로버의 이야기 지점. 모두 백 곳이 안 된다."""
    out = []
    for service, mission, kind in MARS_WAYPOINTS:
        data = _json(_mars(f"{service}/MapServer/0/query", {
            "where": "1=1", "outFields": "name", "returnGeometry": "true", "f": "json"}))
        for feat in data.get("features") or []:
            geom, attrs = feat.get("geometry") or {}, feat.get("attributes") or {}
            try:
                lon, lat = float(geom["x"]), float(geom["y"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append({"name": str(attrs.get("name") or "").strip(), "mission": mission, "kind": kind,
                        "lon": round(lon, 6), "lat": round(lat, 6)})
    return out


def mars_traverses() -> list:
    """`[{"mission", "paths": [[[lon, lat], …], …]}]` — 로버가 달린 길. 좌표는 여섯째 자리(수 cm)까지."""
    out = []
    for service, mission in MARS_TRAVERSES:
        data = _json(_mars(f"{service}/MapServer/0/query", {
            "where": "1=1", "outFields": "FID", "returnGeometry": "true", "f": "json"}))
        paths = []
        for feat in data.get("features") or []:
            for path in (feat.get("geometry") or {}).get("paths") or []:
                line = [[round(float(p[0]), 6), round(float(p[1]), 6)] for p in path if len(p) >= 2]
                if len(line) >= 2:
                    paths.append(line)
        out.append({"mission": mission, "paths": paths})
    return out
