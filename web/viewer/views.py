"""화면 하나, 프록시 둘, 점묶음 넷.

프록시가 있는 까닭은 인증키다 — 브라우저는 키를 모른 채 `/wms/` 를 부르고,
여기서 키를 붙여 상류로 넘긴다. CLAUDE.md 의 "인증키" 를 볼 것.
"""
import functools
import hashlib
import json
import logging
import math
import re
import threading

from django.conf import settings
from django.contrib.staticfiles import finders
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.gzip import gzip_page
from django.views.decorators.http import require_GET, require_POST

from gsmweb.version import VERSION

from . import (coords, crs, geo3al, geomap, geus, grportal, gsj, i18n, janmayen, kigam, npolar, patchnotes,
               elevation, peninsula, phyloserver, pointsets, tilecache, tiles, trek, vworld, warp)
from .i18n import msg
from .models import Layer, LayerGroup, Point, PointSet, PointSetDeletion, Shape

log = logging.getLogger(__name__)

#: 레이어 하나가 팝업에 내놓는 속성 덩이의 최대 수. 겹친 폴리곤을 추린
#: 뒤에도 여럿 남을 수 있어 둔다 — 팝업이 길어지면 읽히지 않는다.
MAX_FEATURES = 3

#: 찍어 둔 점을 한 번에 목록으로 저장할 수 있는 수. 손으로 찍는 것이라
#: 이보다 많을 일이 드물고, 한계가 없으면 한 번의 요청이 얼마든 커진다.
MAX_SAVED_POINTS = 2000
#: 찍고 잰 것에서 한 번에 저장하는 모양(잡은 범위·잰 선) 수
MAX_SAVED_SHAPES = 200

_ANCHOR = re.compile(r"""<a\s[^>]*href=["']([^"']+)["'][^>]*>(.*?)</a>""", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")

#: 팝업에 올리지 않는 곁가지. 상류의 지질도는 레이어 하나가 아니라 **묶음**이라,
#: 하나를 물으면 밑에 깔린 것까지 함께 온다. 행정경계가 그렇다 —
#: `ufid`·`bjcd`·`divi`·`scls` 같은 코드뿐이고 읽을 수 있는 것은 `name` 하나인데,
#: 그 이름은 배경지도에 이미 글자로 적혀 있다. 지질을 물었는데 먼저 보이면
#: 방해가 된다. 도곽(`…_frame…`)은 **버리지 않는다** — 도폭명·제작연도·조사자가
#: 들어 있어 5만 지질도를 볼 때 쓸모가 있다.
NOISE_PREFIXES = ("admin_boundary",)


def _is_noise(feature_id: str) -> bool:
    return str(feature_id).lower().startswith(NOISE_PREFIXES)


def _split_links(value):
    """속성값에 섞여 온 `<a>` 를 글자와 링크로 가른다.

    **5만 지질도의 `도폭` 이 그렇게 온다** — `유성[1977]` 뒤에 원도 PDF 와
    수치지질도 DOI 가 앵커로 붙어 있다. 쓸모 있는 링크라 버리기 아깝다.

    그대로 두면 팝업에 태그가 글자로 보이고, 브라우저에서 `innerHTML` 로
    넣으면 **상류가 준 HTML 을 그대로 믿는 것**이 된다. 그래서 여기서 갈라
    보낸다 — 글자는 글자대로, 링크는 주소와 이름표로. 주소는 http·https 만
    받는다(`javascript:` 를 막는다).

    앵커가 없으면 값을 그대로 돌려준다 — 대부분이 그 경우다.
    """
    if not isinstance(value, str) or "<a" not in value.lower():
        return value

    links = []

    def take(match):
        url = match.group(1).strip()
        label = _TAG.sub("", match.group(2)).strip()
        if not url.lower().startswith(("http://", "https://")):
            # 받지 않은 주소다. **글자는 남긴다** — 이름표가 뜻을 담고 있는데
            # 주소가 못 미덥다고 글자까지 지우면 사람이 읽을 것이 사라진다.
            return label
        links.append({"label": (label or "열기")[:40], "url": url})
        return ""              # 링크로 옮겼으니 글자에서는 뺀다

    text = _TAG.sub("", _ANCHOR.sub(take, value)).strip()
    if not links:
        return text or value
    return {"text": text, "links": links}


# ── 화면 ──────────────────────────────────────────────────────────────

#: 주소 끝에 붙여 캐시를 끊는 파일들.
STAMPED = ("viewer/map.css", "viewer/map.js", "viewer/emblem.svg", "viewer/map3d.js", "viewer/moon.js")


@functools.lru_cache(maxsize=1)
def asset_stamp():
    """CSS·JS 의 내용으로 만든 짧은 표. `?v=` 로 주소 끝에 붙인다.

    **nginx 가 정적 파일을 7 일간 `immutable` 로 내보낸다.** 파일 이름이
    그대로면 브라우저는 새로 배포한 것을 받지 않고 들고 있던 것을 쓴다 —
    v0.2.1 을 배포하고도 화면에 옛 판이 뜬 까닭이다. 판 번호가 아니라
    내용으로 만드는 것은, 같은 판을 다시 구워도 내용이 바뀌면 표가 바뀌게
    하려는 것이다. 프로세스가 뜰 때 한 번 센다.
    """
    digest = hashlib.sha256(VERSION.encode())
    for name in STAMPED:
        path = finders.find(name)
        if path:
            with open(path, "rb") as fh:
                digest.update(fh.read())
    return digest.hexdigest()[:10]


def _script_json(data) -> str:
    """`<script type="application/json">` 에 넣을 JSON. 점묶음 이름은 사람이 적은
    것이라 `</script>` 가 들어 있으면 문서가 끊긴다 — `<`·`>`·`&` 를 `\\u` 로 적는다."""
    text = json.dumps(data, ensure_ascii=False)
    return text.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


@require_GET
def map_view(request):
    lang = i18n.lang_of(request)
    return render(request, "viewer/map.html", {
        "lang": lang,
        "i18n_json": json.dumps(i18n.client_table(lang), ensure_ascii=False),
        "crs_options": [(code, i18n.t(spec[0], lang)) for code, spec in crs.SYSTEMS.items()],
        "catalog": json.dumps(_catalog(lang), ensure_ascii=False),
        "pointsets": _script_json(_pointset_list()),
        "has_key": kigam.has_key(),
        "dev_direct": settings.DEV_DIRECT_WMS,
        # 브라우저가 직접 VWorld 를 부른다. 까닭은 settings.VWORLD_KEY.
        "vworld_key": settings.VWORLD_KEY,
        "version": VERSION,
        "stamp": "" if settings.DEBUG else asset_stamp(),
    })


@require_GET
def map3d_view(request):
    """3D — 실험 (devlog 015). MapLibre + 공개 표고 타일 + 서버 중계 지질도."""
    lang = i18n.lang_of(request)
    # 3D 는 3857 WMS 타일만 얹는다(`map3d.js` 의 `wmsTiles`). 모양·점 레이어와, 우리가
    # 굽거나(GeoMAP·음영판) z/x/y·극지 투영으로 받는 것(GSJ·NPI·phyloserver)은 뺀다 —
    # 목록에 두면 골라도 빈 화면이다
    # NPI(스발바르·드로닝모드랜드)는 `export` 가 3857 로도 그려 준다 — 극지 3D 에 얹는다(032)
    groups = [dict(g, layers=[l for l in g["layers"] if l.get("kind") not in ("vector", "points")
                              and (l.get("upstream") in ("kigam", "geus", "vworld")
                                   or (l.get("upstream") == "npolar" and npolar.knows(l["name"])))])
              for g in _catalog(lang)]
    # 커스텀 지질도 — 한반도 지질도 셋은 서버가 3857 로 다시 펴 주고(`warp/`), 암맥은
    # 모양 한 덩이(`points/`)라 3D 가 그대로 그린다. 밖에 열면 `_catalog` 가 이미 뺐다
    custom = [{"name": l["name"], "title": l["title"], "kind": l.get("kind"), "group": g["name"]}
              for g in _catalog(lang) for l in g["layers"] if l.get("upstream") in ("peninsula", "phyloserver")]
    return render(request, "viewer/map3d.html", {
        "lang": lang,
        "i18n_json": json.dumps(i18n.client_table(lang), ensure_ascii=False),
        "catalog_groups": [g for g in groups if g["layers"]],
        "custom_layers": _script_json(custom),
        # 점묶음 요약 — 2D 와 같은 것이다. 모양은 `pointsets/<번호>/geojson/` 으로 받는다 (P02)
        "pointsets": _script_json(_pointset_list()),
        "vworld_key": settings.VWORLD_KEY,
        "base": request.path.rsplit("3d", 1)[0],
        "version": VERSION,
        "stamp": "" if settings.DEBUG else asset_stamp(),
    })


@require_GET
def moon_view(request):
    """달 (devlog 036, P05). CesiumJS 의 둥근 달에 USGS 달 통합 지질도와 LOLA 지형을 얹는다.

    지역 탭이 아니라 대돌여지도 아이콘의 숨은 차림에서 들어온다. 지질도·표고·속성·범례는
    `moon/…` 이 `trek.py` 로 받고, 영상 배경만 브라우저가 Trek 을 곧장 부른다."""
    lang = i18n.lang_of(request)
    return render(request, "viewer/moon.html", {
        "lang": lang,
        "i18n_json": json.dumps(i18n.client_table(lang), ensure_ascii=False),
        "base": request.path.rsplit("moon", 1)[0],
        "version": VERSION,
        "stamp": "" if settings.DEBUG else asset_stamp(),
    })


# ── 달 (devlog 036, P05) ───────────────────────────────────────────────
#
# 문은 `trek.py` 다. 지질도·표고·속성·범례를 캐시에 담는다(007) — 영상 배경만 브라우저가
# 곧장 부른다. 격자는 경위도(줌 0 이 가로 2 장·세로 1 장)이고 y 는 북쪽부터 센다.

def moon_tile_key(layer, z, x, y):
    return tilecache.key_text("trek", f"{layer}/{z}/{x}/{y}")


@require_GET
def moon_tile(request, layer, z, x, y):
    """달 지질도 타일 — `moon/tiles/<units|contacts|linear>/<z>/<x>/<y>.png`."""
    z, x, y = int(z), int(x), int(y)
    if layer not in trek.LAYERS or not trek.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    key = moon_tile_key(layer, z, x, y)
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = trek.get_tile(layer, z, x, y)
    except trek.TrekError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("달 지질도 타일을 받지 못했다 (%s %s/%s/%s): %s", layer, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MAP), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
def moon_dem(request, z, x, y):
    """달 표고 격자 — `moon/dem/<z>/<x>/<y>.png`, 65×65 Terrarium (LOLA).

    못 받으면 502 다. 화면은 그 자리를 평평하게 그린다 — 안내 타일을 표고로 읽으면
    엉뚱한 산이 솟는다."""
    z, x, y = int(z), int(x), int(y)
    if not trek.valid_tile(z, x, y, trek.DEM_MAX_ZOOM):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    key = tilecache.key_text("trek-dem", f"{z}/{x}/{y}")
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = trek.dem_tile(z, x, y)
    except trek.TrekError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("달 표고를 받지 못했다 (%s/%s/%s): %s", z, x, y, exc)
        return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), i18n.lang_of(request))}, status=502)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
