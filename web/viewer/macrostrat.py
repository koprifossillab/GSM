"""Macrostrat 으로 나가는 문 — 온 지구의 지질도 (wetherilli P06·082).

온 지구 화면(`/GSM/earth/`)의 지질 레이어는 여기로만 나간다 (CLAUDE.md "상류마다 문이 하나").

- 주소 둘. 타일은 `tiles.macrostrat.org/carto/{z}/{x}/{y}.png`(3857 z/x/y), 속성·범례는
  `macrostrat.org/api/v2`. **열쇠가 없다.** 자료는 CC BY 4.0 이다 — API 가 답마다 `license` 로 적는다
- carto 판은 나라마다 가장 자세한 지도를 이어 붙였다. 빈 곳은 GSC 세계 지질도(Chorlton 2007, 1:3500만)가
  채운다 — 한국은 거기서 "Precambrian crystalline metamorphic rocks" 한 면이다
- 판은 축척 넷(tiny·small·medium·large)으로 나뉘고 줌마다 그리는 판이 다르다(`SCALES`). **carto 는 한 대역
  아래만 채운다** — small 대역(줌 3–5)은 tiny 로 빈 곳을 채우지만 medium(6–9)은 small 까지만이다. 그래서 세계
  지질도(tiny)밖에 없는 한반도는 줌 6 부터 비었다(2026-09-30, 타일을 줌마다 받아 보았다). 우리는 **더 거친 대역의
  마지막 줌 타일(5·9)을 늘려 밑에 깔고 제 타일을 얹는다**(`fill`). 누르기도 같은 차례 — 제 축척, 그다음 더
  거친 축척 — 로 찾는다. 그래서 보이는 색과 누른 단위가 맞는다
- 바다·없는 자리의 타일은 1 KB 남짓한 빈 PNG 로 온다(200). 그대로 담는다
"""
import io
import logging
import time

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

CREDIT = "Macrostrat (CC BY 4.0) · Peters, Husson & Czaplewski 2018, G-cubed"
MAX_ZOOM = 16

#: 줌 → 그 줌에서 carto 가 그리는 축척. Macrostrat 의 갈림과 같다(대역의 마지막 줌, 축척)
SCALES = ((2, "tiny"), (5, "small"), (9, "medium"), (99, "large"))
SCALE_ORDER = ("tiny", "small", "medium", "large")
#: 대역마다 밑에 까는 더 거친 대역의 마지막 줌 — small 은 carto 가 스스로 tiny 로 채운다
FILL_FROM = {"tiny": (), "small": (), "medium": (5,), "large": (5, 9)}


class MacrostratError(RuntimeError):
    pass


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z


def scale_of(z: int) -> str:
    return next(name for last, name in SCALES if z <= last)


def _get(url: str, params: dict | None = None):
    # 차단 조짐이 이어지면 잠시 묻지 않는다 (usage.py). 캐시가 대신 내준다
    left = usage.paused()
    if left:
        raise MacrostratError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    # 상류 캐시(Varnish)가 처음 묻는 큰 타일(200 KB 넘는 것)을 보내다 끊는다(IncompleteRead). 1–2 초 뒤 다시
    # 물으면 제 캐시에 든 것을 온전히 준다(2026-09-30, curl 로도 같다). 끊긴 것만 세 번까지 쉬어 가며 묻는다
    for attempt in (1, 2, 3):
        try:
            r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                             verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
            break
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError) as exc:
            if attempt == 3:
                usage.record("macrostrat", ok=False)
                raise MacrostratError(f"Macrostrat 에 닿지 못했다: {exc}") from exc
            time.sleep(attempt)
        except requests.RequestException as exc:
            usage.record("macrostrat", ok=False)
            raise MacrostratError(f"Macrostrat 에 닿지 못했다: {exc}") from exc
    log.info("Macrostrat %s -> %s", r.url, r.status_code)
    blocked = usage.looks_blocked(r.status_code, r.content[:1000])
    usage.record("macrostrat", ok=r.status_code == 200, blocked=blocked)
    return r


