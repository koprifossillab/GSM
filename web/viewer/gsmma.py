"""대만 경제부 지질조사·광업관리중심(GSMMA)으로 나가는 문 — 대만 지질도 (wetherilli 136).

대만 레이어는 여기로만 나간다 (CLAUDE.md "상류마다 문이 하나"). 같은 기관의 호스트 둘을 이 문 하나가 맡는다.

- **그림** — `geomap.gsmma.gov.tw` 의 MapGuide WMS. 열쇠가 없다. **EPSG:4326 만 받는다** — 3857·3826(대만 TM2)로
  물으면 `InvalidCRS` 다(2026-10-02). 그래서 화면은 4326 격자로 받아 옮겨 그린다(`map.js` 의 `taiwanSource`).
  레이어가 지층·경계·단층처럼 잘게 나뉘어 있어, 카탈로그의 레이어 하나가 상류 레이어 여럿을 엮는다(`LAYERS`).
  `GetFeatureInfo`(모두 `queryable=0`)와 `GetLegendGraphic`(559)은 주지 않는다
- **속성** — `www.geologycloud.tw` 의 지질운 API(GeoJSON). 1/5만 지층(`Stratum`)과 1/25만 지층(`Stratum25`)을 `bbox` 로
  묻는다. 누른 자리를 가운데 둔 작은 네모(약 20 m)로 묻고, 돌아온 면 가운데 그 점을 품은 것을 고른다
- 조건: 기관의 "정부 웹사이트 자료 개방 선언" — 무상·비독점으로 복제·가공·공중 전송, 상품·서비스 개발까지 허락하고
  **출처를 밝힌다**. 확인한 선언은 같은 기관의 활동단층 사이트(`fault.gsmma.gov.tw/Webservice/Opendata`)의 것이고
  지도 서버에는 따로 붙은 문구가 없다. GetCapabilities 는 `Fees=none`, `AccessConstraints=none`
- 값(지층명·암상)은 중국어 그대로 둔다. 지질시대만 옮긴다(`i18n.age_zh`)
"""
import logging
import math
from types import SimpleNamespace

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

ATTRIBUTION = ('臺灣地質圖 © <a href="https://www.gsmma.gov.tw/" target="_blank" rel="noopener">'
               '經濟部地質調查及礦業管理中心</a>')


class GsmmaError(RuntimeError):
    pass


#: 카탈로그의 레이어 → 상류 레이어(아래부터 위로 겹친다)와 속성을 물을 지질운 API. `info` 가 없으면 누르지 않는다
LAYERS = {
    "gsmma:geology_50k": {"wms": ["50K_Geomap_strata", "50K_Geomap_strata_boundary", "50K_Geomap_fault",
                                  "50K_Geomap_fold"],
                          "info": "Stratum"},
    "gsmma:geology_250k": {"wms": ["250K_Geomap_strata_1974", "250K_Geomap_strata_boundary_1974",
                                   "250K_Geomap_fault_1974"],
                           "info": "Stratum25"},
    "gsmma:geology_500k": {"wms": ["500K_Geomap_strata_2000", "500K_Geomap_boundary_2000", "500K_Geomap_fault_2000",
                                   "500K_Geomap_earthquake_fault_2000"]},
    "gsmma:geology_1m": {"wms": ["1M_Geomap_strata_1986", "1M_Geomap_strata_boundary_1986"]},
    "gsmma:labels_50k": {"wms": ["50K_Geomap_lable", "50K_Geomap_fault_name", "50K_Geomap_fold_name"]},
    "gsmma:attitude_50k": {"wms": ["50K_Geomap_attitude", "50K_Geomap_dip_angle"]},
    "gsmma:active_faults": {"wms": ["25K_Geomap_fault_2021"]},
    "gsmma:tectonic_500k": {"wms": ["500K_Tectonic_map_tectonic_element_1978", "500K_Tectonic_map_fault_1978",
                                    "500K_Tectonic_map_fold_1978",
                                    "500K_Tectonic_map_extinct_or_dormant_volcano_1978"]},
    "gsmma:sheets_50k": {"wms": ["50K_Geomap_index_frame", "50K_Geomap_index_name"]},
}


def knows(name: str) -> bool:
    return name in LAYERS


def queryable(name: str) -> bool:
    return bool(LAYERS.get(name, {}).get("info"))


def _upstream_layers(value: str) -> str:
    """카탈로그 이름(쉼표로 여럿일 수 있다) → MapGuide 레이어 이름들."""
    out = []
    for name in str(value or "").split(","):
        name = name.strip()
        if name not in LAYERS:
            raise GsmmaError(f"모르는 대만 레이어: {name}")
        out.extend("WMS/" + layer for layer in LAYERS[name]["wms"])
    return ",".join(out)