def moon_info(request):
    """`?lon=-15&lat=20` — 누른 자리의 지질 단위. `{"rows": [[이름, 값], …]}`.

    값은 옮기지 않는다. 시대만 한국어판에서 옮긴다(`trek.AGES_KO`)."""
    lang = i18n.lang_of(request)
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if lat is None or lon is None or not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang), "rows": []}, status=400)
    # 1e-3° 는 달에서 30 m 남짓이다 — 1:500만 지도에는 한 점이다
    key = tilecache.key_text("trek-info", f"{lon:.3f},{lat:.3f}")
    raw = _cached_json(key)
    if raw is None:
        try:
            raw = {"hit": trek.identify(lon, lat)}
        except trek.TrekError as exc:
            raw = _cached_json(key, stale=True)
            if raw is None:
                log.warning("달 속성을 읽지 못했다: %s", exc)
                return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang), "rows": []}, status=502)
        else:
            tilecache.put(key, json.dumps(raw, ensure_ascii=False).encode("utf-8"), ".json")
    hit = raw.get("hit")
    if not hit:
        return JsonResponse({"rows": []})
    rows = []
    for label, value in hit["rows"]:
        if label == "시대" and lang != "en":
            value = trek.AGES_KO.get(value, value)
        rows.append([i18n.PROP_EN.get(label, label) if lang == "en" else label, value])
    return JsonResponse({"unit": hit.get("unit", ""), "rows": rows})


@require_GET
def moon_legend(request):
    """달 지질 단위 49 가지의 범례. 이름은 상류의 것 그대로다(값이라 옮기지 않는다)."""
    key = tilecache.key_text("trek-legend", "units")
    data = _cached_json(key)
    if data is None:
        try:
            data = {"items": trek.legend()}
        except trek.TrekError as exc:
            data = _cached_json(key, stale=True)
            if data is None:
                log.warning("달 범례를 받지 못했다: %s", exc)
                return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), i18n.lang_of(request)),
                                     "items": []}, status=502)
        else:
            tilecache.put(key, json.dumps(data, ensure_ascii=False).encode("utf-8"), ".json")
    return JsonResponse(data)


@functools.lru_cache(maxsize=1)
def _moon_places():
    return trek.load_places(settings.MOON_PLACES_FILE)


@require_GET
def moon_places(request):
    """`?q=tycho` — 달 지명·착륙지 찾기. 저장소의 `data/moon_places.json` 만 뒤진다."""
    return JsonResponse({"results": trek.search_places(_moon_places(), request.GET.get("q", "")[:80])})


# ── 카탈로그 ──────────────────────────────────────────────────────────

#: 연구실 안에서만 보는 상류. 밖에 열면(`settings.PUBLIC`) 목록에서 빠지고 길도
#: 닫힌다. 레이어 이름이 `<상류>:…` 꼴이라 이름만 보고 가른다.
LAB_ONLY = ("geo3al", "phyloserver", "peninsula")


def _lab_only(name: str) -> bool:
    return settings.PUBLIC and str(name).split(":", 1)[0] in LAB_ONLY


def _catalog(lang="ko"):
    """레이어 패널의 목록. 영어판이면 제목만 `i18n.LAYER_EN` 으로 바꾼다."""
    en = lang == "en"
    groups = []
    for group in LayerGroup.objects.prefetch_related("layers").all():
        layers = [{
            "name": l.name,
            "title": i18n.LAYER_EN.get(l.name, l.title) if en else l.title,
            "bbox": l.bbox,
            "queryable": l.queryable,
            # 대조할 상류가 없는 것(우리가 그리는 GeoMAP)은 "대조 안 함" 표를 달지 않는다
            "verified": bool(l.verified_at) or l.upstream in ("geomap", "janmayen", "geo3al", "peninsula"),
            # 설명은 상류가 한국어 제목을 되풀이한 것이라 영어판에서는 숨긴다
            "abstract": "" if en else l.abstract,
            # 어느 상류인지 — 화면이 출처(`attributions`)를 붙인다. vector 면
            # 타일이 아니라 모양을 받아 그린다 (`map.js` 의 `vectorLayerFor`)
            "upstream": l.upstream,
            "kind": l.kind,
            **({"cell": VECTOR_CELL} if l.kind == "vector" else {}),
            **_point_fields(l),
            **_layer_extra(l),
        } for l in group.layers.filter(enabled=True)
            # VWorld 열쇠가 없으면 "지질 참고" 는 그릴 길이 없다 — 목록에서 뺀다
            if (l.upstream != "vworld" or vworld.enabled()) and not _lab_only(l.name)]
        if layers:
            name = i18n.GROUP_EN.get(group.name, group.name) if en else group.name
            groups.append({"name": name, "region": group.region, "layers": layers})
    return groups


def _point_fields(layer) -> dict:
    """점을 통째로 받아 브라우저가 그리는 레이어(`grportal`·`npolar` 의 점)에만 붙는 것.

    타일이 아니므로 `/wms/`·`/featureinfo/`·`/legend/` 를 부르지 않는다 —
    `queryable` 을 끄고, 받을 곳과 출처를 따로 적는다 (devlog 019·021).
    """
    if layer.upstream == "janmayen" and janmayen.knows(layer.name):
        # 얀마옌 지질도(022) — 점 말고 선·면도 이 길로 간다. 색은 자료가 준다
        return {"kind": "points", "queryable": False, "style": janmayen.LAYERS[layer.name]["style"],
                "source": janmayen.SOURCE_URL, "attribution": janmayen.ATTRIBUTION,
                "opacity": 0.75 if janmayen.LAYERS[layer.name]["style"] == "unit" else 1}
    if layer.upstream == "geo3al" and geo3al.knows(layer.name):
        # 중국 지질도(USGS geo3al, 025) — 얀마옌처럼 면을 한 덩이로. 면이 1 만 2 천이라
        # 화면이 한 장으로 구워 그린다(`render: image`). 이용 조건은 범례 칸이 적는다
        spec = geo3al.LAYERS[layer.name]
        return {"kind": "points", "queryable": False, "style": spec["style"], "render": "image",
                "source": geo3al.SOURCE_URL, "attribution": geo3al.ATTRIBUTION,
                "opacity": spec["opacity"]}
    if layer.upstream == "grportal" and grportal.knows(layer.name):
        return {"kind": "points", "queryable": False, "style": grportal.LAYERS[layer.name]["style"],
                "source": grportal.source_url(layer.name), "portal": grportal.WEBMAP}
    if layer.upstream == "phyloserver" and phyloserver.knows(layer.name):
        # 연구실의 암맥 기록(026) — 같은 서버의 phyloserver 에서 통째로 받는다
        return {"kind": "points", "queryable": False, "style": phyloserver.LAYERS[layer.name]["style"],
                "source": phyloserver.source_url(layer.name), "attribution": phyloserver.ATTRIBUTION}
    if layer.upstream == "npolar" and npolar.knows_points(layer.name):
        return {"kind": "points", "queryable": False, "style": npolar.POINTS[layer.name]["style"],
                "source": npolar.source_url(layer.name), "portal": npolar.DATA_URL,
                "attribution": npolar.ATTRIBUTION, "license": "CC BY 4.0"}
    return {}


