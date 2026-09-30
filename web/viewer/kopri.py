"""극지연구소(KOPRI)로 나가는 문 — 암석 시료 DB·KPDC 자료 목록·KPDC 지도 서버.

상류마다 문이 하나라는 규칙(CLAUDE.md)에서 **극지연구소를 한 상류로 친다.**
주소는 셋이지만 같은 기관의 한 자료 센터(KPDC)가 차린 것이다.

- `rock.kopri.re.kr/rock?page=N` — 암석 시료 목록(시료 번호·채집일·지역·암석 갈래·층·지질시대·
  좌표). 한 장에 100 행 남짓, 마지막 장을 넘겨 부르면 **마지막 장을 되풀이해 준다** — 새 시료가
  하나도 없는 장에서 멈춘다 (053)
- `kpdc.kopri.re.kr/search/?c=<묶음>&size=500&page=N` — 자료 목록. 한 행에 uuid·제목이 있다.
  `search/<uuid>` 상세 페이지에 과학 키워드·지역·기간·**공간 범위**(점·면)가 있다. 파일 자체는
  로그인해 신청해야 받는다 — 우리는 **위치와 설명만** 싣고 KPDC 페이지로 잇는다 (055·056)
- `kpdcgeo.kopri.re.kr/geoserver/kpdc/{wms,wfs}` — 남극 기지·해안선·해안선 변화 따위. 3031 을
  그대로 준다 (054·057)

**목록과 상세는 한 번 모아 파일로 둔다** (`manage.py fetch_kopri`, `settings.KOPRI_DIR`).
3 천 쪽을 2 초 간격으로 받는 데 두 시간쯤 걸려, 화면이 부를 때 받을 수 없다. 다음부터는 새로
올라온 것만 받는다. 파일이 없으면 그 레이어에 "자료가 없다" 가 뜰 뿐 뷰어는 돈다.
"""
import html as htmlmod
import json
import logging
import math
import re
import time
from pathlib import Path

import requests
from django.conf import settings

from . import usage

log = logging.getLogger(__name__)

#: 쪽과 쪽 사이에 쉬는 초. 한 번 모으는 일이라 서두르지 않는다 (devlog 010)
PAUSE = 2.0
#: 좌표를 이 자리까지만 둔다 (`arcpoints.DIGITS` 와 같다)
DIGITS = 5
ATTRIBUTION = "© 극지연구소 KPDC"
KPDC_HOME = "https://kpdc.kopri.re.kr/"
ROCK_HOME = "https://rock.kopri.re.kr/rock"


class KopriError(RuntimeError):
    pass


