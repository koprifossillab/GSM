"""호주 주 지질조사소로 나가는 문 — 퀸즐랜드(GSQ)·빅토리아(GSV)·남호주(GSSA) (wetherilli 225).

GA(`ga.py`)가 대륙 전체의 1:250만·1:100만을 그린다면, 여기는 주가 내는 더 자세한 판이다. 주마다 서버가 따로라 BGS 문(`bgs.py`)이
GSNI·AGA·GSN 을 함께 내듯 한 파일에 셋을 둔다 — 상류 이름(`gsq`·`gsv`·`gssa`)은 따로다. 셋 다 열쇠가 없고 3857 로 그린다.
조건은 셋 다 **CC BY 4.0** 이다 — 남호주는 Capabilities 의 AccessConstraints 가, 퀸즐랜드·빅토리아는 주 열린자료 목록
(data.qld.gov.au "Queensland geology detailed web map service", discover.data.vic.gov.au "Geological polygons (1:250,000)")이 그렇게 적는다.

- **퀸즐랜드** — `spatial-gis.information.qld.gov.au/arcgis/rest/services/GeoscientificInformation/` 의 `GeologyState`(1:200만, 레이어 6)·
  `GeologyDetailed`(1:10만, 레이어 15 — 1:150만보다 가까울 때만 그린다). WMS 의 레이어 이름에 숫자 꼬리가 붙어
  (`State_Surface_Geology55055`) 판을 다시 올리면 바뀔 수 있다 — REST `export`·`identify` 를 번호로 부른다(남아공 `cgs.py` 와 같은 수)
- **빅토리아** — `opendata.maps.vic.gov.au/geoserver/wms` 의 이음매 없는 지질도(`sg_geological_unit_250k`·`_50k`, GeoSciML 포트레이얼).
  넓게 보면 한 장이 12 초라 가까이서만. 범례는 SGB 처럼 보는 범위의 칸만 JSON 으로 받는다(`hideEmptyRules`) — 이름이 칸에 붙어 온다
- **남호주** — `sarigdata.pir.sa.gov.au/geoserver/ows` 의 `gsmlp:GeologicUnitView`. 1:250만보다 넓으면 빈 그림이다. JSON 범례는 빈 것이 온다
- 속성은 셋 다 JSON. GeoServer 둘은 기하가 따라와 무거워(빅토리아 한 점 38 KB) `propertyName` 으로 열만 받는다
"""
import logging
import math
import re

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)


class AuStatesError(RuntimeError):
    pass