def _layer_extra(layer) -> dict:
    """상류마다 화면에 더 알려야 하는 것. 남극(GeoMAP)은 타일 주소와 출처,
    NPI 는 타일을 받을 투영과 출처 (devlog 021)."""
    if layer.upstream == "geomap":
        return {"attribution": geomap.ATTRIBUTION,
                "tiles": f"geomap/{layer.name}/{{z}}/{{x}}/{{y}}.png",
                "projection": "EPSG:3031"}
    if layer.upstream == "npolar" and npolar.knows(layer.name):
        spec = npolar.TILES[layer.name]
        return {"attribution": npolar.ATTRIBUTION, "projection": spec["projection"],
                **({} if spec["info"] else {"queryable": False})}
    if layer.upstream == "gsj" and gsj.knows(layer.name):
        # 일본(024) — z/x/y 타일을 우리 서버가 중계한다. 경계·단층·기호는 줌 10·11
        # 부터 그려져서 그보다 멀면 화면이 레이어를 숨긴다(`minZoom`)
        spec = gsj.LAYERS[layer.name]
        return {"attribution": gsj.ATTRIBUTION,
                "tiles": f"gsj/{layer.name.split(':', 1)[1]}/{{z}}/{{x}}/{{y}}.png",
                "minZoom": spec["min"], "maxZoom": spec["max"],
                "legend": spec["legend"] or "none", "viewer": gsj.VIEWER_URL,
                **({} if spec["info"] else {"queryable": False})}
    if layer.upstream == "phyloserver" and phyloserver.knows_scan(layer.name):
        # 한반도 지질도(026) — phyloserver 의 카카오 격자 타일. 5181 격자를 화면이 옮겨 그린다
        return {"attribution": phyloserver.ATTRIBUTION, "queryable": False, "noLegend": True,
                "tiles": f"phyloserver/{layer.name.split(':', 1)[1]}/{{z}}/{{x}}_{{y}}.png"}
    if layer.upstream == "peninsula" and layer.name in peninsula.SHEETS:
        # 한반도 지질도 음영판·민판(027·028) — 우리가 잘라 둔 5179 타일. 격자를 화면에 알린다
        sheet = peninsula.SHEETS[layer.name]
        return {"attribution": sheet.attribution, "queryable": False, "noLegend": True,
                "projection": "EPSG:5179", "grid": sheet.grid(),
                "tiles": f"peninsula/{layer.name.split(':', 1)[1]}/{{z}}/{{x}}/{{y}}.{peninsula.FORMAT}"}
    return {}


@require_GET
def patch_notes(request):
    """판 이력. 설정 창이 펼쳐 보인다.

    `CHANGELOG.md` 를 **그때그때 읽는다.** 이미지에 구워 넣은 파일이라
    바뀌지 않고, 파일 하나 읽는 값이 캐시를 두는 값보다 싸다.
    """
    path = settings.REPO_DIR / "CHANGELOG.md"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return JsonResponse({"version": VERSION, "notes": []})
    return JsonResponse({"version": VERSION, "notes": patchnotes.parse(text)})


@require_GET
def catalog_json(request):
    return JsonResponse({"groups": _catalog(i18n.lang_of(request))})


# ── 상류 프록시 ───────────────────────────────────────────────────────
#
# 레이어마다 나가는 문이 다르다 — 한국은 KIGAM(`kigam.py`)과 "지질 참고"의
# VWorld(`vworld.py`), 그린란드는 GEUS(`geus.py`). 캐시·옛것 내주기·안내
# 타일은 셋이 같이 쓴다.

UPSTREAM_ERRORS = (kigam.UpstreamError, geus.GeusError, vworld.VWorldError, geomap.GeomapError,
                   npolar.NpolarError)


def _upstream_of(layers: str) -> str:
    """레이어명(여럿이면 첫째)의 상류. 카탈로그에 없으면 kigam 이다."""
    name = (layers or "").split(",")[0].strip()
    # 도폭 하나(`npolar:svalbard_sheets@A4G`)는 카탈로그에 없다 — 밑 레이어의 상류를 따른다
    name = name.split("@", 1)[0]
    try:
        row = Layer.objects.filter(name=name).values_list("upstream", flat=True).first()
    except Exception:                  # 카탈로그를 못 읽어도 한국 지도는 돌아야 한다
        row = None
    return row or "kigam"


class _Door:
    """상류 하나의 get_map·get_feature_info·get_legend 와, 지금 쓸 수 있는지.

    geomap 은 상류가 아니라 **우리 디스크의 파일**이다(`local`). 받아온 것이
    아니므로 속성·범례를 캐시에 담지 않는다 — 파일에서 읽는 편이 빠르고,
    판을 갈면 곧바로 새 것이 보인다.
    """

    MODULES = {"kigam": kigam, "geus": geus, "vworld": vworld, "geomap": geomap, "npolar": npolar}

    def __init__(self, upstream):
        self.name = upstream if upstream in self.MODULES else "kigam"
        mod = self.MODULES[self.name]
        self.get_map, self.get_feature_info, self.get_legend = mod.get_map, mod.get_feature_info, mod.get_legend
        self.local = self.name == "geomap"
        if self.name in ("geus", "npolar"):             # 열쇠가 없는 공개 서비스다
            self.ready = True
        elif self.name == "vworld":
            self.ready = vworld.enabled()
        elif self.local:
            self.ready = geomap.available()
        else:
            self.ready = kigam.has_key()

    def not_ready_message(self):
        if self.local:
            return msg("남극 지질도 자료(GeoMAP)가 서버에 없다")
        return msg("인증키가 없다")


@require_GET
def wms(request):
    """`GetMap` 중계. 브라우저가 부르는 타일 주소다.

    키가 없으면 500 을 내지 않고 **안내 타일을 200 으로 돌려준다.** 지도
    라이브러리는 타일 하나가 깨지면 그 자리를 비워둘 뿐 까닭을 말해주지
    않는다. 까닭은 타일에 적어 보내는 편이 사람에게 낫다.
    """
    params = kigam.clean_params(request.GET)
    width = _int(params.get("width"), 256)
    height = _int(params.get("height"), 256)

    params.setdefault("format", "image/png")
    params.setdefault("transparent", "true")

    # 남극(GeoMAP)은 우리가 그린다. 이름으로 가른다 — 한국 타일마다 DB 를 묻지 않으려고
    if (params.get("layers") or "").split(",")[0].strip() in geomap.LAYERS:
        return _geomap_wms(params, width, height)

    # 들고 있으면 상류에 묻지 않는다. **인증키가 없어도 캐시는 내준다** —
    # 이미 받아둔 그림이고, 다시 받을 일이 없으니 막을 까닭이 없다.
    cache_key = tilecache.key_for("map", params)
    hit = tilecache.get(cache_key)
    if hit is not None:
        return _tile(hit, cached=True)

    door = _Door(_upstream_of(params.get("layers")))
    if not door.ready:
        old = tilecache.get(cache_key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        return _tile(tiles.notice_tile(width, height, tiles.NO_KEY), store=False)

    try:
        content, ctype = door.get_map(params)
    except UPSTREAM_ERRORS as exc:
        # 늙어서 다시 물었는데 상류가 못 준다 — 빈 자리보다 옛것이 낫다
        old = tilecache.get(cache_key, stale=True)
        if old is not None:
            log.info("타일을 못 받아 옛것을 낸다: %s", exc)
            return _tile(old, cached=True)
        log.warning("타일을 받지 못했다: %s", exc)
        return _tile(tiles.notice_tile(width, height, tiles.NO_MAP), store=False)

    # 안내 타일은 캐시에 넣지 않는다 — 위에서 store=False 로 갈라 둔 까닭이다.
    tilecache.put(cache_key, content)

    response = HttpResponse(content, content_type=ctype)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    response["X-GSM-Cache"] = "miss"
    return response


def _geomap_wms(params, width, height):
    """GeoMAP 을 WMS `GetMap` 꼴로 (3031 만). 화면은 보통 `geomap_tile` 을 부른다."""
    if not geomap.available():
        return _tile(tiles.notice_tile(width, height, tiles.NO_DATA), store=False)
    try:
        content, _ = geomap.get_map(params)
    except geomap.GeomapError as exc:
        log.info("GeoMAP 을 그리지 못했다: %s", exc)
        return _tile(tiles.notice_tile(width, height, tiles.NO_MAP), store=False)
    return _tile(content)


def geomap_tile_key(layer, z, x, y, size):
    """GeoMAP 타일의 캐시 열쇠. `manage.py prewarm` 도 이것으로 담는다."""
    return tilecache.key_text("geomap", f"{layer}/{geomap.data_version()}/r{geomap.RENDERER}"
                                        f"/{z}/{x}/{y}/{size}")


@require_GET
def geomap_tile(request, layer, z, x, y, retina=None):
    """남극 지질도 타일 — `geomap/<레이어>/<z>/<x>/<y>.png` (`@2x` 면 512 px).

    격자는 EPSG:3031 고정이다 (`geomap.py` 머리글). 그린 것은 캐시에 담고 스스로
    지우지 않는다 — 다른 타일과 같다. 열쇠에 자료의 판과 `geomap.RENDERER` 가
    들어 있어, 판을 갈거나 그리는 법을 고치면 새로 그린다.
    """
    z, x, y = int(z), int(x), int(y)
    size = geomap.TILE * (2 if retina else 1)
    if layer not in geomap.LAYERS or not geomap.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    if not geomap.available():
        return _tile(tiles.notice_tile(size, size, tiles.NO_DATA), store=False)

    key = geomap_tile_key(layer, z, x, y, size)
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = geomap.render(layer, geomap.tile_bbox(z, x, y), size, size)
    except (geomap.GeomapError, OSError, ValueError) as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("GeoMAP 타일을 그리지 못했다 (%s %s/%s/%s): %s", layer, z, x, y, exc)
        return _tile(tiles.notice_tile(size, size, tiles.NO_MAP), store=False)
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


# ── 일본 — GSJ 심리스 지질도 (gsj.py, devlog 024) ─────────────────────
#
# WMS 가 아니라 z/x/y 타일과 `point=` 범례라서 `/wms/`·`/featureinfo/`·`/legend/` 를
# 타지 않고 따로 받는다. 캐시·옛것 내주기·안내 타일은 다른 상류와 같다.

def gsj_tile_key(name, z, x, y):
    """GSJ 타일의 캐시 열쇠. `manage.py prewarm` 도 이것으로 담는다."""
    return tilecache.key_text("gsj", f"{name}/{z}/{x}/{y}")


@require_GET
def gsj_tile(request, layer, z, x, y):
    """일본 지질도 타일 — `gsj/<레이어>/<z>/<x>/<y>.png`. 레이어는 `gsj:` 를 뗀 이름이다."""
    name, z, x, y = f"gsj:{layer}", int(z), int(x), int(y)
    if not gsj.valid_tile(name, z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    key = gsj_tile_key(name, z, x, y)
    hit = tilecache.get(key)
    if hit is not None:
        return _tile(hit, cached=True)
    try:
        png = gsj.get_tile(name, z, x, y)
    except gsj.GsjError as exc:
        old = tilecache.get(key, stale=True)
        if old is not None:
            return _tile(old, cached=True)
        log.warning("GSJ 타일을 받지 못했다 (%s %s/%s/%s): %s", name, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MAP), store=False)
    # 빈 타일도 담는다 — 바다 한가운데를 다시 물을 까닭이 없다
    tilecache.put(key, png)
    response = _tile(png)
    response["X-GSM-Cache"] = "miss"
    return response


@require_GET
def vworld_tile(request, layer, z, y, x):
    """VWorld 배경지도 타일 — `vworld/<레이어>/<z>/<y>/<x>`. 자리 차례는 WMTS 대로 z/y/x.

    **브라우저가 `api.vworld.kr` 에 곧장 닿지 못할 때만 온다** — 사내 VPN 이
    그 연결을 끊는다 (033). 캐시에 담지 않는다. 자료 밖은 투명한 빈 타일이다."""
    if layer not in vworld.WMTS_LAYERS:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    try:
        got = vworld.get_wmts_tile(layer, int(z), int(y), int(x))
    except vworld.VWorldError as exc:
        log.warning("VWorld 배경지도를 받지 못했다: %s", exc)
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MAP), store=False)
    if got is None:
        return _tile(tiles.blank_tile(256, 256))
    return _tile(got[0], content_type=got[1])


