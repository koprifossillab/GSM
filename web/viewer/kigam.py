"""상류로 나가는 유일한 문.

뷰는 여기를 거치지 않고 `requests` 를 부르지 않는다. 상류가 바뀌거나 주소가
닫힐 때 고칠 자리를 하나로 묶어두려는 것이다. CLAUDE.md 의 "구조" 를 볼 것.

인증키는 이 파일 밖으로 나가지 않는다 — 브라우저에게도, 로그에게도.
"""
import logging
import re

import requests
from django.conf import settings

log = logging.getLogger(__name__)

#: 브라우저가 넘겨도 되는 WMS 변수. 여기 없는 것은 버린다.
#: `key` 가 빠져 있는 것이 이 목록의 요점이다 — 키는 서버가 붙인다.
ALLOWED = {
    "service", "version", "request", "layers", "query_layers", "styles",
    "srs", "crs", "bbox", "width", "height", "format", "transparent",
    "bgcolor", "exceptions", "tiled", "info_format", "feature_count",
    "x", "y", "i", "j", "buffer",
}

_KEY_RE = re.compile(r"(key=)[^&\s]*", re.I)

#: 오픈API 로 열린 GeoServer 워크스페이스. 개발 스위치가 켜졌을 때만 쓴다.
OPEN_WORKSPACE = "geoOpen"


def redact(text: str) -> str:
    """로그에 남길 문자열에서 인증키를 지운다."""
    return _KEY_RE.sub(r"\1…", text or "")


def has_key() -> bool:
    """상류에 요청을 낼 수 있는 상태인가.

    개발 스위치가 켜져 있으면 키 없이도 낼 수 있다 — 그 길은 키를 묻지
    않기 때문이다. 뷰가 "키가 없다" 안내 타일을 띄울지 판단할 때 쓴다.
    """
    return bool(settings.KIGAM_KEY) or settings.DEV_DIRECT_WMS


def _endpoint():
    """이번 요청이 나갈 주소와, 레이어명에 붙일 워크스페이스 접두사.

    문서화된 `/openapi/wms` 는 접두사 없는 이름(`L_250K_Geology_Map`)을 받고,
    GeoServer 로 곧장 갈 때는 워크스페이스가 필요하다
    (`geoOpen:L_250K_Geology_Map`). 갈리는 자리를 여기 하나로 모은다.
    """
    if settings.DEV_DIRECT_WMS:
        return settings.CAPABILITIES_URL, f"{OPEN_WORKSPACE}:"
    return settings.WMS_URL, ""


def _verify():
    """`requests` 에 넘길 `verify` 값.

    KOPRI 망이 TLS 를 가로채는 탓에 certifi 꾸러미로는 검증이 멈춘다.
    까닭은 `gsmweb.settings._default_ca_bundle()` 에 적었다.
    """
    return settings.CA_BUNDLE or True


class UpstreamError(RuntimeError):
    """상류가 돌려준 것이 지도가 아닐 때."""

    def __init__(self, message, status=None, body=""):
        super().__init__(message)
        self.status = status
        self.body = body


def clean_params(query) -> dict:
    """브라우저가 준 질의 변수를 걸러낸다. 이름은 소문자로 모은다 —
    WMS 는 변수 이름의 대소문자를 가리지 않는다."""
    out = {}
    for raw_key in query:
        low = raw_key.lower()
        if low in ALLOWED:
            out[low] = query[raw_key]
    return out


def _qualify(params: dict, prefix: str) -> dict:
    """레이어명에 워크스페이스 접두사를 붙이거나 뗀다."""
    if not prefix:
        return params
    out = dict(params)
    for key in ("layers", "query_layers", "layer"):
        value = out.get(key)
        if value:
            out[key] = ",".join(
                name if ":" in name else prefix + name
                for name in str(value).split(","))
    return out