class _NS:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _get(upstream: str, url: str, params: dict, timeout: int = 45):
    left = usage.paused()
    if left:
        raise AuStatesError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(url, params=params, timeout=max(settings.UPSTREAM_TIMEOUT, timeout),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record(upstream, ok=False)
        raise AuStatesError(f"{upstream.upper()} 에 닿지 못했다: {exc}") from exc
    log.info("%s %s -> %s", upstream.upper(), r.url, r.status_code)
    usage.record(upstream, ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _one(params: dict, layers: dict, *keys) -> str:
    for key in keys:
        names = [n.strip() for n in str(params.get(key) or "").split(",") if n.strip()]
        if names:
            if len(names) != 1 or names[0] not in layers:
                raise AuStatesError(f"모르는 레이어다: {names}")
            return names[0]
    raise AuStatesError("레이어가 없다")


def _text(value) -> str:
    text = " ".join(str("" if value is None else value).split())
    return "" if text.lower() in ("null", "none", "-999") else text


# ── 지질시대 — GeoSciML 의 ICS 주소 꼬리(`LowerOrdovician`)를 ICS 영어 이름으로 ─────────

_SERIES = {"Lower": "Early", "Upper": "Late"}


def age_of_uri(uri: str) -> str:
    """`…/ischart/LowerOrdovician` → `Early Ordovician`. ICS 의 계(Series) 이름은 Lower·Upper 라 `i18n.age_ko` 가 아는 Early·Late 로 바꾼다."""
    tail = str(uri or "").rstrip("/").rsplit("/", 1)[-1]
    words = re.findall(r"[A-Z][a-z]+|[a-z]+", tail)
    if not words:
        return ""
    if len(words) == 2 and words[0] in _SERIES:
        words[0] = _SERIES[words[0]]
    return " ".join(w.capitalize() for w in words)


def _span(old: str, young: str, lang: str) -> str:
    age = old if old == young or not young else (young if not old else f"{old} - {young}")
    return i18n.age_ko(age) if lang == "ko" and age else age


# ── 퀸즐랜드 GSQ — ArcGIS REST ───────────────────────────────────────

GSQ_ATTRIBUTION = ('<a href="https://www.business.qld.gov.au/industries/mining-energy-water/resources/geoscience-information/gsq" '
                   'target="_blank" rel="noopener">© State of Queensland</a> (Geological Survey of Queensland, CC BY 4.0)')
#: 레이어 → (서비스, REST 레이어 번호, 처음 그리는 줌)
GSQ_LAYERS = {
    "gsq:state": ("GeologyState", 6, None),
    "gsq:detailed": ("GeologyDetailed", 15, 9),
}


def _box(params: dict) -> tuple:
    try:
        box = tuple(float(v) for v in str(params.get("bbox", "")).split(","))
    except ValueError as exc:
        raise AuStatesError("BBOX 를 읽지 못했다") from exc
    if len(box) != 4:
        raise AuStatesError("BBOX 를 읽지 못했다")
    return box


def _size(params: dict) -> tuple:
    try:
        w, h = int(params.get("width") or 256), int(params.get("height") or 256)
    except ValueError as exc:
        raise AuStatesError("크기를 읽지 못했다") from exc
    if not (0 < w <= 2048 and 0 < h <= 2048):
        raise AuStatesError("크기가 지나치다")
    return w, h


def _merc(params: dict):
    code = str(params.get("crs") or params.get("srs") or "EPSG:3857").upper()
    if code not in ("EPSG:3857", "EPSG:900913"):
        raise AuStatesError(f"3857 만 받는다: {code}")


def _gsq_url(name: str, op: str) -> str:
    return f"{settings.GSQ_REST_URL.rstrip('/')}/{GSQ_LAYERS[name][0]}/MapServer/{op}"


def gsq_get_map(params: dict):
    name = _one(params, GSQ_LAYERS, "layers")
    _merc(params)
    box, (w, h) = _box(params), _size(params)
    r = _get("gsq", _gsq_url(name, "export"), {
        "bbox": ",".join(repr(v) for v in box), "bboxSR": 3857, "imageSR": 3857, "size": f"{w},{h}", "dpi": 96,
        "format": "png32", "transparent": "true", "layers": f"show:{GSQ_LAYERS[name][1]}", "f": "image"})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise AuStatesError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def gsq_get_feature_info(params: dict) -> dict:
    name = _one(params, GSQ_LAYERS, "query_layers", "layers")
    _merc(params)
    box, (w, h) = _box(params), _size(params)
    try:
        i = float(params.get("i", params.get("x")))
        j = float(params.get("j", params.get("y")))
    except (TypeError, ValueError) as exc:
        raise AuStatesError("누른 자리를 읽지 못했다") from exc
    x = box[0] + (i + 0.5) * (box[2] - box[0]) / w
    y = box[3] - (j + 0.5) * (box[3] - box[1]) / h
    r = _get("gsq", _gsq_url(name, "identify"), {
        "geometry": f"{x!r},{y!r}", "geometryType": "esriGeometryPoint", "sr": 3857,
        "layers": f"visible:{GSQ_LAYERS[name][1]}", "tolerance": 2, "mapExtent": ",".join(repr(v) for v in box),
        "imageDisplay": f"{w},{h},96", "returnGeometry": "false", "f": "json"})
    if r.status_code != 200:
        raise AuStatesError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        results = r.json().get("results") or []
    except ValueError as exc:
        raise AuStatesError("속성이 JSON 이 아니다") from exc
    return {"features": [{"id": f"gsq.{(x.get('attributes') or {}).get('OBJECTID', n)}", "properties": x.get("attributes") or {}}
                         for n, x in enumerate(results[:3])]}


def gsq_get_legend(layer: str):
    raise AuStatesError("퀸즐랜드 범례는 아직 없다")


def gsq_friendly(props: dict, lang: str = "ko") -> dict:
    """identify 의 열은 사람이 읽는 이름이다(`Rock Unit Name`). 값은 영어 그대로, 시대(`DEVONIAN - CARBONIFEROUS`)만 옮긴다."""
    v = lambda k: _text(props.get(k))       # noqa: E731
    age = v("Age").title()
    rows = (("기호", v("Map Symbol")), ("이름", v("Rock Unit Name")), ("암석", v("Lithological Summary")),
            ("주 암석", v("Dominant Rock").capitalize()), ("갈래", v("Rock Type").capitalize()),
            ("지질시대", i18n.age_ko(age) if lang == "ko" and age else age))
    return {k: x for k, x in rows if x}


GSQ = _NS(get_map=gsq_get_map, get_feature_info=gsq_get_feature_info, get_legend=gsq_get_legend, friendly=gsq_friendly)


# ── 빅토리아 GSV·남호주 GSSA — GeoServer 의 GeoSciML 포트레이얼 ──────────────

GSV_ATTRIBUTION = ('<a href="https://earthresources.vic.gov.au/geology-exploration" target="_blank" rel="noopener">'
                   '© State of Victoria</a> (Geological Survey of Victoria, CC BY 4.0)')
GSSA_ATTRIBUTION = ('<a href="https://www.energymining.sa.gov.au/industry/geological-survey" target="_blank" rel="noopener">'
                    '© Government of South Australia</a> (Geological Survey of South Australia, SARIG, CC BY 4.0)')
#: 레이어 → (상류 레이어, 처음 그리는 줌)
GSV_LAYERS = {
    "gsv:250k": ("open-data-platform:sg_geological_unit_250k", 8),
    "gsv:50k": ("open-data-platform:sg_geological_unit_50k", 11),
}
GSSA_LAYERS = {
    "gssa:units": ("gsmlp:GeologicUnitView", 9),
}
#: 속성으로 받을 열 — 빅토리아는 작은 글자, 남호주는 낙타 꼴이다
GSV_PROPERTIES = "name,description,rank,lithology,geologichistory,representativeage_uri,representativelowerage_uri,representativeupperage_uri"
GSSA_PROPERTIES = ("name,description,rank,lithology,geologicHistory,numericOlderAge,numericYoungerAge,"
                   "representativeOlderAge_uri,representativeYoungerAge_uri")
#: 범례 칸을 몇 개까지 싣나, 범례를 뜨는 가장 넓은 범위(°)
MAX_LEGEND = 60
LEGEND_SPAN = 4.0


def _gs(upstream: str):
    if upstream == "gsv":
        return settings.GSV_WMS_URL, GSV_LAYERS, GSV_PROPERTIES
    return settings.GSSA_WMS_URL, GSSA_LAYERS, GSSA_PROPERTIES


def _gs_get_map(upstream: str, params: dict):
    url, layers, _ = _gs(upstream)
    name = _one(params, layers, "layers")
    params = dict(params, service="WMS", request="GetMap", layers=layers[name][0], styles="")
    r = _get(upstream, url, params)
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise AuStatesError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def _gs_get_feature_info(upstream: str, params: dict) -> dict:
    url, layers, columns = _gs(upstream)
    name = _one(params, layers, "query_layers", "layers")
    params = dict(params, service="WMS", request="GetFeatureInfo", layers=layers[name][0], query_layers=layers[name][0],
                  styles="", info_format="application/json", feature_count=3, propertyName=columns)
    r = _get(upstream, url, params)
    if r.status_code != 200:
        raise AuStatesError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        features = r.json().get("features") or []
    except ValueError as exc:
        raise AuStatesError("속성이 JSON 이 아니다") from exc
    return {"features": [{"id": f.get("id"), "properties": f.get("properties") or {}} for f in features]}


def _gs_get_legend(layer: str):
    raise AuStatesError("범례는 보는 범위로만 뜬다")


def gs_friendly(props: dict, lang: str = "ko") -> dict:
    """GeoSciML 포트레이얼의 열(빅토리아는 작은 글자, 남호주는 낙타 꼴). 이름·설명·암석은 영어 그대로, 시대만 옮긴다."""
    low = {str(k).lower(): v for k, v in props.items()}
    v = lambda k: _text(low.get(k))         # noqa: E731
    old = age_of_uri(low.get("representativeolderage_uri") or low.get("representativelowerage_uri")
                     or low.get("representativeage_uri"))
    young = age_of_uri(low.get("representativeyoungerage_uri") or low.get("representativeupperage_uri"))
    ma_old, ma_young = v("numericolderage"), v("numericyoungerage")
    ma = f"{ma_young}–{ma_old}" if ma_old and ma_young and ma_old != ma_young else (ma_old or ma_young)
    rows = (("이름", v("name")), ("설명", v("description")), ("암석", v("lithology")), ("위계", v("rank")),
            ("지질시대", _span(old, young, lang)), ("연대 (Ma)", ma), ("지질 이력", v("geologichistory")))
    return {k: x for k, x in rows if x}


def extent_legend(name: str, bbox_3857: tuple, width: int = 1024, height: int = 768) -> list:
    """빅토리아 — 범위 `(서, 남, 동, 북)`(3857 미터)에 칠해진 칸 `[{"lithology", "color", "count"}]`, 많이 칠해진 것부터.
    GeoServer 가 그 범위를 그려 보고 빈 규칙을 뺀다(`hideEmptyRules`). 규칙 이름이 단위 이름이다 — "Bacchus Marsh Formation (Pxb)" """
    if name not in GSV_LAYERS:
        raise AuStatesError("범례가 없는 레이어다")
    r = _get("gsv", settings.GSV_WMS_URL, {
        "service": "WMS", "version": "1.3.0", "request": "GetLegendGraphic", "format": "application/json",
        "layer": GSV_LAYERS[name][0], "legend_options": "countMatched:true;hideEmptyRules:true",
        "bbox": ",".join(f"{v:.0f}" for v in bbox_3857), "srs": "EPSG:3857", "crs": "EPSG:3857",
        "srcwidth": str(width), "srcheight": str(height)})
    if r.status_code != 200:
        raise AuStatesError(f"범례를 읽지 못했다 (status={r.status_code})")
    try:
        rules = (r.json().get("Legend") or [{}])[0].get("rules") or []
    except (ValueError, AttributeError, IndexError) as exc:
        raise AuStatesError("범례가 JSON 이 아니다") from exc
    out = []
    for rule in rules:
        label = str(rule.get("name") or "").strip()
        fill = next((s["Polygon"].get("fill") for s in rule.get("symbolizers") or [] if "Polygon" in s), None)
        if not label or not fill:
            continue
        title = str(rule.get("title") or "")
        count = int(title.rsplit("(", 1)[1].rstrip(") ")) if title.endswith(")") and "(" in title and \
            title.rsplit("(", 1)[1].rstrip(") ").isdigit() else 0
        out.append({"symbol": "", "lithology": label, "color": fill, "swatch": "", "age": "", "count": count})
    return sorted(out, key=lambda r: -r["count"])


def legend_bbox(west: float, south: float, east: float, north: float) -> tuple:
    """위경도 범위 → 3857 미터."""
    def merc(lon, lat):
        lat = max(min(lat, 85.0), -85.0)
        return lon * 20037508.342789244 / 180, math.log(math.tan((90 + lat) * math.pi / 360)) * 6378137
    (x0, y0), (x1, y1) = merc(west, south), merc(east, north)
    return x0, y0, x1, y1


GSV = _NS(get_map=lambda p: _gs_get_map("gsv", p), get_feature_info=lambda p: _gs_get_feature_info("gsv", p),
          get_legend=_gs_get_legend, friendly=gs_friendly)
GSSA = _NS(get_map=lambda p: _gs_get_map("gssa", p), get_feature_info=lambda p: _gs_get_feature_info("gssa", p),
           get_legend=_gs_get_legend, friendly=gs_friendly)

#: 상류 → (문, 레이어 표, 출처)
UPSTREAMS = {"gsq": (GSQ, GSQ_LAYERS, GSQ_ATTRIBUTION), "gsv": (GSV, GSV_LAYERS, GSV_ATTRIBUTION),
             "gssa": (GSSA, GSSA_LAYERS, GSSA_ATTRIBUTION)}


def knows(upstream: str, name: str) -> bool:
    return upstream in UPSTREAMS and name in UPSTREAMS[upstream][1]


def first_zoom(upstream: str, name: str):
    spec = UPSTREAMS[upstream][1][name]
    return spec[2] if upstream == "gsq" else spec[1]