@require_GET
def phyloserver_tile(request, layer, level, x, y):
    """한반도 지질도 타일 — `phyloserver/<레이어>/<레벨>/<x>_<y>.png` (026).

    카카오 격자의 번호 그대로 phyloserver 에 넘긴다. 같은 서버의 파일이라
    캐시에 담지 않는다. 없는 자리는 빈 타일이다."""
    name, level, x, y = f"phyloserver:{layer}", int(level), int(x), int(y)
    if _lab_only(name) or not phyloserver.valid_scan_tile(name, level, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    try:
        png = phyloserver.get_scan_tile(name, level, x, y)
    except phyloserver.PhyloserverError as exc:
        log.warning("phyloserver 타일을 받지 못했다 (%s %s/%s_%s): %s", name, level, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MAP), store=False)
    if png is None:
        png = tiles.blank_tile(256, 256)
    return _tile(png)


@require_GET
def peninsula_tile(request, layer, z, x, y):
    """한반도 지질도 음영판·민판 타일 — `peninsula/<레이어>/<z>/<x>/<y>.webp` (027·028).

    `manage.py build_peninsula` 가 잘라 둔 파일을 내주기만 한다. 캐시에 담지 않는다 —
    이미 우리 디스크의 타일이다. 잘라 둔 것이 없으면 안내 타일, 바다는 빈 타일이다."""
    name, z, x, y = f"peninsula:{layer}", int(z), int(x), int(y)
    sheet = peninsula.SHEETS.get(name)
    if _lab_only(name) or sheet is None or not sheet.valid_tile(z, x, y):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))},
                            status=404)
    if not sheet.available():
        return _tile(tiles.notice_tile(256, 256, tiles.NO_PENINSULA), store=False)
    data = sheet.read_tile(z, x, y)
    if data is None:
        return _tile(tiles.blank_tile(256, 256))
    return _tile(data, content_type="image/webp")


#: 3D 가 다시 편 타일을 받는 줌. 멀리서는 원본을 수십 장 모아야 해 묻지 않는다
WARP_ZOOMS = (5, 17)


@require_GET
def warp_tile(request, upstream, layer, z, x, y):
    """평면 격자 타일을 3857 로 다시 편 것 — `warp/<상류>/<레이어>/<z>/<x>/<y>.png` (3D 가 쓴다).

    3D(MapLibre)는 3857 만 받아 5179(음영판·민판)·5181(스캔판) 격자를 못 얹는다.
    요청마다 원본을 모아 편다(`warp.py`, 0.1 초 남짓). 캐시에 담지 않는다 — 원본이 우리
    디스크(음영판)거나 같은 서버의 파일(스캔판, 026 이 캐시를 두지 않은 까닭 그대로)이다."""
    name, z, x, y = f"{upstream}:{layer}", int(z), int(x), int(y)
    lang = i18n.lang_of(request)
    if _lab_only(name) or not (WARP_ZOOMS[0] <= z <= WARP_ZOOMS[1]) or not (0 <= x < 2 ** z and 0 <= y < 2 ** z):
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), lang)}, status=404)
    if name in peninsula.SHEETS:
        sheet = peninsula.SHEETS[name]
        if not sheet.available():
            return _tile(tiles.notice_tile(256, 256, tiles.NO_PENINSULA), store=False)
        grid = warp.peninsula_grid(sheet)
    elif phyloserver.knows_scan(name):
        grid = warp.kakao_grid(phyloserver.SCAN_LEVELS, phyloserver.SCAN_ORIGIN, phyloserver.SCAN_TOP,
                               lambda level, tx, ty: phyloserver.get_scan_tile(name, level, tx, ty))
    else:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), lang)}, status=404)
    try:
        png = warp.render(grid, z, x, y)
    except (phyloserver.PhyloserverError, OSError, ValueError) as exc:
        log.warning("다시 펴지 못했다 (%s %s/%s/%s): %s", name, z, x, y, exc)
        return _tile(tiles.notice_tile(256, 256, tiles.NO_MAP), store=False)
    return _tile(png or tiles.blank_tile(256, 256))


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@require_GET
def gsj_info(request):
    """`?layer=gsj:geology&lat=35.36&lon=138.73` — 누른 자리의 속성. 팝업이 받는
    꼴(`features`)은 `/featureinfo/` 와 같다."""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    lat, lon = _float(request.GET.get("lat")), _float(request.GET.get("lon"))
    if not gsj.knows(name) or lat is None or lon is None or not gsj.LAYERS[name]["info"]:
        return JsonResponse({"error": i18n.t(msg("layer·lat·lon 이 없다"), lang), "features": []},
                            status=400)
    # 1e-5° 는 1 m 남짓이다. 같은 자리를 다시 누르면 상류를 타지 않는다
    key = tilecache.key_text("gsj-info", f"{name}/{lat:.5f},{lon:.5f}")
    raw = _cached_json(key)
    if raw is None:
        try:
            raw = {"row": gsj.point_legend(name, lat, lon)}
        except gsj.GsjError as exc:
            raw = _cached_json(key, stale=True)
            if raw is None:
                log.warning("GSJ 속성을 읽지 못했다: %s", exc)
                error = str(exc) if lang == "ko" else i18n.t(msg("상류에서 받지 못했다"), lang)
                return JsonResponse({"error": error, "features": []}, status=502)
        else:
            tilecache.put(key, json.dumps(raw, ensure_ascii=False).encode("utf-8"), ".json")
    row = raw.get("row")
    if not row:
        return JsonResponse({"features": []})
    props = gsj.friendly(row, lang)
    if lang == "en":
        props = i18n.props_en(props)
    return JsonResponse({"features": [{"id": row.get("symbol", ""), "props": props}]})