def _get(params: dict, *, stream=False):
    url, prefix = _endpoint()
    sent = _qualify(params, prefix)
    if settings.DEV_DIRECT_WMS:
        log.debug("개발 스위치로 GeoServer 에 곧장 간다")
    elif settings.KIGAM_KEY:
        sent = dict(sent, key=settings.KIGAM_KEY)
    else:
        raise UpstreamError("인증키가 없다")
    try:
        r = requests.get(url, params=sent, stream=stream,
                         timeout=settings.UPSTREAM_TIMEOUT,
                         verify=_verify(),
                         headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        raise UpstreamError(f"상류에 닿지 못했다: {exc}") from exc
    log.info("상류 %s -> %s", redact(r.url), r.status_code)
    return r


def get_map(params: dict):
    """`GetMap`. (바이트, content-type) 을 돌려준다.

    상류는 잘못된 요청에도 200 에 HTML 을 실어 보내는 일이 있다. 그래서
    상태코드가 아니라 **돌아온 것이 이미지인지**로 성패를 가른다."""
    r = _get(dict(params, service="WMS", request="GetMap"))
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise UpstreamError(
            f"지도가 아닌 것이 왔다 (status={r.status_code}, type={ctype})",
            status=r.status_code, body=r.text[:500])
    return r.content, ctype


def get_feature_info(params: dict) -> dict:
    """`GetFeatureInfo`. GeoJSON FeatureCollection 을 돌려준다.

    문서의 요청변수 표에는 `REQUEST=GetMap` 고정이라고 적혀 있지만 이것도
    된다 — 상류가 GeoServer 이기 때문이다. devlog 001 을 볼 것.
    """
    r = _get(dict(params, service="WMS", request="GetFeatureInfo",
                  info_format="application/json"))
    if r.status_code != 200:
        raise UpstreamError(f"속성을 읽지 못했다 (status={r.status_code})",
                            status=r.status_code, body=r.text[:500])
    try:
        return r.json()
    except ValueError as exc:
        raise UpstreamError("속성이 JSON 이 아니다", body=r.text[:500]) from exc


def get_legend(layer: str):
    """`GetLegendGraphic`. (바이트, content-type) 을 돌려준다.

    문서에 적혀 있지 않지만 상류가 GeoServer 라 된다. 범례를 우리가 그리지
    않고 상류 것을 그대로 거는 까닭은, 지질도의 범례가 암상마다 색과 무늬를
    달리 쓰는 통에 우리가 다시 그리면 원본과 어긋나기 때문이다.
    """
    r = _get({"service": "WMS", "version": "1.0.0",
              "request": "GetLegendGraphic", "format": "image/png",
              "layer": layer})
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or not ctype.startswith("image/"):
        raise UpstreamError(f"범례가 아닌 것이 왔다 (status={r.status_code})",
                            status=r.status_code)
    return r.content, ctype


def fetch_capabilities() -> str:
    """`GetCapabilities` XML 을 통째로 받는다.

    **문서에 없는 주소를 탄다.** 제품이 도는 길에서는 부르지 않는다 —
    `manage.py seed_catalog --from-upstream` 이 사람 손에 불릴 때만 온다.
    CLAUDE.md 의 "두 개의 상류 주소" 를 볼 것.
    """
    url = settings.CAPABILITIES_URL
    log.warning("문서에 없는 주소로 씨앗을 뽑는다: %s", url)
    r = requests.get(url, params={"service": "WMS", "version": "1.3.0",
                                  "request": "GetCapabilities"},
                     timeout=60, verify=_verify(),
                     headers={"User-Agent": "GSM/0.1 (catalog seed)"})
    if r.status_code != 200 or "xml" not in r.headers.get("content-type", ""):
        raise UpstreamError(
            f"카탈로그를 받지 못했다 (status={r.status_code}). "
            "이 주소가 닫혔을 수 있다 — data/kigam_layers.json 의 씨앗을 쓴다.",
            status=r.status_code)
    return r.text
