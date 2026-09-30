"""ArcGIS 의 점을 통째로 받아 브라우저에 한 덩이로 주는 틀 — 문이 아니다.

그린란드 정부 포털(`grportal.py`, devlog 019)에서 생긴 것을 노르웨이 극지연구소
(`npolar.py`, devlog 021)가 함께 쓰려고 떼어 냈다. **여기서는 상류를 부르지
않는다** (`requests` 가 없다 — CLAUDE.md "상류마다 문이 하나"). 한 장을 받는
손(`get_page`)은 문이 건넨다. 여기 있는 것은 받은 feature 를 우리 꼴로 줄이고,
장을 넘기고, 브라우저에 보낼 덩이를 싸는 일뿐이다.

레이어 하나의 명세(`spec`)는 이렇다.

    {"style": "age",                     그리는 갈래 (map.js 의 portalPointStyle)
     "fields": {"age": field("age_num", "연대 (Ma)", "number"), …}}

`fields` 의 열쇠가 짧은 까닭 — 수천 점마다 되풀이되는 이름이라 짧을수록 덜
싣는다. 팝업의 이름(`label`)은 한 번만 따로 보낸다. `label` 이 없는 열(색
따위)은 그리는 데만 쓰고 팝업에 올리지 않는다.
"""
import json
import logging
import time

log = logging.getLogger(__name__)

#: 좌표를 이 자리까지만 둔다. 소수 다섯째 자리가 1 m 남짓이다.
DIGITS = 5


def field(upstream, label, kind="text"):
    return {"from": upstream, "label": label, "kind": kind}


def signature(spec: dict, head: str) -> str:
    """캐시 열쇠에 넣는 것 — 받는 열이 바뀌면 받아 둔 것을 쓰지 않는다.
    팝업 이름(`label`)은 넣지 않는다. 이름을 고쳤다고 상류에 다시 물을 까닭이 없다."""
    cols = ",".join(f"{k}={f['from']}:{f['kind']}" for k, f in sorted(spec["fields"].items()))
    return f"{head}|{cols}"


def labels(spec: dict) -> dict:
    return {k: f["label"] for k, f in spec["fields"].items() if f["label"]}


def links(spec: dict) -> list:
    """링크로 그릴 열. 팝업이 이것을 보고 `<a>` 를 만든다."""
    return sorted(k for k, f in spec["fields"].items() if f["kind"] == "link")


def collect(get_page, fields: dict, *, page: int, max_pages: int, pause: float, name: str = "",
            oid: str = "FID", areal: bool = False) -> list:
    """`get_page(offset)` 로 장을 넘기며 끝까지 받아 우리 꼴의 feature 목록으로.

    상류는 한 번에 `page` 점까지 준다. 덜 오거나 `exceededTransferLimit` 가
    없으면 끝이다. 장과 장 사이에 `pause` 초 쉰다. `areal` 이면 면도 받는다(`compact`).
    """
    out, offset = [], 0
    for index in range(max_pages):
        if index:
            time.sleep(pause)
        data = get_page(offset)
        got = data.get("features") or []
        for feature in got:
            row = compact(feature, fields, oid, areal=areal)
            if row is not None:
                out.append(row)
        more = (data.get("exceededTransferLimit")
                or (data.get("properties") or {}).get("exceededTransferLimit"))
        if not got or (len(got) < page and not more):
            break
        offset += len(got)
    else:
        log.warning("%s: %d 장을 넘겨도 끝나지 않아 멈췄다", name, max_pages)
    return out


def _round(coords):
    if coords and isinstance(coords[0], (int, float)):
        return [round(float(coords[0]), DIGITS), round(float(coords[1]), DIGITS)]
    return [_round(c) for c in coords]


def compact(feature: dict, fields: dict, oid: str = "FID", *, areal: bool = False):
    """상류 feature 하나 → 우리 것. 점이 아니면(기하가 없으면) None.
    `areal` 이면 면(Polygon·MultiPolygon)도 받는다 — 스발바르 도폭 경계."""
    geom = feature.get("geometry") or {}
    coords = geom.get("coordinates")
    if areal and geom.get("type") in ("Polygon", "MultiPolygon") and coords:
        try:
            geometry = {"type": geom["type"], "coordinates": _round(coords)}
        except (TypeError, ValueError, IndexError):
            return None
    elif geom.get("type") != "Point" or not coords or len(coords) < 2:
        return None
    else:
        try:
            geometry = {"type": "Point", "coordinates": [round(float(coords[0]), DIGITS),
                                                         round(float(coords[1]), DIGITS)]}
        except (TypeError, ValueError):
            return None
    src = feature.get("properties") or {}
    props = {}
    for key, spec in fields.items():
        value = clean(src.get(spec["from"]), spec["kind"])
        if value is not None:
            props[key] = value
    fid = feature.get("id")
    if fid is None:
        fid = src.get(oid, src.get("FID", src.get("OBJECTID", src.get("ObjectId"))))
    return {"type": "Feature", "id": fid, "geometry": geometry, "properties": props}


def clean(value, kind):
    """값 하나. 고치지 않는다 — 앞뒤 빈칸만 떼고, 빈 값은 뺀다."""
    if value is None:
        return None
    if kind in ("number", "measure"):
        try:
            number = round(float(value), 3)
        except (TypeError, ValueError):
            return None
        # `measure` — GEUS 의 다이아몬드 자료처럼 모르는 값을 -999 로 적는 열
        return None if kind == "measure" and number <= -999 else number
    text = " ".join(str(value).split())       # 앞뒤 빈칸·줄바꿈("\r\n")을 한 칸으로
    if not text:
        return None
    if kind == "link":
        # 주소는 http·https 만 받는다 — `javascript:` 를 팝업에 들이지 않는다
        return text if text.lower().startswith(("http://", "https://")) else None
    if kind == "rgb":
        try:
            r, g, b = (int(p) for p in text.split()[:3])
        except ValueError:
            return None
        return "#%02x%02x%02x" % (r, g, b)
    return text


def body(spec: dict, features_json: bytes) -> bytes:
    """브라우저에 보내는 한 덩이. 캐시에 든 feature 목록(바이트)을 다시 풀지 않고 감싼다.

    `labels` 는 팝업 이름(한국어 — 영어는 브라우저가 `PROP_EN` 으로 옮긴다),
    `links` 는 링크로 그릴 열, `style` 은 그리는 갈래다.
    """
    head = json.dumps({"type": "FeatureCollection", "labels": labels(spec), "links": links(spec),
                       "style": spec["style"]}, ensure_ascii=False)
    return head[:-1].encode("utf-8") + b', "features": ' + features_json + b"}"
