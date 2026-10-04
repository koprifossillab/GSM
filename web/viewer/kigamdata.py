"""KIGAM 오픈플랫폼의 자료 — 시료·분석, 조사·탐사, 지질자원주제도를 모아 두고 지도에 올린다 (wetherilli 169).

`manage.py fetch_kigam_data` 가 문(`kigam.py` 의 `data_list`·`data_detail`)으로 1 초에 한 번씩 받아 `<KIGAM_DATA_DIR>/data.json`
에 적는다. 화면이 부를 때는 이 파일만 읽는다 — 상류를 타지 않는다. 문이 아니다.

- **처음은 한 시간 남짓**(목록 35 쪽 + 상세 3 450 건). 다음부터는 목록의 `lastModified` 가 바뀐 것과 새 것만 상세를 받는다
- 좌표는 상세의 `metadata.위치정보.좌표` — WKT `POINT (경도 위도)`(축은 경도 먼저, 2026-10-02 에 한국 안에 드는 것으로 확인),
  주제도는 `POLYGON`. **좌표 없이 행정구역만 적힌 것**(옛 소장 표본 따위)은 VWorld 로 그 행정구역을 찾아 가운데에 두고
  `approx` 로 표시한다 — 찾은 자리는 `places.json` 에 담아 두 번 묻지 않는다. 나라가 대한민국이 아닌 것은 올리지 않는다
- 레이어는 모음(collection)마다 하나 — 시료·분석(GEO2)·조사·탐사(GEO1)·지질자원주제도(GEO3, 면)
- 이용 조건은 자료마다 적혀 온다(대부분 CC BY-NC, 일부 CC BY-NC-ND) — 팝업에 그대로 싣고 DOI 로 출처를 잇는다
"""
import json
import re
import time
from pathlib import Path

from django.conf import settings

DATA_FILE = "data.json"
ATTRIBUTION = "© 한국지질자원연구원 지오빅데이터 오픈플랫폼 — 이용 조건은 자료마다(대부분 CC BY-NC)"
PLACES_FILE = "places.json"

#: 레이어 → 모음 이름(상류의 `collection.name`)과 그리는 꼴
LAYERS = {
    "kigam_data:samples": {"collection": "GEO2", "title": "시료·분석"},
    "kigam_data:surveys": {"collection": "GEO1", "title": "조사·탐사"},
    "kigam_data:maps": {"collection": "GEO3", "title": "지질자원주제도", "areal": True},
}


def data_dir() -> Path:
    return Path(settings.KIGAM_DATA_DIR)


def knows(name: str) -> bool:
    return name in LAYERS


def load(file_name: str = DATA_FILE) -> dict:
    path = data_dir() / file_name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save(data: dict, file_name: str = DATA_FILE):
    path = data_dir() / file_name
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".part")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    tmp.replace(path)


def available() -> bool:
    return (data_dir() / DATA_FILE).exists()


# ── 모으기 ───────────────────────────────────────────────────────────

def trim(detail: dict) -> dict:
    """상세 한 건 → 담아 둘 것. 판 이력(`series`)·파일 목록은 덜어 낸다 — 파일은 수만 센다."""
    files = [f.get("name") for b in detail.get("bundles") or [] for f in b.get("files") or []]
    return {"id": detail.get("id"), "title": (detail.get("title") or "").strip(),
            "collection": (detail.get("collection") or {}).get("name", ""),
            "license": detail.get("license") or "", "doi": detail.get("doi") or "",
            "lastModified": detail.get("lastModified") or "", "metadata": detail.get("metadata") or {},
            "files": len(files)}


def harvest(log=print, pause: float = 1.0, limit: int = None) -> dict:
    """목록을 다 받고, 새것·바뀐 것의 상세를 받는다. 50 건마다 적어 두어 멈췄다 다시 불러도 이어 간다.
    상류가 거절하면 `kigam.UpstreamError` 가 그대로 올라간다 — 그때까지 받은 것은 남는다."""
    from . import kigam

    data = load() or {"items": {}}
    items = data.setdefault("items", {})
    listed, page, total_pages = {}, 0, None
    while total_pages is None or page < total_pages:
        if page:
            time.sleep(pause)
        got = kigam.data_list(page)
        total_pages = got.get("totalPages") or 0
        for row in got.get("content") or []:
            listed[row["id"]] = row.get("lastModified") or ""
        page += 1
    log(f"  목록 {len(listed):,} 건 ({total_pages} 쪽)")
    todo = [i for i, stamp in listed.items() if i not in items or items[i].get("lastModified") != stamp]
    gone = [i for i in items if i not in listed]
    for i in gone:
        del items[i]
    if limit is not None:
        todo = todo[:limit]
    log(f"  상세를 받을 것 {len(todo):,} 건 (없어진 것 {len(gone)} 건)")
    for n, dataset_id in enumerate(todo, 1):
        time.sleep(pause)
        items[dataset_id] = trim(kigam.data_detail(dataset_id))
        if n % 50 == 0:
            data["harvested"] = time.strftime("%Y-%m-%d %H:%M")
            save(data)
            log(f"  {n:,} / {len(todo):,}")
    data["harvested"] = time.strftime("%Y-%m-%d %H:%M")
    save(data)
    return {"listed": len(listed), "fetched": len(todo), "gone": len(gone)}


