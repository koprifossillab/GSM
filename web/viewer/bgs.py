"""BGS(영국 지질조사소)로 나가는 문 — 영국(그레이트브리튼) 1:5만 지질도 (wetherilli 143).

- 주소: `map.bgs.ac.uk/arcgis/services/BGS_Detailed_Geology/MapServer/WMSServer` (ArcGIS WMS). 열쇠가 없다
- 조건: **Open Government Licence** — 출처 문구 "Contains British Geological Survey materials © UKRI [해]" 를 달아야 한다
  (GetCapabilities 의 AccessConstraints). `ATTRIBUTION`
- 3857 을 그대로 받는다. **1:94 495 보다 가까울 때만 그린다**(3857 줌 13 쯤부터) — 넓게 볼 때는 EGDI 1:100만이 밑을 채운다
- 레이어명에 `bgs:` 를 붙여 카탈로그에 둔다 — 상류 이름(`BGS.50k.Bedrock`)에 점이 들어 있다. 상류로 나갈 때 뗀다
- 속성은 `application/geo+json`. 열이 쉰 남짓이라 `FRIENDLY` 에 적은 것만 보인다
"""
import logging

import requests
from django.conf import settings

from . import i18n, usage

log = logging.getLogger(__name__)

PREFIX = "bgs:"
ATTRIBUTION = ('Contains <a href="https://www.bgs.ac.uk/" target="_blank" rel="noopener">British Geological Survey</a>'
               ' materials © UKRI 2026 (<a href="https://www.nationalarchives.gov.uk/doc/open-government-licence/"'
               ' target="_blank" rel="noopener">OGL</a>)')
#: 가장 넓게 그리는 축척 — 이보다 멀면 상류가 빈 그림을 준다. 3857 로 줌 13 부터다(2026-10-02 에 쟀다) — 화면은 그보다 멀면 묻지 않는다
MAX_SCALE = 94494.99256
MIN_ZOOM = 13


class BgsError(RuntimeError):
    pass


def upstream_name(name: str) -> str:
    return ",".join(n.strip()[len(PREFIX):] if n.strip().startswith(PREFIX) else n.strip()
                    for n in str(name or "").split(","))


def _get(params: dict):
    left = usage.paused()
    if left:
        raise BgsError(f"차단 조짐이 있어 {int(left)}초 동안 상류에 묻지 않는다")
    try:
        r = requests.get(settings.BGS_WMS_URL, params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("bgs", ok=False)
        raise BgsError(f"BGS 에 닿지 못했다: {exc}") from exc
    log.info("BGS %s -> %s", r.url, r.status_code)
    usage.record("bgs", ok=r.status_code == 200, blocked=usage.looks_blocked(r.status_code, r.content[:1000]))
    return r


def _wms(params: dict, request: str) -> dict:
    params = dict(params, service="WMS", request=request, version="1.1.1")
    if "crs" in params and "srs" not in params:
        params["srs"] = params.pop("crs")
    for key in ("layers", "query_layers"):
        if key in params:
            params[key] = upstream_name(params[key])
    return params


def get_map(params: dict):
    r = _get(_wms(params, "GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise BgsError(f"그림이 아닌 것이 왔다 (status={r.status_code}, type={ctype})")
    return r.content, ctype


def get_legend(layer: str):
    r = _get({"service": "WMS", "version": "1.1.1", "request": "GetLegendGraphic", "format": "image/png",
              "layer": upstream_name(layer)})
    if r.status_code != 200 or not r.headers.get("content-type", "").startswith("image/"):
        raise BgsError(f"범례가 아닌 것이 왔다 (status={r.status_code})")
    return r.content, r.headers.get("content-type")


def get_feature_info(params: dict) -> dict:
    params = _wms(params, "GetFeatureInfo")
    params["info_format"] = "application/geo+json"
    if "i" in params and "x" not in params:
        params["x"], params["y"] = params.pop("i"), params.pop("j", "0")
    r = _get(params)
    if r.status_code != 200:
        raise BgsError(f"속성을 읽지 못했다 (status={r.status_code})")
    try:
        return {"features": r.json().get("features") or []}
    except ValueError as exc:
        raise BgsError("속성이 JSON 이 아니다") from exc


#: 상류의 열 → 팝업에 보일 이름. **여기 적은 것만, 적은 차례로.** `_D` 가 붙은 열이 글로 풀린 값이다
FRIENDLY = (
    ("LEX_D", "지층명"),
    ("RCS_D", "암석"),
    ("TYPE_D", "갈래"),
    ("MAX_PERIOD", "지질시대"),
    ("MAX_EPOCH", "세"),
    ("MAX_TIME_D", "가장 오랜 시기"),
    ("MIN_TIME_D", "가장 젊은 시기"),
    ("GP_EQ_D", "층군"),
    ("SETTING_D", "생성 환경"),
    ("FEATURE_D", "선 구조"),
    ("FLTNAME_D", "단층 이름"),
    ("CATEGORY", "갈래"),
    ("MAP_SRC", "도폭"),
    ("LEX_WEB", "어휘집"),
)
_EMPTY = {"null", "not applicable", "no parent", "none"}
_AGES = ("MAX_PERIOD", "MAX_EPOCH")


def friendly(props: dict, lang: str = "ko") -> dict:
    out = {}
    for key, label in FRIENDLY:
        value = str(props.get(key) or "").strip()
        if not value or value.lower() in _EMPTY or label in out:
            continue
        if key in _AGES and lang == "ko":
            value = i18n.age_ko(value)
        out[label] = value
    return out
