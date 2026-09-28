"""VWorld 로 나가는 문 — 주소·장소 검색, 좌표→주소, "지질 참고" 레이어.

`kigam.py` 와 나란한 **두 번째 문**이다. 상류마다 문을 하나씩 둔다 — 주소가
바뀌거나 창구가 닫힐 때 고칠 자리를 하나로 묶으려는 것이다. KIGAM 은 전혀
타지 않는다.

배경지도(WMTS)는 여기를 거치지 않는다. 그것은 브라우저가 곧장 부른다
(`settings.VWORLD_KEY` 의 설명). 여기로 오는 것은 사람이 검색 칸에 넣고
누른 한 번, 팝업을 연 한 번, 그리고 "지질 참고" 레이어의 타일·속성·단층
모양이다 (아래 WMS·WFS, devlog 020).

**KIGAM 의 지도 화면(TerriaMap)은 Bing 지오코더를 쓴다.** 한국 주소에
약해서 검색이 자주 빗나간다. VWorld 는 국토지리정보원 자료라 도로명·지번
·행정구역이 정확하다 (devlog 009).
"""
import logging
import re
from concurrent.futures import ThreadPoolExecutor

import requests
from django.conf import settings

from . import usage

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
    # 스레드 안에서 세지 않는다 — DB 연결이 스레드마다 생긴다
    usage.record("vworld", ok=True, count=len(futures) - len(errors))
    if errors:
        usage.record("vworld", ok=False, count=len(errors))
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
    try:
        result = _get(ADDRESS_URL, {"service": "address", "request": "getAddress",
                                    "type": "both", "point": f"{lon},{lat}"})
    except VWorldError:
        usage.record("vworld", ok=False)
        raise
    usage.record("vworld", ok=True)
    out = {"road": "", "parcel": ""}
    rows = result if isinstance(result, list) else []
    for row in rows:
        kind = (row.get("type") or "").lower()
        if kind in out and not out[kind]:
            out[kind] = row.get("text") or ""
    return out


# ── WMS·WFS — "지질 참고" 레이어군 (devlog 020) ─────────────────────────
#
# 주소 검색과 달리 여기로는 **타일이** 온다. 그래서 KIGAM 타일과 같은 캐시를
# 타고(`views.wms`), 열쇠는 여기서만 붙는다 — 브라우저는 `/GSM/wms/` 만 안다.
#
# 배경지도(WMTS)는 브라우저가 곧장 부르지만 WMS 는 중계한다. `GetFeatureInfo`
# 와 WFS 가 CORS 로 막혀 어차피 중계가 필요하고(004), 중계하면 열쇠가 안
# 나가고 캐시도 탄다.
#
# **도메인(`domain=`)을 붙이지 않는다.** 2026-09-27 에 쏴 보니 서버에서 부르는
# WMS·WFS 는 도메인이 있든 없든 같은 것을 줬다 — 주소 검색(`_get`)도 붙이지
# 않고 돈다. 도메인 검사는 브라우저가 부르는 JS API 쪽 일이다.

WMS_URL = "https://api.vworld.kr/req/wms"
WFS_URL = "https://api.vworld.kr/req/wfs"
IMAGE_URL = "https://api.vworld.kr/req/image"

#: WFS 한 번에 받는 모양 수의 상한. 1° 칸 하나에 단층이 많아야 수백 개다
#: (대전 둘레 1° 칸이 167 개). 이만큼 차면 잘린 것이라 로그를 남긴다.
MAX_FEATURES = 1000


def _redact(text: str) -> str:
    return _KEY_RE.sub(r"\1…", text or "")


