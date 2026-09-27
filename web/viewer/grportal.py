"""그린란드 정부의 광물자원 포털(ArcGIS)로 나가는 문 — 시료·연대·광물 산출지.

`kigam.py`·`vworld.py`·`geus.py` 와 나란한 **네 번째 문**이다 (CLAUDE.md
"상류마다 문이 하나"). 이 상류의 레이어는 여기로만 나간다.

- 주소: `services5.arcgis.com/wbN76kmEQ2ue8VQm/arcgis/rest/services/<서비스>/FeatureServer/0`
  그린란드 정부(광물자원청, 계정 `emni_nanoq`)가 올린 공개 FeatureServer 다.
  Asiaq 가 차린 웹지도 "Online Map Geological data from Greenland" 가 이것들을
  얹어 보인다. 값의 뿌리는 GEUS 자료다(`data.geus.dk` 링크가 딸려 온다)
- **타일이 아니라 점을 받는다.** 레이어 하나가 수백~2 만 점이라 통째로 받아
  한 덩이의 GeoJSON 으로 브라우저에 준다. 브라우저가 그리고, 누르면 그
  자리에서 속성을 읽는다 — 상류에 한 번 더 묻지 않는다
- 한 번에 2 000 점까지 준다(`maxRecordCount`). `resultOffset` 으로 넘기며 받고,
  한 장과 한 장 사이에 **쉰다** — 2 만 점이 열 번이다
- 이용 조건은 항목에 적혀 있지 않다(`licenseInfo` 가 비어 있다). 웹지도의
  한 줄 소개가 "Free Geological Data for Greenland" 다. devlog 019
"""
import logging

import requests
from django.conf import settings

from . import arcpoints, usage

log = logging.getLogger(__name__)

#: 한 번에 받는 점의 수. 상류의 `maxRecordCount` 와 같다.
PAGE = 2000
#: 한 레이어에서 넘기는 장의 한계. 상류가 끝을 알려주지 않고 돌기만 할 때를 막는다.
MAX_PAGES = 40
#: 장과 장 사이에 쉬는 초. 한 레이어를 받는 동안 브라우저가 기다리므로
#: 너무 길게는 못 둔다 — 2 만 점이면 열 장, 쉬는 것만 5 초다.
PAUSE = 0.5
#: 좌표를 이 자리까지만 둔다 (`arcpoints.DIGITS`).
DIGITS = arcpoints.DIGITS


class PortalError(RuntimeError):
    pass


_field = arcpoints.field


#: 레이어명 → 상류 서비스와 받는 열. **열쇠가 짧은 까닭** — 2 만 점마다 되풀이되는
#: 이름이라 짧을수록 덜 싣는다. 팝업의 이름(`label`)은 한 번만 따로 보낸다.
#: `label` 이 없는 열(색 따위)은 그리는 데만 쓰고 팝업에 올리지 않는다.
#: 팝업 이름의 영어는 `i18n.PROP_EN` 에 적는다.
LAYERS = {
    "grportal:geochron": {
        "service": "geochron",
        "item": "6ddb07fed184429cab4c8a3f1326d644",
        "style": "age",
        "fields": {
            "sample": _field("sample_no", "시료 번호"),
            "age": _field("age_num", "연대 (Ma)", "number"),
            "err": _field("uncertaint", "오차 (Ma)"),
            "interp": _field("interpreta", "해석"),
            "mineral": _field("mineral", "광물"),
            "tech": _field("technique", "측정법"),
            "appr": _field("approach", "계산법"),
            "lith": _field("lithology", "암상"),
            "rock": _field("rock_type", "암석 갈래"),
            "terrane": _field("terrane", "지괴"),
            "fm": _field("formation", "지층"),
            "unit": _field("unit", "단위"),
            "ref": _field("reference", "문헌"),
            "link": _field("details", "GEUS 상세", "link"),
        },
    },
    "grportal:mineral_occurrences": {
        "service": "mineral_occurrences",
        "item": "bf6ac25c4cd6453eb5400d464aff8fab",
        "style": "mineral",
        "fields": {
            "name": _field("name", "이름"),
            "comm": _field("commodity", "광종"),
            "group": _field("commodity_", "광종 무리"),
            "status": _field("economic_s", "경제성"),
            "link": _field("report", "보고서", "link"),
        },
    },
    "grportal:intrusions": {
        "service": "intrusions",
        "item": "0936c8ef763c46e7b9c06b92180b0d09",
        "style": "intrusion",
        "fields": {
            "name": _field("name", "이름"),
            "desc": _field("descriptio", "설명"),
            "link": _field("link", "보고서", "link"),
        },
    },
    "grportal:samples": {
        "service": "samples_grportal",
        "item": "bb962bb1fc6a420b99349f7e59992bab",
        "style": "sample",
        "fields": {
            "no": _field("sampleno", "시료 번호"),
            "type": _field("sample_typ", "시료 갈래"),
            "lith": _field("lithology_", "암상"),
            "mat": _field("material_s", "시료 기재"),
            "loc": _field("localityna", "채취 지점"),
            "by": _field("collector", "채취자"),
            "date": _field("collected_", "채취일"),
            # 포털이 시료 갈래마다 매겨 둔 색("220 220 0"). 그 색으로 그린다
            "color": _field("rgb", "", "rgb"),
        },
    },
}