@require_GET
def gsj_legend(request):
    """`?layer=gsj:geology&bbox=서,남,동,북&z=9` — 보는 범위의 범례 칸들.

    원본은 범례가 2 416 칸이라 그림 한 장으로 줄 수 없다. 화면이 보는 범위에
    든 것만 물어 HTML 로 그린다. 간략판(14 칸)은 범위를 보지 않고 통째로 준다.
    범위는 소수 둘째 자리(1 km 남짓)로 잘라 캐시가 맞게 한다.
    """
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    spec = gsj.LAYERS.get(name)
    if not spec or not spec["legend"]:
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), lang), "rows": []}, status=400)
    bbox, z = None, _int(request.GET.get("z"), spec["max"])
    if spec["legend"] == "extent":
        parts = [_float(v) for v in (request.GET.get("bbox") or "").split(",")]
        if len(parts) != 4 or None in parts:
            return JsonResponse({"error": i18n.t(msg("bbox 가 없다"), lang), "rows": []}, status=400)
        bbox = [round(v, 2) for v in parts]
    key = tilecache.key_text("gsj-legend", f"{name}/{bbox}/z{z if bbox else ''}")
    rows = (_cached_json(key) or {}).get("rows")
    if rows is None:
        try:
            rows = gsj.extent_legend(name, bbox, z)
        except gsj.GsjError as exc:
            rows = (_cached_json(key, stale=True) or {}).get("rows")
            if rows is None:
                log.info("GSJ 범례를 받지 못했다 (%s): %s", name, exc)
                return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), lang), "rows": []},
                                    status=502)
        else:
            tilecache.put(key, json.dumps({"rows": rows}, ensure_ascii=False).encode("utf-8"), ".json")
    shown = [gsj.legend_row(r, lang) for r in rows[:gsj.MAX_LEGEND]]
    return JsonResponse({"rows": shown, "more": max(0, len(rows) - len(shown))})


def _tile(png: bytes, *, cached: bool = False, store: bool = True, content_type: str = "image/png"):
    """안내 타일과 캐시에서 꺼낸 타일을 같은 문으로 내보낸다.

    안내 타일은 `store=False` 다 — 브라우저가 들고 있으면 인증키가 생긴 뒤에도
    "키가 없다" 가 계속 뜬다. 캐시에서 꺼낸 것은 진짜 지도이므로 평소대로 둔다.
    """
    response = HttpResponse(png, content_type=content_type)
    if store and settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    else:
        response["Cache-Control"] = "no-store"
    response["X-GSM-Cache"] = "hit" if cached else "bypass"
    return response


@require_GET
def feature_info(request):
    """`GetFeatureInfo` 중계. 팝업이 쓸 만큼만 추려 돌려준다.

    상류가 주는 속성 이름은 이미 한국어다(`지층명`·`지질시대`·`대표암석`).
    그래서 번역표를 두지 않고 **받은 차례 그대로** 보낸다 — 상류가 열을
    더하면 팝업에도 저절로 는다. 기하는 버린다. 팝업에 쓰지 않는데
    폴리곤 좌표가 한 응답에 수천 개씩 실려 오기 때문이다.
    """
    lang = i18n.lang_of(request)
    params = kigam.clean_params(request.GET)
    params.setdefault("feature_count", "5")

    # 속성도 담아 둔다. 같은 자리를 다시 누르면 상류를 타지 않는다 —
    # 지도 범위와 누른 픽셀이 같아야 맞으므로 타일만큼 자주 맞지는 않는다
    cache_key = tilecache.key_for("info", params)
    door = _Door(_upstream_of(params.get("query_layers") or params.get("layers")))
    data = None if door.local else _cached_json(cache_key)
    if data is None:
        if not door.ready:
            data = None if door.local else _cached_json(cache_key, stale=True)
            if data is None:
                return JsonResponse({"error": i18n.t(door.not_ready_message(), lang), "features": []},
                                    status=503)
        else:
            try:
                data = door.get_feature_info(params)
            except UPSTREAM_ERRORS as exc:
                data = _cached_json(cache_key, stale=True)
                if data is None:
                    log.warning("속성을 읽지 못했다: %s", exc)
                    error = str(exc) if lang == "ko" else i18n.t(msg("상류에서 받지 못했다"), lang)
                    return JsonResponse({"error": error, "features": []},
                                        status=502)
            else:
                if not door.local:
                    _store_json(cache_key, data)

    # 같은 것이 여러 번 온다. 지질도는 폴리곤이 겹쳐 놓인 자리가 많고,
    # 클릭 한 점이 아니라 몇 픽셀 둘레를 물어보기 때문이다. 사람에게는
    # "여기가 무엇인가" 한 답이면 되므로 **속성이 같은 것은 하나로 친다.**
    features, seen = [], set()
    for feature in (data.get("features") or []):
        if _is_noise(feature.get("id", "")):
            continue
        props = {k: v for k, v in (feature.get("properties") or {}).items()
                 if v not in (None, "", "null")}
        if not props:
            continue
        mark = tuple(sorted((k, str(v)) for k, v in props.items()))
        if mark in seen:
            continue
        seen.add(mark)
        props = {k: _split_links(v) for k, v in props.items()}
        if door.name == "geus":
            props = geus.friendly(props)          # gu_name → 지질 단위 …
        elif door.name == "vworld":
            props = vworld.friendly(props)        # riv_nm → 하천명 …
        elif door.name == "npolar":
            # NAME → 이름 …, 한국어판이면 지질시대(영문 ICS)를 옮긴다
            props = npolar.friendly(props, lang)
        if lang == "en":
            # 캐시에는 상류가 준 한국어 그대로 두고, 내보낼 때만 옮긴다
            props = i18n.props_en(props)
        features.append({"id": feature.get("id", ""), "props": props})
        if len(features) >= MAX_FEATURES:
            break
    return JsonResponse({"features": features})


def _cached_json(key: str, *, stale: bool = False):
    raw = tilecache.get(key, ".json", stale=stale)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def _store_json(key: str, data: dict) -> None:
    """기하를 떼고 담는다. 팝업이 쓰지 않는 폴리곤 좌표가 대부분이다."""
    slim = dict(data)
    slim["features"] = [{k: v for k, v in f.items() if k != "geometry"}
                        for f in (data.get("features") or [])]
    tilecache.put(key, json.dumps(slim, ensure_ascii=False).encode("utf-8"),
                  ".json")


@require_GET
def legend(request):
    """레이어 범례 이미지. 레이어 패널에서 펼쳐 볼 때 부른다."""
    layer = request.GET.get("layer", "")
    if not layer:
        return JsonResponse({"error": i18n.t(msg("layer 가 없다"), i18n.lang_of(request))}, status=400)

    if layer in geomap.LAYERS:
        return _geomap_legend(request, layer)
    if phyloserver.knows_scan(layer) or layer in peninsula.LAYERS:
        # 한반도 지질도(026·027)는 범례를 따로 주지 않는다. KIGAM 에 묻지 않게 여기서 막는다
        return JsonResponse({"error": i18n.t(msg("범례가 없는 레이어다"), i18n.lang_of(request))}, status=404)

    # 범례도 캐시한다. 타일보다 훨씬 드물게 부르지만 한 장이 수십 KB 라
    # (25만 지질도 범례는 223x5218 픽셀이다) 다시 받을 까닭이 없다.
    cache_key = tilecache.key_for("legend", {"layer": layer})
    hit = tilecache.get(cache_key)
    if hit is not None:
        response = HttpResponse(hit, content_type="image/png")
        response["X-GSM-Cache"] = "hit"
        if settings.TILE_CACHE_SECONDS > 0:
            response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
        return response

    door = _Door(_upstream_of(layer))
    try:
        if not door.ready:
            raise kigam.UpstreamError("인증키가 없다", status=503)
        content, ctype = door.get_legend(layer)
    except UPSTREAM_ERRORS as exc:
        old = tilecache.get(cache_key, stale=True)
        if old is not None:
            response = HttpResponse(old, content_type="image/png")
            response["X-GSM-Cache"] = "stale"
            return response
        log.info("범례를 받지 못했다 (%s): %s", layer, exc)
        return JsonResponse({"error": str(exc)},
                            status=503 if not door.ready else 502)
    tilecache.put(cache_key, content)
    response = HttpResponse(content, content_type=ctype)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


# ── 벡터 레이어 — 모양을 받아 우리가 그린다 (단층, devlog 020) ──────────
#
# 타일이 아니라 모양(GeoJSON)을 준다. 브라우저가 선 색·굵기를 정하므로 어느
# 줌에서도 또렷하고, 누르면 그 선의 속성이 곧장 뜬다(상류를 다시 안 탄다).
#
# **위경도 1° 칸으로 나눠 받는다.** 화면 범위를 그대로 상류에 넘기면 지도를
# 조금만 움직여도 열쇠가 달라져 캐시가 맞지 않는다. 칸으로 자르면 같은 칸은
# 한 번만 받고, 칸 이름이 좌표계와 상관없어 극지 투영에서도 같은 것을 쓴다.
# 남한은 1° 칸 50 개 남짓이고, 한 칸에 단층이 많아야 수백 개(수십 KB)다.

#: 칸의 크기(도). 화면(`map.js`)은 카탈로그의 `cell` 로 이 값을 받는다
VECTOR_CELL = 1