def get_tile(z: int, x: int, y: int) -> bytes:
    """carto 타일 한 장(PNG, 256)."""
    r = _get(f"{settings.MACROSTRAT_TILES_URL.rstrip('/')}/carto/{z}/{x}/{y}.png")
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise MacrostratError(f"타일이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content


def _api(path: str, params: dict) -> dict:
    """API 의 `success` 칸. `data` 에 목록, 속성이면 `refs` 에 원도 인용이 든다."""
    r = _get(f"{settings.MACROSTRAT_API_URL.rstrip('/')}/{path}", params)
    try:
        body = r.json()
    except ValueError as exc:
        raise MacrostratError(f"JSON 이 아니다 (status={r.status_code})") from exc
    if r.status_code != 200 or "success" not in body:
        raise MacrostratError(f"답이 없다 (status={r.status_code}, {str(body)[:200]})")
    return body["success"]


def search_order(z: int) -> list:
    """그 줌에서 찾을 축척의 차례 — 제 축척, 그다음 더 거친 것들. 타일이 까는 차례(`fill`)와 같다."""
    i = SCALE_ORDER.index(scale_of(z))
    return [SCALE_ORDER[i]] + list(reversed(SCALE_ORDER[:i]))


def fill(z: int, x: int, y: int, get_raw) -> bytes:
    """carto 타일 한 장에 더 거친 대역의 조상 타일을 늘려 밑에 깐다. `get_raw(z, x, y)` 는 상류의 타일(캐시를
    거친다)을 준다. 제 타일이 빈 곳 없이 칠해졌으면 조상을 묻지 않는다."""
    from PIL import Image

    own = Image.open(io.BytesIO(get_raw(z, x, y))).convert("RGBA")
    ancestors = [za for za in FILL_FROM[scale_of(z)] if za < z]
    if not ancestors or own.getchannel("A").getextrema()[0] == 255:
        return get_raw(z, x, y)
    out = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
    for za in ancestors:                                   # 거친 것부터 — 고운 것이 위에 온다
        k = 2 ** (z - za)
        ax, ay = x // k, y // k
        whole = Image.open(io.BytesIO(get_raw(za, ax, ay))).convert("RGBA")
        if whole.getchannel("A").getextrema()[1] == 0:
            continue                                       # 바다 — 깔 것이 없다
        w = 256 / k
        box = ((x - ax * k) * w, (y - ay * k) * w, (x - ax * k + 1) * w, (y - ay * k + 1) * w)
        # 가장 가까운 칸으로 늘린다 — 겹선형은 단위 경계의 색을 섞어 없는 색을 만든다
        out.alpha_composite(whole.transform((256, 256), Image.Transform.EXTENT, box, Image.Resampling.NEAREST))
    out.alpha_composite(own)
    buf = io.BytesIO()
    out.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def unit_row(u: dict, scale: str, lang: str = "ko") -> dict:
    """상류의 단위 하나 → 팝업이 쓰는 꼴. 연대는 숫자(Ma)로 둔다 — 옛 위치(P06 §3)가 그것을 쓴다."""
    def age(name):
        return (i18n.age_ko(name) if lang == "ko" else name) if name else ""
    oldest, youngest = u.get("b_int_name") or "", u.get("t_int_name") or ""
    span = age(oldest) if oldest == youngest or not youngest else f"{age(oldest)} – {age(youngest)}"
    return {
        "name": u.get("name") or "",
        "strat": u.get("strat_name") or "",
        "lith": u.get("lith") or "",
        "descrip": u.get("descrip") or "",
        "age": span,
        "b_age": u.get("b_age"),
        "t_age": u.get("t_age"),
        "color": u.get("color") or "",
        "source_id": u.get("source_id"),
        "scale": scale,
    }


def identify(lon: float, lat: float, z: int, lang: str = "ko") -> dict:
    """누른 자리를 그 줌의 판으로 읽는다. `{"units": [...], "refs": {source_id: 인용}}` — 없으면 빈 목록."""
    for scale in search_order(z):
        body = _api("geologic_units/map", {"lat": f"{lat:.5f}", "lng": f"{lon:.5f}", "scale": scale})
        data = body.get("data") or []
        if data:
            return {"units": [unit_row(u, scale, lang) for u in data],
                    "refs": {str(k): v for k, v in (body.get("refs") or {}).items()}}
    return {"units": [], "refs": {}}


def legend(lang: str = "ko") -> list:
    """범례 — 기(period) 스물둘. carto 의 색은 단위의 시대(ICS)의 색이라 이것으로 읽힌다.
    세·절까지 가른 단위는 색이 조금 다르다. 젊은 것부터."""
    rows = _api("defs/intervals", {"timescale": "international periods"}).get("data") or []
    rows.sort(key=lambda r: r.get("t_age") or 0)
    return [{"name": i18n.age_ko(r["name"]) if lang == "ko" else r["name"], "en": r["name"],
             "b_age": r.get("b_age"), "t_age": r.get("t_age"), "color": r.get("color") or ""} for r in rows]