def _raw(url: str, params: dict, timeout=None):
    """열쇠를 붙여 부르고 응답을 그대로 돌려준다. 세는 것도 여기서 한다."""
    if not enabled():
        raise VWorldError("VWorld 열쇠가 없다")
    left = usage.paused()
    if left:
        raise VWorldError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    sent = dict(params, key=settings.VWORLD_KEY)
    try:
        r = requests.get(url, params=sent, timeout=timeout or settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("vworld", ok=False)
        raise VWorldError(f"VWorld 에 닿지 못했다: {_redact(str(exc))}") from exc
    log.info("VWorld %s -> %s", _redact(r.url), r.status_code)
    usage.record("vworld", ok=r.status_code == 200,
                 blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms_params(params: dict) -> dict:
    """VWorld WMS 는 레이어명이 **소문자라야** 돈다 (대문자면 예외 XML)."""
    out = dict(params, service="WMS", version="1.3.0")
    for key in ("layers", "query_layers"):
        if out.get(key):
            out[key] = str(out[key]).lower()
    out.setdefault("styles", "")
    # WMS 1.1.1 로 온 것(`srs`)을 1.3.0 의 `crs` 로 옮겨 적는다
    if "srs" in out and "crs" not in out:
        out["crs"] = out.pop("srs")
    return out


def get_map(params: dict):
    """`GetMap`. (바이트, content-type). 그림이 아니면 `VWorldError`.

    **빈 타일도 그림이다.** VWorld 는 축척 밖이거나 자료가 없는 자리에 투명한
    PNG 를 준다 — 그것도 그대로 캐시에 둔다. 다시 물어도 같은 것이 온다.
    """
    r = _raw(WMS_URL, _wms_params(dict(params, request="GetMap")))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise VWorldError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    """`GetFeatureInfo` → GeoJSON FeatureCollection (KIGAM 과 같은 꼴).

    **시간 제한을 찾기와 같게 짧게 둔다(`TIMEOUT`).** 팝업은 켠 레이어의 속성이
    다 와야 한 번에 뜬다 — VWorld 하나가 늦으면 지질도 속성까지 20 초를 기다린다
    (020 에서 한 번 보았다). 이틀 동안 82 번에 실패 0 이라 잦지는 않지만, 늦을 때
    지질 참고 한 칸을 버리는 편이 팝업 전체를 붙잡는 것보다 낫다."""
    r = _raw(WMS_URL, _wms_params(dict(params, request="GetFeatureInfo",
                                       info_format="application/json")), timeout=TIMEOUT)
    if r.status_code != 200:
        raise VWorldError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return r.json()
    except ValueError as exc:
        raise VWorldError("속성이 JSON 이 아니다") from exc


def get_legend(layer: str):
    """범례. WMS 의 `GetLegendGraphic` 이 아니라 VWorld 의 이미지 API 로 받는다."""
    layer = layer.lower()
    r = _raw(IMAGE_URL, {"service": "image", "request": "GetLegendGraphic",
                         "format": "png", "type": "ALL", "layer": layer, "style": layer})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise VWorldError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, ctype


def get_features(typename: str, west: float, south: float, east: float, north: float) -> dict:
    """WFS `GetFeature` — 위경도 범위 안의 모양을 GeoJSON(EPSG:4326)으로.

    **WFS 1.1.0 의 bbox 는 위도가 먼저다** (`남,서,북,동,EPSG:4326`). 돌아오는
    좌표는 경도가 먼저다 — GeoJSON 의 차례다. 2026-09-27 에 대전 둘레로 확인했다.

    기하를 **남긴다** — 이것을 그리려고 받는 것이다. 브라우저가 쓰지 않는
    곁가지(`bbox`·`geometry_name`)만 뗀다.
    """
    r = _raw(WFS_URL, {
        "service": "WFS", "version": "1.1.0", "request": "GetFeature",
        "typename": typename.lower(), "srsname": "EPSG:4326",
        "bbox": f"{south},{west},{north},{east},EPSG:4326",
        "output": "application/json", "maxfeatures": str(MAX_FEATURES),
    })
    if r.status_code != 200:
        raise VWorldError(f"모양을 받지 못했다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        raise VWorldError("모양이 JSON 이 아니다") from exc
    features = []
    for f in data.get("features") or []:
        if not f.get("geometry"):
            continue
        features.append({"type": "Feature", "id": f.get("id"),
                         "geometry": f["geometry"], "properties": f.get("properties") or {}})
    if len(features) >= MAX_FEATURES:
        log.warning("VWorld WFS %s 가 %d 개에서 잘렸다 (%s,%s,%s,%s)",
                    typename, MAX_FEATURES, west, south, east, north)
    return {"type": "FeatureCollection", "features": features}


# ── 팝업에 보일 이름 ────────────────────────────────────────────────
#
# VWorld 의 열 이름은 영문 약어다(`riv_nm`·`sig_kor_nm`). 사람이 읽을 것에만
# 한국어 이름을 붙여 **그것만** 보인다 — 나머지는 코드(`*_cd`·`mnum`·`cat_cde`)
# 라 팝업을 길게 할 뿐이다. 표에 든 열이 하나도 없으면 받은 것을 그대로 둔다.
# 영어는 `i18n.PROP_EN` 에 있다. 2026-09-27 에 레이어마다 한 자리씩 눌러
# 모았다 (devlog 020).

FRIENDLY = {
    # 단층 — 벡터(WFS)로 받는다. `legend` 의 뜻은 VWorld 가 밝히지 않았다
    "legend": "구분",
    "leng": "길이 (m)",
    # 수문지질단위 · 지질구조선
    "info": "수문지질단위",
    "sig_nam": "시군구",
    # 온천지구
    "uname": "지구",
    "sido_name": "시도",
    "sigg_name": "시군구",
    # 등산로 — 길이·걸리는 시간 열도 있지만 단위를 밝히지 않아 싣지 않는다
    "mntn_nm": "산",
    "pmntn_nm": "구간",
    "sec_grad": "난이도",
    # 국가지명
    "land_kpyo": "지명",
    # 하천망
    "riv_nm": "하천명",
    "riv_level": "하천 등급",
    # 행정경계
    "full_nm": "행정구역",
    "ctp_kor_nm": "시도",
    "sig_kor_nm": "시군구",
    "emd_kor_nm": "읍면동",
    "li_kor_nm": "리",
}


def friendly(props: dict) -> dict:
    """VWorld 의 열 → 팝업에 보일 `{한국어 이름: 값}`. 받은 차례를 지킨다."""
    out = {}
    for key, value in props.items():
        name = FRIENDLY.get(str(key).lower())
        if not name or value in (None, "", "null"):
            continue
        if name == "길이 (m)":
            try:
                value = f"{float(value):,.0f}"
            except (TypeError, ValueError):
                pass
        out.setdefault(name, value)
    return out or dict(props)