@require_GET
def vector(request):
    """`?layer=lt_l_gimsfault&lon=127&lat=36` — 칸 하나의 모양. 서남 모서리가 칸 이름이다."""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    try:
        lon, lat = int(request.GET.get("lon", "")), int(request.GET.get("lat", ""))
    except ValueError:
        return JsonResponse({"error": "lon·lat"}, status=400)
    if not (-180 <= lon < 180 and -90 <= lat < 90) or lon % VECTOR_CELL or lat % VECTOR_CELL:
        return JsonResponse({"error": "lon·lat"}, status=400)
    layer = Layer.objects.filter(name=name, kind="vector", enabled=True).first()
    if layer is None or layer.upstream != "vworld":
        return JsonResponse({"error": "layer"}, status=404)

    empty = {"type": "FeatureCollection", "features": []}
    box = layer.bbox
    if box and (lon + VECTOR_CELL <= box[0] or lon >= box[2]
                or lat + VECTOR_CELL <= box[1] or lat >= box[3]):
        return _vector_response(empty)             # 레이어 범위 밖이다. 상류에 묻지 않는다

    key = tilecache.key_text("vector", f"{name}|{lon}|{lat}|{VECTOR_CELL}")
    data = _cache_get(key)
    if data is None:
        try:
            if not vworld.enabled():
                raise vworld.VWorldError("VWorld 열쇠가 없다")
            data = vworld.get_features(name, lon, lat, lon + VECTOR_CELL, lat + VECTOR_CELL)
        except vworld.VWorldError as exc:
            data = _cache_get(key, stale=True)     # 빈 자리보다 옛것이 낫다
            if data is None:
                log.warning("모양을 받지 못했다 (%s %s,%s): %s", name, lon, lat, exc)
                return JsonResponse({"error": i18n.t(msg("VWorld 가 답하지 않는다"), lang),
                                     "features": []}, status=502)
        else:
            _cache_put(key, data)

    # 팝업에 보일 이름을 곁들인다. 캐시에는 받은 그대로 두고 내보낼 때만 붙인다
    out = []
    for f in data.get("features") or []:
        props = dict(f.get("properties") or {})
        popup = vworld.friendly(props, name)
        props["_popup"] = i18n.props_en(popup) if lang == "en" else popup
        out.append(dict(f, properties=props))
    return _vector_response({"type": "FeatureCollection", "features": out})


def _vector_response(data):
    response = JsonResponse(data)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


# ── 점 레이어 (그린란드 정부 포털·NPI) ─────────────────────────────────
#
# 타일이 아니라 점을 통째로 받아 브라우저에 한 덩이로 준다 (`grportal.py` 019,
# `npolar.py` 021 — 받은 것을 줄이는 틀은 `arcpoints.py` 하나다).
# 캐시의 규칙은 타일과 같다 — 들고 있으면 묻지 않고, 3 년이 지나면 다시 묻고,
# 상류가 못 주면 옛것을 낸다. 담는 것은 feature 목록(JSON)이다.

_point_locks = {}

#: 점 레이어의 문. (알아보기, 받기, 싸기, 캐시 열쇠, 오류)
_POINT_DOORS = (
    ("grportal", grportal.knows, grportal, grportal.PortalError),
    ("npolar", npolar.knows_points, npolar, npolar.NpolarError),
    ("phyloserver", phyloserver.knows, phyloserver, phyloserver.PhyloserverError),
)
POINT_ERRORS = tuple(door[3] for door in _POINT_DOORS)


def _point_door(name: str):
    for key, knows, module, _ in _POINT_DOORS:
        if knows(name):
            return key, module
    return None, None


def _point_key(name: str) -> str:
    key, module = _point_door(name)
    return tilecache.key_text(key, module.signature(name))


def point_features(name: str, *, refresh: bool = False) -> bytes:
    """레이어 하나의 feature 목록(JSON 바이트). 못 받으면 그 문의 오류(`POINT_ERRORS`).

    같은 레이어를 두 사람이 한꺼번에 열어도 **상류에는 한 번만 묻는다** —
    2 만 점이면 열 장이다. 뒤에 온 사람은 앞사람이 받는 것을 기다린다.
    """
    _, module = _point_door(name)
    key = _point_key(name)
    # 날마다 바뀌는 상류(phyloserver 의 암맥, 026)는 하루면 다시 묻는다
    fresh = getattr(module, "FRESH_SECONDS", None)
    if not refresh:
        hit = tilecache.get(key, ".json", max_age=fresh)
        if hit is not None:
            return hit
    lock = _point_locks.setdefault(name, threading.Lock())
    with lock:
        if not refresh:
            hit = tilecache.get(key, ".json", max_age=fresh)   # 기다리는 사이 앞사람이 담았다
            if hit is not None:
                return hit
        try:
            features = module.fetch(name)
        except POINT_ERRORS:
            old = tilecache.get(key, ".json", stale=True)
            if old is not None:
                return old
            raise
        data = json.dumps(features, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        tilecache.put(key, data, ".json")
        return data


@gzip_page
@require_GET
def point_layer(request):
    """점 레이어 하나를 GeoJSON 으로. 2 만 점이 4.5 MB, 줄이면(gzip) 0.4 MB 다."""
    lang = i18n.lang_of(request)
    name = request.GET.get("layer", "")
    if _lab_only(name):
        return JsonResponse({"error": i18n.t(msg("그런 점 레이어가 없다"), lang)}, status=404)
    if janmayen.knows(name):
        return _janmayen_layer(name, lang)
    if geo3al.knows(name):
        return _geo3al_layer(name, lang)
    _, module = _point_door(name)
    # 지명은 레이어가 아니라 찾기 칸의 것이다 — 통째로 내주지 않는다
    if module is None or name == PLACE_NAMES:
        return JsonResponse({"error": i18n.t(msg("그런 점 레이어가 없다"), lang)}, status=404)
    try:
        features = point_features(name)
    except POINT_ERRORS as exc:
        log.warning("점 레이어를 받지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang)}, status=502)
    response = HttpResponse(module.body(name, features), content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


#: 스발바르 지명 8 393 — 찾기 칸이 뒤진다 (npolar.py, devlog 021)
PLACE_NAMES = "npolar:place_names"


@require_GET
def place_names(request):
    """스발바르 지명 찾기. 한국의 `search/`(VWorld) 자리다. 지명을 한 번 통째로
    받아 두고(아홉 장) 그 안에서 찾는다 — 찾을 때마다 상류에 묻지 않는다."""
    lang = i18n.lang_of(request)
    query = (request.GET.get("q") or "").strip()[:100]
    if not query:
        return JsonResponse({"results": []})
    try:
        features = json.loads(point_features(PLACE_NAMES))
    except (npolar.NpolarError, ValueError) as exc:
        log.warning("스발바르 지명을 받지 못했다: %s", exc)
        return JsonResponse({"error": i18n.t(msg("상류에서 받지 못했다"), lang)}, status=502)
    return JsonResponse({"results": npolar.match_places(features, query)})


def _janmayen_layer(name, lang):
    """얀마옌 지질도 한 레이어 (022). 파일이 없으면 503 으로 까닭을 말한다 —
    화면은 그 글을 레이어 패널에 띄우고, 나머지는 그대로 돈다."""
    if not janmayen.available(name):
        return JsonResponse({"error": i18n.t(msg("얀마옌 지질도 자료(NPI)가 서버에 없다"), lang)},
                            status=503)
    try:
        content = janmayen.body(name, lang)
    except (janmayen.JanMayenError, OSError, ValueError) as exc:
        log.warning("얀마옌 지질도를 읽지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("얀마옌 지질도 자료(NPI)를 읽지 못했다"), lang)},
                            status=500)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _geo3al_layer(name, lang):
    """중국 지질도(USGS geo3al) 한 레이어 (025). 꼴과 까닭은 `_janmayen_layer` 와 같다."""
    if not geo3al.available():
        return JsonResponse({"error": i18n.t(msg("중국 지질도 자료(USGS geo3al)가 서버에 없다"), lang)},
                            status=503)
    try:
        content = geo3al.body(name, lang)
    except (geo3al.Geo3alError, OSError, ValueError) as exc:
        log.warning("geo3al 을 읽지 못했다 (%s): %s", name, exc)
        return JsonResponse({"error": i18n.t(msg("중국 지질도 자료(USGS geo3al)를 읽지 못했다"), lang)},
                            status=500)
    response = HttpResponse(content, content_type="application/geo+json")
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _geomap_legend(request, layer):
    """GeoMAP 범례는 스타일 표에서 그때그때 그린다 — 파일도 상류도 타지 않는다."""
    try:
        content, ctype = geomap.get_legend(layer)
    except (geomap.GeomapError, OSError, ValueError) as exc:
        log.info("GeoMAP 범례를 그리지 못했다 (%s): %s", layer, exc)
        return JsonResponse({"error": i18n.t(msg("범례를 받지 못했다"), i18n.lang_of(request))},
                            status=500)
    response = HttpResponse(content, content_type=ctype)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


# ── 점묶음 ────────────────────────────────────────────────────────────

def _pointset_summary(ps):
    shapes = list(ps.shapes.values_list("kind", flat=True))
    elevated = ps.points.filter(elev__isnull=False).count()
    return {
        "id": ps.id,
        "name": ps.name,
        "color": ps.color,
        "visible": ps.visible,
        "count": ps.points.count(),
        "lines": shapes.count("line"),
        "polygons": shapes.count("polygon"),
        "elevated": elevated,
    }


def _pointset_list():
    return [_pointset_summary(ps) for ps in PointSet.objects.all()]


@require_GET
def pointset_index(request):
    return JsonResponse({"pointsets": _pointset_list()})


@require_POST
def pointset_upload(request):
    lang = i18n.lang_of(request)
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": i18n.t(msg("올린 파일이 없다"), lang)}, status=400)

    try:
        code = request.POST.get("crs") or "4326"
        points, notes = pointsets.parse(upload.name, upload.read(),
                                        crs_code=code if code in crs.SYSTEMS else "4326")
    except pointsets.UploadError as exc:
        return JsonResponse({"error": i18n.t(exc.args[0], lang)}, status=400)

    name = (request.POST.get("name") or "").strip() or upload.name.rsplit(".", 1)[0]
    color = (request.POST.get("color") or "").strip() or "#e4572e"

    with transaction.atomic():
        pointset = PointSet.objects.create(
            name=name[:120], source_filename=upload.name[:255], color=color[:7])
        Point.objects.bulk_create([
            Point(pointset=pointset, lat=p["lat"], lon=p["lon"],
                  label=p["label"][:200], props=p["props"])
            for p in points if "geometry" not in p
        ])
        Shape.objects.bulk_create([
            Shape(pointset=pointset, kind=p["kind"], geometry=p["geometry"],
                  lat=p["lat"], lon=p["lon"], label=p["label"][:200], props=p["props"])
            for p in points if "geometry" in p
        ])

    summary = _pointset_summary(pointset)
    log.info("점묶음 '%s' 생겼다 — 점 %d, 선 %d, 면 %d", pointset.name,
             summary["count"], summary["lines"], summary["polygons"])
    return JsonResponse({
        "pointset": summary,
        "notes": [i18n.t(note, lang) for note in notes],
    })


@require_POST
def pointset_create(request):
    """찍어 둔 점을 **목록으로 저장한다.** 구글 지도의 "장소 저장" 과 같은 자리다.

    지도에서 찍은 점은 새로 고치면 사라지는 임시 표시다. 그러다 "이건 남겨야
    겠다" 싶은 때가 오는데, 그때 파일로 내보냈다 다시 올리게 하면 아무도 안
    한다. 그래서 있는 그대로 점묶음이 되게 했다.

    받는 것: `{"name": "...", "color": "#rrggbb", "points": [{lat, lon, label}]}`
    """
    lang = i18n.lang_of(request)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": i18n.t(msg("읽지 못했다"), lang)}, status=400)

    rows = payload.get("points") or []
    shape_rows = payload.get("shapes") or []
    if not rows and not shape_rows:
        return JsonResponse({"error": i18n.t(msg("저장할 점이 없다"), lang)}, status=400)
    if len(rows) > MAX_SAVED_POINTS:
        return JsonResponse(
            {"error": i18n.t(msg("한 번에 {n}점까지 저장한다", n=MAX_SAVED_POINTS), lang)},
            status=400)

    points = []
    for row in rows:
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        points.append((lat, lon, str(row.get("label") or "")[:200]))
    # 잡은 범위·잰 선·면. 올린 GeoJSON 과 같은 거름을 탄다
    shapes = []
    for row in shape_rows[:MAX_SAVED_SHAPES]:
        geom = (row or {}).get("geometry") or {}
        if geom.get("type") not in pointsets.SHAPE_KINDS:
            continue
        try:
            shape = pointsets._shape_from(geom)
        except pointsets.UploadError as exc:
            return JsonResponse({"error": i18n.t(exc.args[0], lang)}, status=400)
        if shape:
            shape.pop("vertices")
            props = row.get("props") if isinstance(row.get("props"), dict) else {}
            shapes.append(dict(shape, label=str(row.get("label") or "")[:200], props=props))
    if not points and not shapes:
        return JsonResponse({"error": i18n.t(msg("쓸 만한 좌표가 없다"), lang)}, status=400)

    name = (payload.get("name") or "").strip() or "찍은 점"
    color = (payload.get("color") or "").strip() or "#27456f"

    with transaction.atomic():
        pointset = PointSet.objects.create(
            name=name[:120], source_filename="", color=color[:7])
        Point.objects.bulk_create([
            Point(pointset=pointset, lat=lat, lon=lon, label=label)
            for lat, lon, label in points
        ])
        Shape.objects.bulk_create([
            Shape(pointset=pointset, kind=s["kind"], geometry=s["geometry"],
                  lat=s["lat"], lon=s["lon"], label=s["label"], props=s["props"])
            for s in shapes
        ])

    log.info("찍은 점 %d개·모양 %d개를 '%s' 로 저장했다", len(points), len(shapes), pointset.name)
    return JsonResponse({"pointset": _pointset_summary(pointset)})


#: 표고 타일에서 읽은 고도를 GeoJSON 에 싣는 이름(P03). "고도" 로 하지 않는 것은 원본의
#: `고도` 열(실측)과 부딪히지 않게 하려는 것이다. 되살리기(`pointsets.restore`)가 이 둘을 떼어
#: 제 칸으로 돌린다
ELEV_PROP, ELEV_SOURCE_PROP = "표고(DEM)", "표고 출처"


def _point_props(p) -> dict:
    props = dict(p.props, **{"이름표": p.label} if p.label else {})
    if p.elev is not None:
        props[ELEV_PROP] = round(p.elev, 1)
        props[ELEV_SOURCE_PROP] = p.elev_source
    return props


def _pointset_features(pointset) -> dict:
    """점묶음 하나를 GeoJSON FeatureCollection 으로. 내려받기와 지울 때의 사본이 쓴다."""
    return {
        "type": "FeatureCollection",
        "name": pointset.name,
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p.lon, p.lat]},
            "properties": _point_props(p),
        } for p in pointset.points.all()] + [{
            "type": "Feature",
            "geometry": s.geometry,
            "properties": dict(s.props, **{"이름표": s.label} if s.label else {}),
        } for s in pointset.shapes.all()],
    }