def _get(url: str, params: dict = None, *, timeout: int = None):
    try:
        r = requests.get(url, params=params, timeout=timeout or max(settings.UPSTREAM_TIMEOUT, 60),
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("kopri", ok=False)
        raise KopriError(f"극지연구소에 닿지 못했다: {exc}") from exc
    log.info("kopri %s -> %s", r.url, r.status_code)
    blocked = usage.looks_blocked(r.status_code, r.content[:1000])
    usage.record("kopri", ok=r.status_code == 200, blocked=blocked)
    if r.status_code != 200:
        raise KopriError(f"극지연구소가 받지 않았다 (status={r.status_code})")
    return r


def _text(fragment: str) -> str:
    return " ".join(htmlmod.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


# ── 암석 시료 (053) ──────────────────────────────────────────────────

_ROW = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
ROCK_COLUMNS = ("sample", "date", "region", "rocktype", "strat", "age", "coord")


def parse_rock_page(page: str) -> list:
    """목록 한 장 → 행들. 칸이 일곱 개인 행만 받는다."""
    rows = []
    for tr in _ROW.findall(page):
        cells = [_text(c) for c in _CELL.findall(tr)]
        if len(cells) >= len(ROCK_COLUMNS) and cells[0]:
            rows.append(dict(zip(ROCK_COLUMNS, cells)))
    return rows


def harvest_rock(pause: float = PAUSE, max_pages: int = 100, say=None) -> list:
    """암석 시료 목록을 끝까지. 새 시료가 하나도 없는 장에서 멈춘다 — 상류가 마지막 장을
    되풀이해 주기 때문이다(한 번 모를 때 200 장을 불렀다, 053)."""
    seen, out = set(), []
    for page in range(max_pages):
        if page:
            time.sleep(pause)
        rows = parse_rock_page(_get(settings.KOPRI_ROCK_URL, {"page": page}).text)
        fresh = [r for r in rows if r["sample"] not in seen]
        if say:
            say(f"암석 시료 {page} 장: {len(rows)} 행, 새 것 {len(fresh)}")
        if not fresh:
            break
        for row in fresh:
            seen.add(row["sample"])
            out.append(row)
    else:
        log.warning("암석 시료: %d 장을 넘겨도 끝나지 않아 멈췄다", max_pages)
    return out


def rock_coord(text: str):
    """"-74.4773,165.3399" → (위도, 경도). 없거나 0,0 이면 None."""
    try:
        lat, lon = (float(v) for v in str(text).split(",")[:2])
    except ValueError:
        return None
    if (lat == 0 and lon == 0) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return lat, lon


#: 암석 갈래 — 상류의 표기가 들쭉날쭉하다(`Igneous`·`igneous`·`IGNEOUS`). 접어서 가른다
ROCK_CLASSES = (
    ("sedimentary", ("sedimentary", "sediment"), "퇴적암", "#e0a526"),
    ("volcanic", ("volcanic",), "화산암", "#d7301f"),
    ("plutonic", ("igneous", "plutonic"), "화성암·심성암", "#c51b7d"),
    ("metamorphic", ("metamorphic",), "변성암", "#2c7fb8"),
    ("other", (), "그 밖·미상", "#8c8c8c"),
)


def rock_class(text: str) -> str:
    folded = (text or "").strip().lower()
    for code, words, _, _ in ROCK_CLASSES:
        if folded in words:
            return code
    return "other"


# ── KPDC 자료 목록 (055·056) ────────────────────────────────────────

_ITEM = re.compile(r'<tr class="item result-item" data-id="([0-9a-f-]{36})"(.*?)</tr>', re.S)
_ENTRY = re.compile(r'<span class="entry_id">\[([^\]]+)\]</span>')


def parse_list_page(page: str) -> list:
    """목록 한 장 → [{uuid, id, title}]."""
    out = []
    for uuid, rest in _ITEM.findall(page):
        title = re.search(r'data-title="([^"]*)"', rest)
        entry = _ENTRY.search(rest)
        out.append({"uuid": uuid, "id": entry.group(1) if entry else "",
                    "title": " ".join(htmlmod.unescape(title.group(1)).split()) if title else ""})
    return out


def list_collection(collection: str, pause: float = PAUSE, size: int = 500, max_pages: int = 30,
                    say=None) -> list:
    """묶음(`KPDC`·`KoreaMet`) 하나의 목록 전체. 목록은 가볍다 — 500 행이 한 장이다."""
    seen, out = set(), []
    url = settings.KOPRI_KPDC_URL.rstrip("/") + "/search/"
    for page in range(max_pages):
        if page:
            time.sleep(pause)
        rows = parse_list_page(_get(url, {"page": page, "size": size, "c": collection}).text)
        fresh = [r for r in rows if r["uuid"] not in seen]
        if say:
            say(f"{collection} 목록 {page} 장: {len(rows)} 행, 새 것 {len(fresh)}")
        if not fresh:
            break
        for row in fresh:
            seen.add(row["uuid"])
            out.append(row)
    return out


_DL = re.compile(r"<dt>\s*(.*?)\s*</dt>\s*<dd[^>]*>(.*?)</dd>", re.S)
_BLOCK = re.compile(r'<p class="point-header">\s*([A-Za-z]+)\s*</p>(.*?)</ul>', re.S)
_LATLON = re.compile(r"lat:</span>\s*(-?[\d.]+)\s*,\s*<span[^>]*>\s*lon:</span>\s*(-?[\d.]+)")


def parse_detail(page: str) -> dict:
    """상세 페이지 → 우리 것. 공간 범위는 [(갈래, [(위도, 경도), …]), …] 이다.

    KPDC 의 `POLYGON` 은 대개 **모서리 두 점**(사각형)이다 — 셋 이상이면 그대로 면으로 둔다.
    """
    fields = {}
    for key, value in _DL.findall(page):
        key = _text(key)
        if key and key not in fields:
            fields[key] = value
    shapes = []
    for kind, body in _BLOCK.findall(page):
        pts = [(float(a), float(b)) for a, b in _LATLON.findall(body)]
        if pts:
            shapes.append([kind.upper(), pts])

    def one(key):
        return _text(fields.get(key, ""))

    def keyword(key):
        # "EARTH SCIENCE > OCEANS > MARINE SEDIMENTS > …" — 여럿이면 줄마다 하나
        raw = fields.get(key, "")
        parts = [_text(p) for p in re.split(r"<br\s*/?>|</li>|\n\s*\n", raw)]
        return [re.sub(r"\s*>\s*", " > ", p) for p in parts if p]

    # 운석은 KoreaMet 의 기록으로 잇는 고리가 `Dataset` 둘째 칸에 있다 — 페이지에서 곧장 찾는다
    link = re.search(r'href="(https?://koreamet\.kopri\.re\.kr/[^"]+)"', page)
    return {
        "doi": one("DOI"),
        "keywords": keyword("Science Keyword"),
        "location": keyword("Location"),
        "period": one("Research period"),
        "paleo": one("Paleo age") or one("Paleo"),
        "platform": one("Platforms"),
        "instrument": one("Instruments"),
        "shapes": shapes,
        **({"link": link.group(1)} if link else {}),
    }


def fetch_detail(uuid: str) -> dict:
    return parse_detail(_get(settings.KOPRI_KPDC_URL.rstrip("/") + "/search/" + uuid).text)


def detail_url(uuid: str) -> str:
    return "https://kpdc.kopri.re.kr/search/" + uuid


# ── 모아 둔 파일 ─────────────────────────────────────────────────────

def data_dir() -> Path:
    return Path(settings.KOPRI_DIR)


def load(name: str) -> dict:
    """`rock`·`kpdc` 파일 하나. 없으면 빈 것."""
    path = data_dir() / f"{name}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}


def save(name: str, data: dict) -> None:
    """다 쓴 뒤 바꿔 끼운다 — 모으다 멈춰도 앞의 파일이 깨지지 않는다."""
    path = data_dir() / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def available(name: str) -> bool:
    return (data_dir() / f"{name}.json").exists()


def mtime(name: str) -> float:
    try:
        return (data_dir() / f"{name}.json").stat().st_mtime
    except FileNotFoundError:
        return 0.0


# ── 화면에 내는 것 ────────────────────────────────────────────────────
#
# 암석 시료·운석·KPDC 자료는 모아 둔 파일에서, 기지는 KPDC 지도 서버의 WFS 에서 온다. 넷 다
# 한 꼴(`style: class`)로 브라우저에 간다 — feature 마다 `code`, 덩이에 `legend`
# ([{code, label, color, shape, count}]). 브라우저는 그 표 하나로 그리고 범례를 적는다.
# 팝업 이름(`labels`)·범례 이름은 한국어이고 영어판이면 브라우저가 `T()` 로 옮긴다.

#: 레이어 → 무엇을 어디서. `box` 는 (서, 남, 동, 북) — 이 안의 것만 싣는다
LAYERS = {
    "kopri:rock_antarctica": {"from": "rock", "box": (-180, -90, 180, -50)},
    "kopri:rock_svalbard": {"from": "rock", "box": (5, 74, 36, 81.5)},
    "kopri:rock_greenland": {"from": "rock", "box": (-75, 59, -10, 84)},
    "kopri:meteorites": {"from": "kpdc", "collection": "KoreaMet", "box": (-180, -90, 180, -50)},
    "kopri:stations": {"from": "wfs", "types": ("antarctic_human_facilities", "antarctic_human_facilities_k")},
}

#: KPDC 자료는 주제(GCMD 과학 키워드)마다 한 레이어다 — 레이어 패널에서 켜고 끄는 것이 곧 고르기다.
#: (코드, 한국어, 색, 키워드에 이것이 들면). 위에서부터 먼저 맞는 것
TOPICS = (
    ("sediment", "해양 퇴적물·코어", "#8c510a", ("MARINE SEDIMENTS", "SEDIMENT")),
    ("solid", "고체지구", "#c51b7d", ("SOLID EARTH",)),
    ("paleo", "고기후", "#e08214", ("PALEOCLIMATE",)),
    ("cryo", "빙권", "#2c7fb8", ("CRYOSPHERE", "GLACIERS", "ICE SHEETS", "SEA ICE", "SNOW")),
    ("ocean", "해양", "#1b9e77", ("OCEANS",)),
    ("atmo", "대기", "#7570b3", ("ATMOSPHERE", "CLIMATE INDICATORS")),
    ("bio", "생물", "#66a61e", ("BIOSPHERE", "BIOLOGICAL CLASSIFICATION", "AGRICULTURE")),
    ("other", "그 밖", "#6b6b6b", ()),
)
for _code, _label, _color, _words in TOPICS:
    LAYERS[f"kopri:kpdc_{_code}"] = {"from": "kpdc", "collection": "KPDC", "topic": _code,
                                     "box": (-180, -90, 180, -50)}

#: 이보다 넓은 범위(경도 60° 또는 위도 20° 넘게)는 그리지 않는다 — 남극 전체·남빙양 전체를 덮는
#: 위성 자료가 대륙을 네모로 덮어 다른 것을 가린다. 그런 자료는 KPDC 에서 찾는 편이 낫다
WIDE_LON, WIDE_LAT = 60, 20

#: KPDC 지도 서버의 3031 WMS — 레이어명 → 상류 레이어
WMS = {
    "kopri:coast_change": "antarctic_coastline_coast_change",
    "kopri:lakes": "antarctic_water_lakes",
    "kopri:streams": "antarctic_water_streams",
    "kopri:moraines": "antarctic_topography_moraines",
}

LABELS = {
    "rock": {"no": "시료 번호", "type": "암석 갈래", "strat": "지층", "age": "지질시대",
             "date": "채취일", "region": "지역"},
    "kpdc": {"title": "제목", "id": "자료 번호", "kw": "과학 키워드", "where": "지역", "period": "연구 기간",
             "paleo": "고기후 시기", "gear": "장비", "page": "KPDC 자료 페이지", "doi": "DOI"},
    "met": {"title": "운석", "id": "자료 번호", "period": "찾은 날", "where": "지역",
            "page": "KPDC 자료 페이지", "db": "운석 기록 (KoreaMet)"},
    "wfs": {"name": "기지", "nation": "나라", "type": "갈래", "status": "운영", "opened": "처음 연 해",
            "winter": "월동 인원", "peak": "여름 최대 인원", "alt": "고도", "other": "다른 이름", "notes": "비고"},
}
LINKS = ("page", "doi", "db")

#: KPDC 지도 서버 속성 → 팝업 이름 (073). 여기 없는 열(편집자·SCAR 갈래 번호·참고 번호 따위)은 보이지 않는다.
#: 차례가 팝업의 차례다. 날짜(`revdate`)는 두 꼴(19570101 · 13/01/1992)로 와서 그대로 둔다
WMS_PROPS = {
    "kopri:coast_change": (("year", "연도"), ("source_inf", "그린 근거"), ("reliabilit", "신뢰도"),
                           ("revdate", "고친 날")),
    "kopri:lakes": (("surface", "갈래"), ("bedtype", "바닥")),
    "kopri:streams": (("imw_sheet", "도폭 (IMW)"), ("source", "출처"), ("sourcedate", "출처 날짜"),
                      ("revdate", "고친 날")),
    "kopri:moraines": (("surface", "갈래"), ("subsurface", "밑"), ("source", "출처")),
}

STATION_CLASSES = (
    ("korea", "대한민국 기지", "#c8102e", "star"),
    ("year", "상주 기지", "#1f4e79", "square"),
    ("season", "하계 기지", "#6fa8dc", "square"),
    ("other", "그 밖 시설", "#8c8c8c", "dot"),
)


def knows(name: str) -> bool:
    return name in LAYERS


def knows_file(name: str) -> bool:
    return name in LAYERS and LAYERS[name]["from"] != "wfs"


def knows_points(name: str) -> bool:
    """점 레이어의 문(`views._POINT_DOORS`)이 받는 것 — WFS 로 통째로 받는 기지."""
    return name in LAYERS and LAYERS[name]["from"] == "wfs"


def knows_wms(name: str) -> bool:
    return name in WMS


def source_url(name: str) -> str:
    return ROCK_HOME if LAYERS.get(name, {}).get("from") == "rock" else KPDC_HOME


def file_of(name: str) -> str:
    return LAYERS[name]["from"]


def _inside(box, lat, lon) -> bool:
    return box[0] <= lon <= box[2] and box[1] <= lat <= box[3]


def _pt(lat, lon):
    return [round(lon, DIGITS), round(lat, DIGITS)]


def _age(value: str, lang: str) -> str:
    from . import i18n
    return value if lang == "en" else i18n.age_ko(value)


def rock_features(rows: list, box, lang: str = "ko") -> list:
    out = []
    for row in rows:
        ll = rock_coord(row.get("coord"))
        if not ll or not _inside(box, *ll):
            continue
        props = {"code": rock_class(row.get("rocktype")), "no": row["sample"],
                 "type": row.get("rocktype"), "strat": row.get("strat"),
                 "age": _age(row.get("age"), lang) if row.get("age") not in ("", "?", "Unknown") else "",
                 "date": row.get("date"), "region": row.get("region")}
        out.append({"type": "Feature", "id": row["sample"], "geometry": {"type": "Point", "coordinates": _pt(*ll)},
                    "properties": {k: v for k, v in props.items() if v}})
    return out


def topic_of(keywords: list) -> str:
    text = " ".join(keywords or []).upper()
    for code, _, _, words in TOPICS:
        if any(w in text for w in words):
            return code
    return "other"


def _box_ring(a, b, step: float = 1.0) -> list:
    """모서리 두 점 → 경위선을 따라 촘촘히 이은 고리. 3031 에서 위선이 휜다 —
    네 점만 이으면 곧은 선이 되어 범위가 틀린다. 경도 폭이 180° 를 넘으면 날짜변경선을 넘는
    것으로 본다."""
    (lat1, lon1), (lat2, lon2) = a, b
    south, north = min(lat1, lat2), max(lat1, lat2)
    west, east = min(lon1, lon2), max(lon1, lon2)
    if east - west > 180:
        west, east = east, west + 360
    n = max(2, int(math.ceil((east - west) / step)) + 1)
    lons = [west + (east - west) * i / (n - 1) for i in range(n)]
    m = max(2, int(math.ceil((north - south) / step)) + 1)
    lats = [south + (north - south) * i / (m - 1) for i in range(m)]
    wrap = lambda lon: lon - 360 if lon > 180 else lon
    ring = ([_pt(south, wrap(x)) for x in lons] + [_pt(y, wrap(east)) for y in lats[1:]]
            + [_pt(north, wrap(x)) for x in reversed(lons[:-1])] + [_pt(y, wrap(west)) for y in reversed(lats[:-1])])
    return ring


def _shape_geometry(kind: str, pts: list):
    """KPDC 의 공간 범위 하나 → GeoJSON 기하. 넓은 범위면 None."""
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    if kind == "POINT":
        if len(pts) == 1:
            return {"type": "Point", "coordinates": _pt(*pts[0])}
        return {"type": "MultiPoint", "coordinates": [_pt(*p) for p in pts]}
    lon_span = max(lons) - min(lons)
    lon_span = min(lon_span, 360 - lon_span)
    if lon_span > WIDE_LON or max(lats) - min(lats) > WIDE_LAT:
        return None
    if kind in ("LINE", "LINESTRING"):
        return {"type": "LineString", "coordinates": [_pt(*p) for p in pts]}
    if len(pts) == 2:
        return {"type": "Polygon", "coordinates": [_box_ring(*pts)]}
    ring = [_pt(*p) for p in pts]
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return {"type": "Polygon", "coordinates": [ring]}


def kpdc_features(records: dict, spec: dict, lang: str = "ko") -> tuple:
    """모아 둔 KPDC 자료 → (feature 목록, 넓어서 뺀 자료 수)."""
    out, wide = [], 0
    meteor = spec["collection"] == "KoreaMet"
    for uuid, rec in records.items():
        if rec.get("c") != spec["collection"]:
            continue
        if not meteor and topic_of(rec.get("keywords")) != spec["topic"]:
            continue
        shapes = [(kind, pts) for kind, pts in rec.get("shapes") or []
                  if any(_inside(spec["box"], lat, lon) for lat, lon in pts)]
        if not shapes:
            continue
        doi = rec.get("doi") or ""
        if doi and not doi.startswith("http"):
            doi = "https://doi.org/" + doi
        props = {"code": "met" if meteor else spec["topic"], "title": rec.get("title"), "id": rec.get("id"),
                 "where": " · ".join(rec.get("location") or []), "period": rec.get("period"),
                 "page": detail_url(uuid)}
        if meteor:
            props["db"] = rec.get("link")
        else:
            props.update(kw=" · ".join(rec.get("keywords") or []), paleo=rec.get("paleo"),
                         gear=" · ".join(v for v in (rec.get("platform"), rec.get("instrument")) if v), doi=doi)
        props = {k: v for k, v in props.items() if v}
        drawn = 0
        for index, (kind, pts) in enumerate(shapes):
            geom = _shape_geometry(kind, pts)
            if geom is None:
                continue
            drawn += 1
            out.append({"type": "Feature", "id": f"{uuid}#{index}", "geometry": geom, "properties": props})
        if not drawn:
            wide += 1
    return out, wide


def legend_for(name: str, features: list) -> list:
    spec = LAYERS[name]
    counts = {}
    for f in features:
        code = f["properties"].get("code")
        counts[code] = counts.get(code, 0) + 1
    if spec["from"] == "rock":
        table = [(c, label, color, "dot") for c, _, label, color in ROCK_CLASSES]
    elif spec["from"] == "wfs":
        table = list(STATION_CLASSES)
    elif spec.get("collection") == "KoreaMet":
        table = [("met", "운석 발견 지점", "#4d4d4d", "diamond")]
    else:
        table = [(c, label, color, "dot") for c, label, color, _ in TOPICS if c == spec["topic"]]
    return [{"code": c, "label": label, "color": color, "shape": shape, "count": counts.get(c, 0)}
            for c, label, color, shape in table if counts.get(c)]


def _labels_of(name: str) -> dict:
    spec = LAYERS[name]
    if spec["from"] == "kpdc":
        return LABELS["met" if spec["collection"] == "KoreaMet" else "kpdc"]
    return LABELS[spec["from"]]


def _pack(name: str, features: list, **extra) -> bytes:
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": _labels_of(name),
                       "links": list(LINKS), "legend": legend_for(name, features), **extra,
                       "features": features}, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def file_body(name: str, lang: str = "ko") -> bytes:
    """모아 둔 파일에서 레이어 하나. 파일이 없으면 FileNotFoundError."""
    spec = LAYERS[name]
    if not available(spec["from"]):
        raise FileNotFoundError(spec["from"])
    data = load(spec["from"])
    if spec["from"] == "rock":
        return _pack(name, rock_features(data.get("rows") or [], spec["box"], lang),
                     harvested=data.get("harvested"))
    features, wide = kpdc_features(data.get("records") or {}, spec, lang)
    return _pack(name, features, wide=wide, harvested=data.get("harvested"))


# ── 기지 — KPDC 지도 서버의 WFS (054) ────────────────────────────────

def signature(name: str) -> str:
    """캐시 열쇠에 넣는 것 — 받는 상류 레이어가 바뀌면 받아 둔 것을 쓰지 않는다."""
    return "wfs|" + ",".join(LAYERS[name]["types"]) + "|v1"


def _station(feature: dict):
    p = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates") or []
    if geom.get("type") != "Point" or len(coords) < 2:
        return None
    status = (p.get("current_st") or "").lower()
    code = ("korea" if p.get("nationa_01") == "KOR" else "year" if "year" in status
            else "season" if "season" in status else "other")
    props = {"code": code, "name": p.get("facility_n"), "nation": p.get("national_p"),
             "type": p.get("facilty_ty"), "status": p.get("current_st"), "opened": p.get("first_open"),
             "winter": p.get("winter_pop"), "peak": p.get("peak_popul"), "alt": p.get("alt_masl"),
             "other": p.get("cga_name_o"), "notes": p.get("notes")}
    return {"type": "Feature", "id": p.get("un_locode") or feature.get("id"),
            "geometry": {"type": "Point", "coordinates": [round(float(coords[0]), DIGITS),
                                                          round(float(coords[1]), DIGITS)]},
            "properties": {k: v for k, v in props.items() if v not in (None, "")}}


def fetch(name: str, pause: float = 1.0) -> list:
    """기지를 통째로 — 상류 레이어 둘(COMNAP 100 곳, 한국 기지 2 곳). 같은 기지는 한 번만."""
    out, seen = [], set()
    for index, layer in enumerate(LAYERS[name]["types"]):
        if index:
            time.sleep(pause)
        r = _get(settings.KOPRI_GEO_URL.rstrip("/") + "/wfs",
                 {"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": f"kpdc:{layer}",
                  "outputFormat": "application/json", "srsName": "EPSG:4326"})
        try:
            data = r.json()
        except ValueError as exc:
            raise KopriError("KPDC 지도 서버가 JSON 이 아닌 것을 주었다") from exc
        for feature in data.get("features") or []:
            row = _station(feature)
            if row is None:
                continue
            key = row["properties"].get("name")
            if key in seen:
                # 한국 기지 레이어가 뒤에 온다 — 같은 이름이면 그쪽으로 덮는다
                out = [f for f in out if f["properties"].get("name") != key]
            seen.add(key)
            out.append(row)
    return out


def body(name: str, features_json: bytes) -> bytes:
    return _pack(name, json.loads(features_json))


# ── 해안선 따위 — KPDC 지도 서버의 3031 WMS (057) ────────────────────

_PASS = ("bbox", "width", "height", "srs", "crs", "format", "transparent", "version", "styles")


def get_map(params: dict):
    """`GetMap` 을 그대로 넘긴다 — 레이어명만 상류 것으로. (바이트, content-type)."""
    layer = WMS.get((params.get("layers") or "").split(",")[0].strip())
    if not layer:
        raise KopriError("KPDC 지도 서버의 레이어가 아니다")
    sent = {k: v for k, v in params.items() if k in _PASS}
    sent.update(service="WMS", request="GetMap", layers=f"kpdc:{layer}")
    sent.setdefault("styles", "")
    r = _get(settings.KOPRI_GEO_URL.rstrip("/") + "/wms", sent, timeout=settings.UPSTREAM_TIMEOUT)
    ctype = r.headers.get("content-type", "")
    if not ctype.startswith("image/"):
        raise KopriError(f"그림이 아닌 것이 왔다 (type={ctype})")
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    """`GetFeatureInfo` — GeoServer 가 JSON 으로 준다. KIGAM 과 같은 꼴(`features`)로."""
    layer = WMS.get((params.get("query_layers") or params.get("layers") or "").split(",")[0].strip())
    if not layer:
        raise KopriError("KPDC 지도 서버의 레이어가 아니다")
    sent = {k: v for k, v in params.items() if k in _PASS + ("i", "j", "x", "y", "feature_count")}
    sent.update(service="WMS", request="GetFeatureInfo", layers=f"kpdc:{layer}", query_layers=f"kpdc:{layer}",
                info_format="application/json")
    sent.setdefault("styles", "")
    r = _get(settings.KOPRI_GEO_URL.rstrip("/") + "/wms", sent, timeout=settings.UPSTREAM_TIMEOUT)
    try:
        data = r.json()
    except ValueError as exc:
        raise KopriError("KPDC 지도 서버가 JSON 이 아닌 것을 주었다") from exc
    names = WMS_PROPS.get((params.get("query_layers") or params.get("layers") or "").split(",")[0].strip(), ())
    return {"features": [{"id": f.get("id", ""), "properties": _wms_props(f.get("properties") or {}, names)}
                         for f in data.get("features") or []]}


def _wms_props(props: dict, names) -> dict:
    """상류 열 → 팝업 이름. 빈 값은 뺀다. 이름표가 없는 레이어면 상류 것을 그대로(id 따위만 빼고)."""
    if not names:
        return {k: v for k, v in props.items() if k not in ("id", "fid", "gid")}
    return {label: props[key] for key, label in names if props.get(key) not in (None, "")}


def get_legend(layer: str):
    name = WMS.get(layer)
    if not name:
        raise KopriError("KPDC 지도 서버의 레이어가 아니다")
    r = _get(settings.KOPRI_GEO_URL.rstrip("/") + "/wms",
             {"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": f"kpdc:{name}"}, timeout=settings.UPSTREAM_TIMEOUT)
    ctype = r.headers.get("content-type", "")
    if not ctype.startswith("image/"):
        raise KopriError("범례가 그림이 아니다")
    return r.content, ctype
