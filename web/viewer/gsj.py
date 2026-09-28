"""산업기술종합연구소 지질조사종합센터(GSJ, AIST)로 나가는 문 — 일본 지질도.

20만분의 1 일본 심리스 지질도 V2 의 Web API 를 부른다 (devlog 024). 일본
레이어는 여기로만 나간다 (CLAUDE.md "상류마다 문이 하나").

- 주소: `gbank.gsj.jp/seamless/v2/api/1.3` — 타일(`tiles/{z}/{y}/{x}.png`)과
  범례(`legend.json`). **열쇠가 없다.** 정부표준이용규약 2.0 이라 출처만 밝히면 된다
- **WMS(`gbank.gsj.jp/ows/seamlessgeology200k_*`)는 쓰지 않는다.** 2026-09-28 에
  같은 자리를 대조하니 WMS 는 옛 판(V1 — 기호 `N1vb`, 일본어 속성뿐)이고 타일
  API 가 V2(2026-05 판, 범례 2 416, 영어 속성)였다. 새 것이 이긴다
- 타일 경로의 자리 차례가 **z/y/x** 다. 빈 자리는 `blank.png` 로 301 을 보내는데,
  따라가지 않고 우리가 빈 타일을 낸다 — 한 번 덜 묻는다
- 속성은 WMS 꼴이 아니라 `point=위도,경도` 로 묻는다. 그래서 `/featureinfo/` 가
  아니라 `gsj/info/` 가 받는다
- 범례는 그림이 아니라 JSON 이다. 화면이 HTML 로 그린다 — 서버의 Pillow 에는
  한글·일본어 글꼴이 없다(`tiles.py` 머리글)
"""
import functools
import io
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

ATTRIBUTION = ('20万分の1日本シームレス地質図V2 © <a href="https://gbank.gsj.jp/seamless/" '
               'target="_blank" rel="noopener">Geological Survey of Japan, AIST</a>')
#: 선·기호 레이어의 범례는 API 가 주지 않는다. 원본 뷰어로 잇는다
VIEWER_URL = "https://gbank.gsj.jp/seamless/v2/viewer/"

#: 우리 레이어명 → API 의 `layer`·`type`, 그려 주는 줌, 속성·범례를 읽는 법.
#:   legend  "extent" 면 보는 범위의 범례(`box`), "all" 이면 통째로(14 칸), None 이면 없다
#: 경계·단층은 줌 10, 기호는 줌 11 부터다. 그보다 멀면 API 가 빈 타일을 준다
LAYERS = {
    "gsj:geology": {"layer": "g", "min": 0, "max": 13, "info": True, "legend": "extent"},
    "gsj:geology_level2": {"layer": "g", "type": "level2", "min": 0, "max": 13,
                           "info": True, "legend": "all"},
    "gsj:boundaries": {"layer": "l", "min": 10, "max": 13, "info": False, "legend": None},
    "gsj:faults": {"layer": "f", "min": 10, "max": 13, "info": False, "legend": None},
    "gsj:symbols": {"layer": "s", "min": 11, "max": 13, "info": False, "legend": None},
}

#: 범위 범례의 칸 수 한도. 넓게 보면 수백 칸이 온다 — 패널이 끝없이 길어지지 않게
MAX_LEGEND = 200


class GsjError(RuntimeError):
    pass


def knows(name: str) -> bool:
    return name in LAYERS


def valid_tile(name: str, z: int, x: int, y: int) -> bool:
    spec = LAYERS.get(name)
    return bool(spec) and 0 <= z <= spec["max"] and 0 <= x < 2 ** z and 0 <= y < 2 ** z


@functools.lru_cache(maxsize=None)
def blank_tile() -> bytes:
    """투명한 256 타일. 상류의 `blank.png` 대신 낸다."""
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGBA", (256, 256), (0, 0, 0, 0)).save(out, "PNG", optimize=True)
    return out.getvalue()