@require_GET
def pointset_geojson(request, pk):
    """점묶음을 GeoJSON 으로. 지도가 그릴 때도, 사람이 내려받을 때도 쓴다.

    `?download=1` 이면 파일로 내려준다. 한글 이름이 깨지지 않게 파일명을
    RFC 5987 로도 적는다.
    """
    pointset = get_object_or_404(PointSet, pk=pk)
    response = JsonResponse(_pointset_features(pointset),
                            json_dumps_params={"ensure_ascii": False})
    if request.GET.get("download"):
        from urllib.parse import quote
        stem = re.sub(r'[\\/:*?"<>|]+', "_", pointset.name).strip() or f"pointset-{pk}"
        response["Content-Type"] = "application/geo+json; charset=utf-8"
        response["Content-Disposition"] = (
            f'attachment; filename="pointset-{pk}.geojson"; '
            f"filename*=UTF-8''{quote(stem + '.geojson')}")
    return response


@require_POST
def pointset_delete(request, pk):
    """지운다. **지우기 전에 기록과 사본을 남긴다** (`PointSetDeletion`)."""
    pointset = get_object_or_404(PointSet, pk=pk)
    summary = _pointset_summary(pointset)
    client = _client(request)
    with transaction.atomic():
        PointSetDeletion.objects.create(
            name=pointset.name, color=pointset.color,
            source_filename=pointset.source_filename, created_at=pointset.created_at,
            client=client, points=summary["count"], lines=summary["lines"],
            polygons=summary["polygons"], snapshot=_pointset_features(pointset))
        pointset.delete()
    log.info("점묶음 '%s' 지웠다 — 점 %d, 선 %d, 면 %d (%s)", summary["name"],
             summary["count"], summary["lines"], summary["polygons"], client)
    return JsonResponse({"ok": True})


@require_GET
def pointset_deleted(request):
    """최근 지운 점묶음 20 개. 설정의 "지금 상태" 가 부른다. 사본은 싣지 않는다."""
    return JsonResponse({"deleted": [{
        "id": d.id, "name": d.name, "deleted_at": d.deleted_at.isoformat(),
        "client": d.client, "points": d.points, "lines": d.lines, "polygons": d.polygons,
        "restored": bool(d.restored_at),
    } for d in PointSetDeletion.objects.all()[:20]]})


@require_POST
def pointset_restore(request, pk):
    """지운 점묶음을 되살린다. 한 기록은 한 번만 — 두 번 누르면 두 벌이 생긴다."""
    lang = i18n.lang_of(request)
    gone = get_object_or_404(PointSetDeletion, pk=pk)
    if gone.restored_at:
        return JsonResponse({"error": i18n.t(msg("이미 되살렸다"), lang)}, status=409)
    ps, _, _ = pointsets.restore(gone)
    log.info("지운 점묶음 '%s' 을 되살렸다 (%s)", ps.name, _client(request))
    return JsonResponse({"pointset": _pointset_summary(ps)})


#: 한 번의 요청 안에서 채우는 점의 수. 넘으면 명령(`fill_elevation`)으로 채운다.
#: 극지는 한 점에 한 번 PGC 에 묻고 사이를 두어 따로 적게 둔다
ELEV_IN_REQUEST = 2000
ELEV_POLAR_IN_REQUEST = 100


