"""VWorld 로 나가는 문 — 주소·장소 검색과 좌표→주소.

`kigam.py` 와 나란한 **두 번째 문**이다. 상류마다 문을 하나씩 둔다 — 주소가
바뀌거나 창구가 닫힐 때 고칠 자리를 하나로 묶으려는 것이다. KIGAM 은 전혀
타지 않는다.

배경지도(WMTS)는 여기를 거치지 않는다. 그것은 브라우저가 곧장 부른다
(`settings.VWORLD_KEY` 의 설명). 여기로 오는 것은 **사람이 검색 칸에 넣고
누른 한 번**과 **팝업을 연 한 번**뿐이다.

**KIGAM 의 지도 화면(TerriaMap)은 Bing 지오코더를 쓴다.** 한국 주소에
약해서 검색이 자주 빗나간다. VWorld 는 국토지리정보원 자료라 도로명·지번
·행정구역이 정확하다 (devlog 009).
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings

log = logging.getLogger(__name__)

SEARCH_URL = "https://api.vworld.kr/req/search"
ADDRESS_URL = "https://api.vworld.kr/req/address"
TIMEOUT = 8

#: 검색 한 번에 묻는 갈래. 넷을 한꺼번에 묻는다 — 사람이 넣은 글자가
#: 주소인지 장소인지 행정구역인지 우리가 가르지 않는다. 가르려 들면 틀린다.
KINDS = (
    ("district", {"type": "district", "category": "L4"}, 3),   # 읍면동
    ("district", {"type": "district", "category": "L2"}, 2),   # 시군구
    ("road", {"type": "address", "category": "road"}, 4),
    ("parcel", {"type": "address", "category": "parcel"}, 4),
    ("place", {"type": "place"}, 6),
)

_KEY_RE = re.compile(r"(key=)[^&\s]*", re.I)


class VWorldError(RuntimeError):
    """VWorld 가 답하지 않거나 알아볼 수 없는 것을 줬을 때."""


def enabled() -> bool:
    return bool(settings.VWORLD_KEY)


def _get(url: str, params: dict) -> dict:
    sent = dict(params, key=settings.VWORLD_KEY, format="json", crs="EPSG:4326")
    try:
        # KOPRI 망이 TLS 를 가로챈다 — kigam.py 와 같은 CA 꾸러미를 쓴다
        r = requests.get(url, params=sent, timeout=TIMEOUT,
                         verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        reason = _KEY_RE.sub(r"\1…", str(exc))        # 예외 문구에 URL 이 실려 온다
        raise VWorldError(f"VWorld 에 닿지 못했다: {reason}") from exc
    log.info("VWorld %s -> %s", _KEY_RE.sub(r"\1…", r.url), r.status_code)
    try:
        body = r.json()["response"]
    except (ValueError, KeyError) as exc:
        raise VWorldError(f"VWorld 가 알아볼 수 없는 것을 줬다 (status={r.status_code})") from exc
    status = body.get("status")
    if status == "NOT_FOUND":
        return {}
    if status != "OK":
        error = (body.get("error") or {}).get("text", status)
        raise VWorldError(f"VWorld 가 거절했다: {error}")
    return body.get("result") or {}


def _point(item) -> tuple:
    p = item.get("point") or {}
    return float(p["y"]), float(p["x"])


def _one_kind(kind, extra, size, query):
    result = _get(SEARCH_URL, dict(extra, service="search", request="search",
                                   version="2.0", size=size, page=1, query=query))
    out = []
    for item in result.get("items") or []:
        try:
            lat, lon = _point(item)
        except (KeyError, TypeError, ValueError):
            continue
        addr = item.get("address") or {}
        if kind == "place":
            title = item.get("title") or ""
            sub = addr.get("road") or addr.get("parcel") or ""
        elif kind == "district":
            title, sub = item.get("title") or "", ""
        else:
            title = addr.get(kind) or item.get("title") or ""
            # 도로명이면 지번을, 지번이면 도로명을 곁에 적는다
            sub = addr.get("parcel" if kind == "road" else "road") or ""
        if title:
            out.append({"kind": kind, "title": title, "sub": sub, "lat": lat, "lon": lon})
    return out


def search(query: str) -> list:
    """주소·장소·행정구역을 한꺼번에 찾는다. 행정구역 → 주소 → 장소 차례.

    한 갈래가 실패해도 나머지는 돌려준다. 다 실패하면 `VWorldError`.
    """
    query = (query or "").strip()
    if not query:
        return []
    with ThreadPoolExecutor(max_workers=len(KINDS)) as pool:
        futures = [pool.submit(_one_kind, kind, extra, size, query)
                   for kind, extra, size in KINDS]
    results, errors = [], []
    for f in futures:
        try:
            results.extend(f.result())
        except VWorldError as exc:
            errors.append(exc)
    if errors and len(errors) == len(futures):
        raise errors[0]
    # 이름이 같으면 하나로 친다. 한 번지에 건물이 여럿이면(연구원 캠퍼스처럼)
    # 같은 도로명이 건물마다 따로 온다 — 사람에게는 한 곳이다.
    seen, out = set(), []
    for row in results:
        if row["title"] not in seen:
            seen.add(row["title"])
            out.append(row)
    # 넣은 말로 **끝나는** 행정구역을 맨 앞에 둔다. "유성구" 를 찾았는데
    # 유성구의 동들이 유성구보다 먼저 뜨면 안 된다.
    out.sort(key=lambda r: 0 if r["kind"] == "district" and r["title"].endswith(query) else 1)
    return out


def reverse(lat: float, lon: float) -> dict:
    """좌표 → `{"road": "...", "parcel": "..."}`. 없으면 빈 칸이다.

    바다 한가운데처럼 주소가 없는 자리는 VWorld 가 `NOT_FOUND` 를 준다.
    """
    result = _get(ADDRESS_URL, {"service": "address", "request": "getAddress",
                                "type": "both", "point": f"{lon},{lat}"})
    out = {"road": "", "parcel": ""}
    rows = result if isinstance(result, list) else []
    for row in rows:
        kind = (row.get("type") or "").lower()
        if kind in out and not out[kind]:
            out[kind] = row.get("text") or ""
    return out