def _get(path: str, params: dict):
    # 차단 조짐이 이어지면 잠시 묻지 않는다 (usage.py). 캐시가 대신 내준다
    left = usage.paused()
    if left:
        raise GsjError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    url = f"{settings.GSJ_URL.rstrip('/')}/{path}"
    try:
        r = requests.get(url, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, allow_redirects=False,
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("gsj", ok=False)
        raise GsjError(f"GSJ 에 닿지 못했다: {exc}") from exc
    log.info("GSJ %s -> %s", r.url, r.status_code)
    blocked = usage.looks_blocked(r.status_code, r.content[:1000])
    usage.record("gsj", ok=r.status_code in (200, 301, 302), blocked=blocked)
    return r


def get_tile(name: str, z: int, x: int, y: int) -> bytes:
    """타일 한 장(PNG). 그 줌에서 그리지 않는 레이어·빈 자리는 빈 타일이다."""
    spec = LAYERS[name]
    if z < spec["min"]:
        return blank_tile()                 # 상류도 빈 타일을 준다 — 묻지 않는다
    params = {"layer": spec["layer"]}
    if spec.get("type"):
        params["type"] = spec["type"]
    r = _get(f"tiles/{z}/{y}/{x}.png", params)
    if r.status_code in (301, 302) and "blank" in r.headers.get("location", ""):
        return blank_tile()
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise GsjError(f"타일이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content


def _json(r):
    if r.status_code != 200:
        raise GsjError(f"범례를 읽지 못했다 (status={r.status_code}, {r.text[:200]!r})")
    try:
        return r.json()
    except ValueError as exc:
        raise GsjError("범례가 JSON 이 아니다") from exc


def point_legend(name: str, lat: float, lon: float):
    """누른 자리의 범례 한 칸(상류가 준 dict). 칠해지지 않은 자리(바다·매립지)면 None."""
    spec = LAYERS[name]
    params = {"point": f"{lat:.6f},{lon:.6f}"}
    if spec.get("type"):
        params["type"] = spec["type"]
    row = _json(_get("legend.json", params))
    # 빈 자리도 200 이다 — `symbol` 이 null 인 칸이 온다
    if not isinstance(row, dict) or not row.get("symbol"):
        return None
    return row


def extent_legend(name: str, bbox, z: int) -> list:
    """보는 범위의 범례 칸들. `bbox` 는 (서, 남, 동, 북) 위경도.

    **줌을 함께 준다.** 주지 않으면 상류가 줌 13 으로 세어 넓은 범위를 400 으로
    돌려보낸다(1°×2° 에서 이미 그렇다). 화면의 줌을 주면 범위가 늘 화면 한 장이라
    상류의 한도 안에 든다.
    """
    spec = LAYERS[name]
    if spec["legend"] == "all":
        rows = _json(_get("legend.json", {"type": spec["type"]}))
    else:
        west, south, east, north = bbox
        rows = _json(_get("legend.json", {"box": f"{south:.2f},{west:.2f},{north:.2f},{east:.2f}",
                                          "z": max(0, min(spec["max"], int(z)))}))
    return [r for r in rows if isinstance(r, dict) and r.get("symbol")] if isinstance(rows, list) else []


# ── 사람이 읽을 꼴 ────────────────────────────────────────────────────

#: 상류의 대분류 → 한국어. V2 원본은 복수(`Igneous rocks`), 간략판(level2)은
#: 단수(`Igneous rock`)로 온다
GROUP_KO = {
    "sedimentary rock": "퇴적암", "igneous rock": "화성암", "metamorphic rock": "변성암",
    "accretionary complex": "부가체", "other": "기타",
}


def group_ko(value: str) -> str:
    text = str(value or "").strip()
    key = text.lower()
    if key.endswith("es") and key[:-2] in GROUP_KO:
        key = key[:-2]
    elif key.endswith("s") and key[:-1] in GROUP_KO:
        key = key[:-1]
    return GROUP_KO.get(key, text)


def age(row: dict, lang: str) -> str:
    """지질시대. 상류가 영문 ICS 명칭을 준다. 한국어판은 옮기되, 절(Age) 이름이
    섞이면 원문을 둔다 (`i18n.age_ko_stacked`, devlog 021 의 규칙)."""
    value = row.get("formationAge_en") or ""
    return i18n.age_ko_stacked(value) if lang == "ko" else value


def friendly(row: dict, lang: str = "ko") -> dict:
    """팝업에 올릴 속성. 이름은 한국어로 두고, 영어판은 `i18n.props_en` 이 옮긴다.

    암상은 **상류가 준 영어**를 올린다 — 우리가 옮긴 것이 아니라 GSJ 가 붙인
    것이고, 한국어판 사람에게 일본어보다 읽힌다. 일본어 원문은 그 밑에 둔다.
    """
    group = row.get("group_en") or ""
    props = {
        "지질시대": age(row, lang),
        "암상": lithology(row, lang),
        "구분": group_ko(group) if lang == "ko" else group,
        "기호": row.get("symbol") or "",
        "암상 (원문)": row.get("lithology_ja") or "",
    }
    return {k: v for k, v in props.items() if v}


def lithology(row: dict, lang: str) -> str:
    """간략판(level2)은 대분류가 곧 암상이고 `group_en` 이 없다 — 그때는 대분류를
    옮긴다(`Accretionary complex` → 부가체). 원본의 암상은 옮기지 않는다."""
    value = row.get("lithology_en") or ""
    if lang == "ko" and not row.get("group_en"):
        return group_ko(value)
    return value


def legend_row(row: dict, lang: str = "ko") -> dict:
    """범례 한 칸 — 색, 기호, 암상, 시대. 색은 `r·g·b` 가 그 판(간략판이면 간략판)의
    색이다. `value` 는 원본의 색이라 간략판에서 어긋난다."""
    if row.get("r") is not None:
        color = "#%02x%02x%02x" % (row["r"], row["g"], row["b"])
    else:
        color = "#" + str(row.get("value") or "cccccc")
    return {"color": color, "symbol": row.get("symbol") or "",
            "lithology": lithology(row, lang), "age": age(row, lang)}