def fill_elevation(pointset, *, only_missing: bool = False, pause: float = elevation.PGC_PAUSE) -> tuple:
    """점묶음의 점마다 표고를 채운다. (채운 수, 못 읽은 수). 명령과 화면이 함께 쓴다.
    다시 부르면 덮는다 — 원천이 판을 올리면 출처 칸이 달라져 알아볼 수 있다(P03 §3)."""
    points = pointset.points.all()
    if only_missing:
        points = points.filter(elev__isnull=True)
    rows = {p.id: p for p in points}
    got = elevation.elevations({pid: (p.lat, p.lon) for pid, p in rows.items()}, pause=pause)
    for pid, (value, source) in got.items():
        p = rows[pid]
        p.elev, p.elev_source, p.elev_datum = round(value, 1), source, elevation.SOURCES[source][1]
    Point.objects.bulk_update([rows[pid] for pid in got], ["elev", "elev_source", "elev_datum"])
    return len(got), len(rows) - len(got)


@require_POST
def pointset_elevation(request, pk):
    """`POST pointsets/<번호>/elevation/` — 점마다 표고를 채운다 (P03)."""
    lang = i18n.lang_of(request)
    ps = PointSet.objects.filter(pk=pk).first()
    if ps is None:
        return JsonResponse({"error": i18n.t(msg("그런 점묶음이 없다"), lang)}, status=404)
    total = ps.points.count()
    polar = ps.points.filter(Q(lat__gte=elevation.POLAR_LAT) | Q(lat__lte=-elevation.POLAR_LAT)).count()
    if total > ELEV_IN_REQUEST or polar > ELEV_POLAR_IN_REQUEST:
        return JsonResponse({"error": i18n.t(msg("점이 많아 화면에서 채우지 않는다 — 서버에서 "
                                                 "manage.py fill_elevation {id} 를 부른다", id=ps.id), lang)},
                            status=400)
    try:
        filled, missed = fill_elevation(ps)
    except elevation.ElevationError as exc:
        log.warning("표고를 채우지 못했다 (%s): %s", ps.id, exc)
        return JsonResponse({"error": i18n.t(msg("표고를 받지 못했다"), lang)}, status=502)
    return JsonResponse({"filled": filled, "missed": missed, "pointset": _pointset_summary(ps)})


@require_GET
def dem_tile(request, z, x, y):
    """3D 의 촘촘한 지형 — Terrarium 꼴 표고 타일 (`dem/<z>/<x>/<y>.png`).

    위도 60° 너머는 PGC ArcticDEM·REMA(2 m, 032), 일본은 국토지리원(10 m, 031)을 옮긴다.
    그 밖이거나 못 만들면 AWS 로 넘긴다(302). 3D 는 그 두 자리의 타일만 여기로 부른다."""
    z, x, y = int(z), int(x), int(y)
    if not (0 <= x < 2 ** z and 0 <= y < 2 ** z) or z > elevation.POLAR_MAX_ZOOM:
        return JsonResponse({"error": i18n.t(msg("그런 타일은 없다"), i18n.lang_of(request))}, status=404)
    n = 2 ** z
    lon = (x + 0.5) / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 0.5) / n))))
    png = None
    try:
        if abs(lat) >= elevation.POLAR_LAT:
            if z >= elevation.POLAR_MIN_ZOOM:
                png = elevation.polar_terrarium(z, x, y)
        elif z <= elevation.GSI_ZOOM and elevation.in_japan(lat, lon):
            png = elevation.japan_terrarium(z, x, y)
    except (elevation.ElevationError, OSError, ValueError) as exc:
        log.info("표고 타일을 못 만들어 AWS 로 넘긴다 (%s/%s/%s): %s", z, x, y, exc)
        png = None
    if png is None:
        response = HttpResponse(status=302)
        response["Location"] = elevation.TERRARIUM_URL.format(z=z, x=x, y=y)
        return response
    return _tile(png)


def _client(request) -> str:
    """지운 곳. nginx 가 붙여 주는 X-Real-IP 가 먼저다 (deploy/nginx)."""
    return (request.META.get("HTTP_X_REAL_IP")
            or request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
            or request.META.get("REMOTE_ADDR", ""))[:64]


# ── 주소 (VWorld) ─────────────────────────────────────────────────────
#
# KIGAM 을 타지 않는다. 문은 `vworld.py` 다. 받은 것은 타일처럼 캐시에
# 담는다 — 주소는 지질도보다도 드물게 바뀐다.

def _cache_get(key, *, stale=False):
    raw = tilecache.get(key, ".json", stale=stale)
    try:
        return json.loads(raw) if raw is not None else None
    except ValueError:
        return None


def _cache_put(key, data):
    tilecache.put(key, json.dumps(data, ensure_ascii=False).encode("utf-8"), ".json")


def _vworld_cached(key, fetch, lang):
    """캐시 → VWorld → (실패하면) 늙은 캐시. 셋 다 없으면 오류 응답."""
    data = _cache_get(key)
    if data is not None:
        return data, None
    if not vworld.enabled():
        return None, JsonResponse(
            {"error": i18n.t(msg("주소 검색이 꺼져 있다 — VWorld 열쇠가 없다"), lang)}, status=503)
    try:
        data = fetch()
    except vworld.VWorldError as exc:
        old = _cache_get(key, stale=True)
        if old is not None:
            return old, None
        log.warning("VWorld 에서 받지 못했다: %s", exc)
        return None, JsonResponse(
            {"error": i18n.t(msg("VWorld 가 답하지 않는다"), lang)}, status=502)
    _cache_put(key, data)
    return data, None


@require_GET
def place_search(request):
    """주소·장소·행정구역 검색. 화면 아래 검색 칸이 부른다.

    좌표는 여기 오지 않는다 — 브라우저가 먼저 `coords/parse/` 로 물어보고,
    좌표가 아닐 때만 여기로 온다.
    """
    lang = i18n.lang_of(request)
    query = (request.GET.get("q") or "").strip()[:100]
    if not query:
        return JsonResponse({"results": []})
    data, error = _vworld_cached(tilecache.key_text("search", query),
                                 lambda: {"results": vworld.search(query)}, lang)
    return error or JsonResponse(data)


@require_GET
def whereis(request):
    """좌표 → 지번·도로명. 속성 팝업의 위경도 밑에 붙는다."""
    lang = i18n.lang_of(request)
    try:
        # 다섯째 자리(약 1 m)에서 자른다. 같은 자리를 두 번 묻지 않으려는 것이다
        lat = round(float(request.GET["lat"]), 5)
        lon = round(float(request.GET["lon"]), 5)
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": i18n.t(msg("좌표로 읽지 못했다"), lang)}, status=400)
    data, error = _vworld_cached(tilecache.key_text("whereis", f"{lat},{lon}"),
                                 lambda: vworld.reverse(lat, lon), lang)
    return error or JsonResponse(data)


# ── 좌표 ──────────────────────────────────────────────────────────────

@require_GET
def coord_parse(request):
    """찍어 넣은 좌표 한 줄을 읽는다.

    화면 아래 늘 떠 있는 좌표는 브라우저가 스스로 그린다 — 마우스가 움직일
    때마다 서버를 부를 수는 없다. 여기로 오는 것은 **사람이 입력칸에 넣고
    누른 한 번**뿐이고, 도분초·반구 글자까지 받아내는 까다로운 쪽이라
    파이썬에 두고 시험한다.
    """
    lang = i18n.lang_of(request)
    code = request.GET.get("crs", "4326")
    swapped = False
    if crs.is_planar(code):
        q = request.GET.get("q", "")
        not_read = JsonResponse({"error": i18n.t(msg("{name} 좌표로 읽지 못했다 — 한반도 밖으로 간다",
                                                     name=crs.SYSTEMS[code][0]), lang)}, status=400)
        labelled = crs.labelled_pair(q)
        if labelled:
            # 동·북 이름을 붙여 적었으면 그대로 읽는다
            lat, lon = crs.to_latlon(code, *labelled)
            if not crs.in_korea(lat, lon):
                return not_read
        else:
            nums = crs.two_numbers(q)
            found = crs.candidates(code, *nums) if nums else []
            if not found:
                return not_read
            if len(found) == 2:
                # **두 차례가 다 말이 되면 고르지 않는다.** 중부원점에서는 동·북을
                # 뒤바꿔도 둘 다 한반도 안에 떨어지는 일이 있다 — 사람이 고른다
                return JsonResponse({"candidates": [
                    {"lat": la, "lon": lo, "order": order,
                     "east": nums[0] if order == "en" else nums[1],
                     "north": nums[1] if order == "en" else nums[0]}
                    for la, lo, order in found]})
            lat, lon, order = found[0]
            swapped = order == "ne"
    else:
        pair = coords.parse(request.GET.get("q", ""))
        if pair is None:
            return JsonResponse({"error": i18n.t(msg("좌표로 읽지 못했다"), lang)}, status=400)
        lat, lon = pair
    return JsonResponse({"lat": lat, "lon": lon, "swapped": swapped,
                         "dms": coords.format_pair(lon, lat, dms=True)})


@require_GET
def coord_project(request):
    """위경도 → 고른 평면 좌표계. 팝업의 한 줄이 부른다."""
    code = request.GET.get("crs", "")
    try:
        lat, lon = float(request.GET["lat"]), float(request.GET["lon"])
    except (KeyError, TypeError, ValueError):
        return JsonResponse({"error": "lat·lon"}, status=400)
    if not crs.is_planar(code):
        return JsonResponse({"error": "crs"}, status=400)
    east, north = crs.from_latlon(code, lat, lon)
    return JsonResponse({"crs": code, "east": round(east, 2), "north": round(north, 2)})


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