#: 지도 귀퉁이에 적는 출처. 항목 주소가 있으면 그리로, 없으면 웹지도로 잇는다.
WEBMAP = "https://asiaq.maps.arcgis.com/apps/webappviewer/index.html?id=4f800688403c4cfea40175950dd94875"


def knows(name: str) -> bool:
    return name in LAYERS


def source_url(name: str) -> str:
    item = LAYERS.get(name, {}).get("item")
    return f"https://www.arcgis.com/home/item.html?id={item}" if item else WEBMAP


def signature(name: str) -> str:
    """캐시 열쇠에 넣는 것 (`arcpoints.signature`). 019 의 열쇠 그대로다 —
    틀을 떼어 냈다고 받아 둔 점을 다시 받지 않는다."""
    spec = LAYERS[name]
    return arcpoints.signature(spec, f"{spec['service']}|FID")


def labels(name: str) -> dict:
    return arcpoints.labels(LAYERS[name])


def _query_url(service: str) -> str:
    return f"{settings.GRPORTAL_URL.rstrip('/')}/{service}/FeatureServer/0/query"


def _get_page(service: str, fields: list, offset: int) -> dict:
    params = {
        "where": "1=1", "outFields": ",".join(fields), "returnGeometry": "true",
        "outSR": "4326", "f": "geojson", "orderByFields": "FID ASC",
        "resultOffset": offset, "resultRecordCount": PAGE,
    }
    try:
        r = requests.get(_query_url(service), params=params, timeout=settings.UPSTREAM_TIMEOUT,
                         verify=settings.CA_BUNDLE or True, headers={"User-Agent": "GSM/0.1"})
    except requests.RequestException as exc:
        usage.record("grportal", ok=False)
        raise PortalError(f"그린란드 포털에 닿지 못했다: {exc}") from exc
    log.info("grportal %s offset=%d -> %s", service, offset, r.status_code)
    blocked = usage.looks_blocked(r.status_code, r.content[:1000])
    if r.status_code != 200:
        usage.record("grportal", ok=False, blocked=blocked)
        raise PortalError(f"그린란드 포털이 받지 않았다 (status={r.status_code})")
    try:
        data = r.json()
    except ValueError as exc:
        usage.record("grportal", ok=False)
        raise PortalError("그린란드 포털이 JSON 이 아닌 것을 주었다") from exc
    # ArcGIS 는 잘못된 요청에도 200 에 {"error": …} 를 싣는다
    if "error" in data:
        usage.record("grportal", ok=False)
        raise PortalError(f"그린란드 포털의 오류: {data['error'].get('message', '')}")
    usage.record("grportal", ok=True)
    return data


def fetch(name: str, pause: float = None) -> list:
    """레이어 하나의 점을 **모두** 받아 짧은 열쇠의 GeoJSON feature 목록으로.

    상류가 준 값은 고치지 않는다 — 앞뒤 빈칸만 떼고, 빈 값은 뺀다. 이 목록이
    그대로 캐시에 담긴다.
    """
    spec = LAYERS[name]
    fields = spec["fields"]
    # FID 를 늘 함께 받는다 — 열을 골라 받으면 상류가 feature 의 `id` 를 비워 보낸다
    wanted = sorted({f["from"] for f in fields.values()} | {"FID"})
    return arcpoints.collect(lambda offset: _get_page(spec["service"], wanted, offset), fields,
                             page=PAGE, max_pages=MAX_PAGES, pause=PAUSE if pause is None else pause,
                             name=name)


#: 받은 feature 를 우리 꼴로 줄이는 틀은 `arcpoints` 에 있다 (NPI 와 함께 쓴다, 021)
compact = arcpoints.compact
_clean = arcpoints.clean


def body(name: str, features_json: bytes) -> bytes:
    """브라우저에 보내는 한 덩이 (`arcpoints.body`)."""
    return arcpoints.body(LAYERS[name], features_json)