# ── 자리 ─────────────────────────────────────────────────────────────

_WKT_POINT = re.compile(r"^\s*POINT\s*\(\s*(-?[\d.]+)\s+(-?[\d.]+)\s*\)\s*$", re.I)
_WKT_POLYGON = re.compile(r"^\s*POLYGON\s*\(\((.*)\)\)\s*$", re.I | re.S)


def parse_wkt(text: str):
    """WKT `POINT`·`POLYGON`(바깥 고리 하나) → GeoJSON 기하. 모르는 꼴이면 None."""
    text = str(text or "")
    m = _WKT_POINT.match(text)
    if m:
        lon, lat = float(m.group(1)), float(m.group(2))
        return {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]}
    m = _WKT_POLYGON.match(text)
    if m:
        ring = []
        for pair in m.group(1).split("),")[0].split(","):
            parts = pair.strip().strip("()").split()
            if len(parts) >= 2:
                ring.append([round(float(parts[0]), 6), round(float(parts[1]), 6)])
        if len(ring) >= 4:
            return {"type": "Polygon", "coordinates": [ring]}
    return None


def section(item: dict, name: str) -> dict:
    value = (item.get("metadata") or {}).get(name)
    return value if isinstance(value, dict) else {}


def admin_text(item: dict) -> str:
    """좌표 없이 적힌 행정구역 한 줄 — `강원도 태백시 장성동`. 나라가 대한민국이 아니면 빈 글."""
    place = section(item, "위치정보")
    if place.get("국가") and place.get("국가") != "대한민국":
        return ""
    parts = [place.get(k, "") for k in ("도,광역시", "시군구", "동,면")]
    return " ".join(p.strip() for p in parts if p and p.strip())


def locate(places: dict, text: str, geocode, log=print):
    """행정구역 한 줄 → `[위도, 경도]`. 담아 둔 것이 먼저다. 못 찾으면 끝 마디를 떼며 다시 — 동·면이 옛 이름이거나 리가 붙어도
    시군구의 가운데는 선다. 못 찾은 것도 담는다(None) — 두 번 묻지 않는다."""
    if text in places:
        return places[text]
    words = text.split()
    found = None
    while words and found is None:
        try:
            hit = geocode(" ".join(words))
        except Exception as exc:          # VWorld 가 거절하면 이번에는 놓고 다음에 다시 묻는다
            log(f"  {text}: {exc}")
            return None
        if hit:
            found = [round(hit["lat"], 5), round(hit["lon"], 5)]
        words = words[:-1]
    places[text] = found
    return found


# ── 지도에 올리기 ────────────────────────────────────────────────────

#: 갈래 — 레이어마다 (코드, 범례 글, 색, 모양). 좌표 없이 행정구역 가운데에 둔 것은 갈래와 상관없이 `approx` 다
SAMPLE_CLASSES = (
    ("rock", "암석 표본·시료", "#8d6e63", "dot"),
    ("fossil", "화석 표본", "#2e7d32", "dot"),
    ("mineral", "광물·광석", "#1565c0", "dot"),
    ("analysis", "분석 자료", "#6a1b9a", "dot"),
    ("other", "그 밖", "#90a4ae", "dot"),
)
SURVEY_CLASSES = (
    ("spectral", "분광 측정", "#00838f", "diamond"),
    ("field", "야외 조사·탐사", "#ef6c00", "diamond"),
)
MAP_CLASSES = (
    ("geology", "지질도", "#c62828", "square"),
    ("theme", "주제도", "#ad1457", "square"),
    ("site", "그 밖의 지도·영상", "#5d4037", "square"),
)
APPROX = ("approx", "자리가 대략 — 행정구역의 가운데", "#bdbdbd", "dot")
#: 이보다 넓은 면(경위도 상자의 한 변, 도)은 그리지 않는다 — 남한 전체를 덮는 주제도가 다른 도폭을 가린다
WIDE_DEGREES = 2.5

#: 팝업에 올리는 열과 그 이름. 차례가 팝업의 차례다. 영어는 `i18n.PROP_EN`
LABELS = {
    "title": "자료", "kind": "갈래", "where": "지역", "place": "자리", "keeper": "보관", "maker": "만든 이",
    "date": "날짜", "scale": "축척", "license": "이용 조건", "doi": "DOI", "page": "자료 쪽",
}
LINKS = ("page", "doi")