def _get(url: str, params: dict, label: str):
    left = usage.paused()
    if left:
        raise GsmmaError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gsmma", ok=False)
        raise GsmmaError(f"대만 {label} 에 닿지 못했다: {exc}") from exc
    log.info("GSMMA %s -> %s", r.url, r.status_code)
    usage.record("gsmma", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def get_map(params: dict):
    """`GetMap`. (바이트, content-type). 화면이 4326 으로 묻는 것을 그대로 넘기고 레이어 이름만 바꾼다."""
    q = dict(params, service="WMS", request="GetMap")
    q["layers"] = _upstream_layers(q.get("layers"))
    q["styles"] = ""
    r = _get(settings.GSMMA_WMS_URL, q, "지질도 서버")
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GsmmaError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    raise GsmmaError("대만 지질도 서버는 범례를 주지 않는다")


def clicked_lonlat(params: dict):
    """WMS `GetFeatureInfo` 의 범위·크기·픽셀 → 누른 자리의 (경도, 위도). 화면은 4326 으로 묻는다 —
    1.3.0 이면 범위가 위도부터다. 3857 로 온 것도 받는다."""
    srs = (params.get("srs") or params.get("crs") or "EPSG:4326").upper()
    bbox = [float(v) for v in str(params.get("bbox", "")).split(",")]
    width, height = float(params.get("width", 256)), float(params.get("height", 256))
    i = float(params.get("i", params.get("x", width / 2)))
    j = float(params.get("j", params.get("y", height / 2)))
    if srs in ("EPSG:4326", "CRS:84"):
        if srs == "EPSG:4326" and str(params.get("version", "1.3.0")).startswith("1.3"):
            bbox = [bbox[1], bbox[0], bbox[3], bbox[2]]
        return bbox[0] + (bbox[2] - bbox[0]) * i / width, bbox[3] - (bbox[3] - bbox[1]) * j / height
    x = bbox[0] + (bbox[2] - bbox[0]) * i / width
    y = bbox[3] - (bbox[3] - bbox[1]) * j / height
    r = 6378137.0
    return math.degrees(x / r), math.degrees(2 * math.atan(math.exp(y / r)) - math.pi / 2)


def _inside(lon: float, lat: float, ring) -> bool:
    """점이 고리(경위도 쌍의 목록) 안에 드나 — 반직선을 세는 셈."""
    hit = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def contains(geometry: dict, lon: float, lat: float) -> bool:
    """GeoJSON 의 면(Polygon·MultiPolygon)이 점을 품나. 구멍은 뺀다."""
    kind = (geometry or {}).get("type")
    coords = (geometry or {}).get("coordinates") or []
    polygons = [coords] if kind == "Polygon" else coords if kind == "MultiPolygon" else []
    for rings in polygons:
        rings = [[tuple(p[:2]) for p in ring] for ring in rings if ring]
        if rings and _inside(lon, lat, rings[0]) and not any(_inside(lon, lat, hole) for hole in rings[1:]):
            return True
    return False


#: 지질운의 지층 속성 → 팝업에 보일 이름. 도식 번호(`Code`)는 사람에게 뜻이 없어 버린다
FRIENDLY = {"Name": "지층명", "Abbrev": "기호", "Time": "지질시대", "Note": "암상"}


def get_feature_info(params: dict) -> dict:
    """누른 자리의 지층 — 지질운 API 에 약 20 m 네모로 묻고, 그 점을 품은 면만 남긴다(없으면 네모에 걸린 것)."""
    layer = (params.get("query_layers") or params.get("layers") or "").split(",")[0].strip()
    api = LAYERS.get(layer, {}).get("info")
    if not api:
        return {"features": []}
    lon, lat = clicked_lonlat(params)
    half = 0.0001
    r = _get(f"{settings.GSMMA_API_URL}/{api}",
             {"bbox": f"{lon - half:.6f},{lat - half:.6f},{lon + half:.6f},{lat + half:.6f}"}, "지질운")
    if r.status_code != 200:
        raise GsmmaError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        found = r.json().get("features") or []
    except ValueError as exc:
        raise GsmmaError("지질운이 JSON 이 아닌 것을 주었다") from exc
    inside = [f for f in found if contains(f.get("geometry"), lon, lat)]
    features = []
    for n, feature in enumerate(inside or found):
        props = {key: str(value).strip() for key, value in (feature.get("properties") or {}).items()
                 if key in FRIENDLY and value not in (None, "")}
        features.append({"id": f"gsmma.{api}.{n}", "properties": props})
    return {"features": features}


def friendly(props: dict, lang: str = "ko") -> dict:
    """지질운의 열 이름 → 팝업 이름. 지질시대는 중국어에서 옮긴다(영어판은 영어로)."""
    out = {}
    for key, value in props.items():
        if key == "Time":
            value = i18n.age_zh(value, lang)
        out[FRIENDLY.get(key, key)] = value
    return out


#: `views._Door` 가 쓰는 꼴
DOOR = SimpleNamespace(get_map=get_map, get_feature_info=get_feature_info, get_legend=get_legend)