def _class_of(name: str, item: dict) -> str:
    head = section(item, "개요")
    if name == "kigam_data:samples":
        kind = f"{head.get('시료유형', '')} {head.get('시료 분류명', '')} {head.get('시료', '')}"
        if "화석" in kind:
            return "fossil"
        if any(w in kind for w in ("광물", "광석")):
            return "mineral"
        if any(w in kind for w in ("암석", "암")):
            return "rock"
        if head.get("분석방법") or head.get("분석장비명 및 모델"):
            return "analysis"
        return "other"
    if name == "kigam_data:surveys":
        return "spectral" if "분광" in item.get("title", "") else "field"
    kind = head.get("지도자료", "")
    return "geology" if kind == "지질도" else "theme" if kind and kind != "기타" else "site"


def _kind_text(item: dict) -> str:
    head = section(item, "개요")
    for key in ("시료 분류명", "시료유형", "분석방법", "야외탐사/측정", "야외조사데이터", "지도자료", "주제분류"):
        if head.get(key) and head[key] != "기타":
            return str(head[key]).strip()
    return ""


def _props(item: dict, code: str, place: str) -> dict:
    head, where, keep = section(item, "개요"), section(item, "위치정보"), section(item, "보관정보")
    region = where.get("지역명") or " ".join(v for v in (where.get("도,광역시"), where.get("시군구"), where.get("동,면")) if v)
    maker = head.get("저자") or head.get("생산자") or head.get("생산기관") or head.get("발행기관") or ""
    maker = str(maker).strip("[]").replace("'", "")
    props = {"code": code, "title": item.get("title", ""), "kind": _kind_text(item), "where": region,
             "place": place, "keeper": keep.get("(현)보관장소") or "", "maker": "" if maker == "미상" else maker,
             "date": head.get("발간일") or head.get("생산일") or "", "scale": head.get("축척") or "",
             "license": item.get("license", ""), "doi": f"https://doi.org/{item['doi']}" if item.get("doi") else "",
             "page": f"https://data.kigam.re.kr/data/{item['id']}"}
    return {k: v for k, v in props.items() if v}


def _bbox_span(geom: dict) -> float:
    ring = geom["coordinates"][0]
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    return max(max(xs) - min(xs), max(ys) - min(ys))


def features(name: str, data: dict = None, places: dict = None) -> tuple:
    """레이어 하나의 feature 목록과 그리지 않은 넓은 것의 수. 좌표가 없으면 행정구역 가운데(`places`)에, 그것도 없으면 뺀다."""
    data = load() if data is None else data
    places = load(PLACES_FILE) if places is None else places
    collection = LAYERS[name]["collection"]
    out, wide = [], 0
    for item in sorted((data.get("items") or {}).values(), key=lambda i: i.get("title", "")):
        if item.get("collection") != collection:
            continue
        geom = parse_wkt(section(item, "위치정보").get("좌표"))
        place = "좌표"
        if geom is None:
            spot = places.get(admin_text(item)) if admin_text(item) else None
            if not spot:
                continue
            geom, place = {"type": "Point", "coordinates": [spot[1], spot[0]]}, "행정구역의 가운데 (대략)"
            code = APPROX[0]
        else:
            code = _class_of(name, item)
        if geom["type"] == "Polygon" and _bbox_span(geom) > WIDE_DEGREES:
            wide += 1
            continue
        out.append({"type": "Feature", "id": item["id"], "geometry": geom, "properties": _props(item, code, place)})
    return out, wide


def classes(name: str) -> tuple:
    table = {"kigam_data:samples": SAMPLE_CLASSES, "kigam_data:surveys": SURVEY_CLASSES,
             "kigam_data:maps": MAP_CLASSES}[name]
    return table + (APPROX,)


def body(name: str, lang: str = "ko") -> bytes:
    """브라우저에 보내는 한 덩이 — 극지연구소(`kopri._pack`)와 같은 꼴. 파일이 없으면 FileNotFoundError."""
    if not available():
        raise FileNotFoundError(DATA_FILE)
    data = load()
    feats, wide = features(name, data)
    counts = {}
    for f in feats:
        counts[f["properties"]["code"]] = counts.get(f["properties"]["code"], 0) + 1
    legend = [{"code": c, "label": label, "color": color, "shape": shape, "count": counts[c]}
              for c, label, color, shape in classes(name) if counts.get(c)]
    return json.dumps({"type": "FeatureCollection", "style": "class", "labels": LABELS, "links": list(LINKS),
                       "legend": legend, "wide": wide, "harvested": data.get("harvested"), "features": feats},
                      ensure_ascii=False, separators=(",", ":")).encode("utf-8")
