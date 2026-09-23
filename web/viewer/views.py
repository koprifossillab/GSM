"""화면 하나, 프록시 둘, 점묶음 넷.

프록시가 있는 까닭은 인증키다 — 브라우저는 키를 모른 채 `/wms/` 를 부르고,
여기서 키를 붙여 상류로 넘긴다. CLAUDE.md 의 "인증키" 를 볼 것.
"""
import json
import logging
import re

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from gsmweb.version import VERSION

from . import coords, kigam, patchnotes, pointsets, tilecache, tiles
from .models import Layer, LayerGroup, Point, PointSet

log = logging.getLogger(__name__)

#: 레이어 하나가 팝업에 내놓는 속성 덩이의 최대 수. 겹친 폴리곤을 추린
#: 뒤에도 여럿 남을 수 있어 둔다 — 팝업이 길어지면 읽히지 않는다.
MAX_FEATURES = 3

#: 찍어 둔 점을 한 번에 목록으로 저장할 수 있는 수. 손으로 찍는 것이라
#: 이보다 많을 일이 드물고, 한계가 없으면 한 번의 요청이 얼마든 커진다.
MAX_SAVED_POINTS = 2000

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

@require_GET
def map_view(request):
    return render(request, "viewer/map.html", {
        "catalog": json.dumps(_catalog(), ensure_ascii=False),
        "pointsets": json.dumps(_pointset_list(), ensure_ascii=False),
        "has_key": kigam.has_key(),
        "dev_direct": settings.DEV_DIRECT_WMS,
        # 브라우저가 직접 VWorld 를 부른다. 까닭은 settings.VWORLD_KEY.
        "vworld_key": settings.VWORLD_KEY,
        "version": VERSION,
    })


# ── 카탈로그 ──────────────────────────────────────────────────────────

def _catalog():
    groups = []
    for group in LayerGroup.objects.prefetch_related("layers").all():
        layers = [{
            "name": l.name,
            "title": l.title,
            "bbox": l.bbox,
            "queryable": l.queryable,
            "verified": bool(l.verified_at),
            "abstract": l.abstract,
        } for l in group.layers.filter(enabled=True)]
        if layers:
            groups.append({"name": group.name, "layers": layers})
    return groups


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
    return JsonResponse({"groups": _catalog()})


# ── 상류 프록시 ───────────────────────────────────────────────────────

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

    # 들고 있으면 상류에 묻지 않는다. **인증키가 없어도 캐시는 내준다** —
    # 이미 받아둔 그림이고, 다시 받을 일이 없으니 막을 까닭이 없다.
    cache_key = tilecache.key_for("map", params)
    hit = tilecache.get(cache_key)
    if hit is not None:
        return _tile(hit, cached=True)

    if not kigam.has_key():
        return _tile(tiles.notice_tile(width, height, tiles.NO_KEY), store=False)

    try:
        content, ctype = kigam.get_map(params)
    except kigam.UpstreamError as exc:
        log.warning("타일을 받지 못했다: %s", exc)
        return _tile(tiles.notice_tile(width, height, tiles.NO_MAP), store=False)

    # 안내 타일은 캐시에 넣지 않는다 — 위에서 store=False 로 갈라 둔 까닭이다.
    tilecache.put(cache_key, content)

    response = HttpResponse(content, content_type=ctype)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    response["X-GSM-Cache"] = "miss"
    return response


def _tile(png: bytes, *, cached: bool = False, store: bool = True):
    """안내 타일과 캐시에서 꺼낸 타일을 같은 문으로 내보낸다.

    안내 타일은 `store=False` 다 — 브라우저가 들고 있으면 인증키가 생긴 뒤에도
    "키가 없다" 가 계속 뜬다. 캐시에서 꺼낸 것은 진짜 지도이므로 평소대로 둔다.
    """
    response = HttpResponse(png, content_type="image/png")
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
    if not kigam.has_key():
        return JsonResponse({"error": "인증키가 없다", "features": []}, status=503)

    params = kigam.clean_params(request.GET)
    params.setdefault("feature_count", "5")
    try:
        data = kigam.get_feature_info(params)
    except kigam.UpstreamError as exc:
        log.warning("속성을 읽지 못했다: %s", exc)
        return JsonResponse({"error": str(exc), "features": []}, status=502)

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
        features.append({"id": feature.get("id", ""), "props": props})
        if len(features) >= MAX_FEATURES:
            break
    return JsonResponse({"features": features})


@require_GET
def legend(request):
    """레이어 범례 이미지. 레이어 패널에서 펼쳐 볼 때 부른다."""
    layer = request.GET.get("layer", "")
    if not layer:
        return JsonResponse({"error": "layer 가 없다"}, status=400)

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

    if not kigam.has_key():
        return JsonResponse({"error": "인증키가 없다"}, status=503)
    try:
        content, ctype = kigam.get_legend(layer)
    except kigam.UpstreamError as exc:
        log.info("범례를 받지 못했다 (%s): %s", layer, exc)
        return JsonResponse({"error": str(exc)}, status=502)
    tilecache.put(cache_key, content)
    response = HttpResponse(content, content_type=ctype)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


# ── 점묶음 ────────────────────────────────────────────────────────────

def _pointset_list():
    return [{
        "id": ps.id,
        "name": ps.name,
        "color": ps.color,
        "visible": ps.visible,
        "count": ps.points.count(),
    } for ps in PointSet.objects.all()]


@require_GET
def pointset_index(request):
    return JsonResponse({"pointsets": _pointset_list()})


@require_POST
def pointset_upload(request):
    upload = request.FILES.get("file")
    if not upload:
        return JsonResponse({"error": "올린 파일이 없다"}, status=400)

    try:
        points, notes = pointsets.parse(upload.name, upload.read())
    except pointsets.UploadError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    name = (request.POST.get("name") or "").strip() or upload.name.rsplit(".", 1)[0]
    color = (request.POST.get("color") or "").strip() or "#e4572e"

    with transaction.atomic():
        pointset = PointSet.objects.create(
            name=name[:120], source_filename=upload.name[:255], color=color[:7])
        Point.objects.bulk_create([
            Point(pointset=pointset, lat=p["lat"], lon=p["lon"],
                  label=p["label"][:200], props=p["props"])
            for p in points
        ])

    log.info("점묶음 '%s' 생겼다 — %d점", pointset.name, len(points))
    return JsonResponse({
        "pointset": {"id": pointset.id, "name": pointset.name,
                     "color": pointset.color, "visible": True,
                     "count": len(points)},
        "notes": notes,
    })


@require_POST
def pointset_create(request):
    """찍어 둔 점을 **목록으로 저장한다.** 구글 지도의 "장소 저장" 과 같은 자리다.

    지도에서 찍은 점은 새로 고치면 사라지는 임시 표시다. 그러다 "이건 남겨야
    겠다" 싶은 때가 오는데, 그때 파일로 내보냈다 다시 올리게 하면 아무도 안
    한다. 그래서 있는 그대로 점묶음이 되게 했다.

    받는 것: `{"name": "...", "color": "#rrggbb", "points": [{lat, lon, label}]}`
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "읽지 못했다"}, status=400)

    rows = payload.get("points") or []
    if not rows:
        return JsonResponse({"error": "저장할 점이 없다"}, status=400)
    if len(rows) > MAX_SAVED_POINTS:
        return JsonResponse(
            {"error": f"한 번에 {MAX_SAVED_POINTS}점까지 저장한다"}, status=400)

    points = []
    for row in rows:
        try:
            lat, lon = float(row["lat"]), float(row["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        points.append((lat, lon, str(row.get("label") or "")[:200]))
    if not points:
        return JsonResponse({"error": "쓸 만한 좌표가 없다"}, status=400)

    name = (payload.get("name") or "").strip() or "찍은 점"
    color = (payload.get("color") or "").strip() or "#27456f"

    with transaction.atomic():
        pointset = PointSet.objects.create(
            name=name[:120], source_filename="", color=color[:7])
        Point.objects.bulk_create([
            Point(pointset=pointset, lat=lat, lon=lon, label=label)
            for lat, lon, label in points
        ])

    log.info("찍은 점 %d개를 '%s' 로 저장했다", len(points), pointset.name)
    return JsonResponse({"pointset": {
        "id": pointset.id, "name": pointset.name, "color": pointset.color,
        "visible": True, "count": len(points),
    }})


@require_GET
def pointset_geojson(request, pk):
    pointset = get_object_or_404(PointSet, pk=pk)
    return JsonResponse({
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [p.lon, p.lat]},
            "properties": dict(p.props, **{"이름표": p.label} if p.label else {}),
        } for p in pointset.points.all()],
    })


@require_POST
def pointset_delete(request, pk):
    pointset = get_object_or_404(PointSet, pk=pk)
    name = pointset.name
    pointset.delete()
    log.info("점묶음 '%s' 지웠다", name)
    return JsonResponse({"ok": True})


# ── 좌표 ──────────────────────────────────────────────────────────────

@require_GET
def coord_parse(request):
    """찍어 넣은 좌표 한 줄을 읽는다.

    화면 아래 늘 떠 있는 좌표는 브라우저가 스스로 그린다 — 마우스가 움직일
    때마다 서버를 부를 수는 없다. 여기로 오는 것은 **사람이 입력칸에 넣고
    누른 한 번**뿐이고, 도분초·반구 글자까지 받아내는 까다로운 쪽이라
    파이썬에 두고 시험한다.
    """
    pair = coords.parse(request.GET.get("q", ""))
    if pair is None:
        return JsonResponse({"error": "좌표로 읽지 못했다"}, status=400)
    lat, lon = pair
    return JsonResponse({"lat": lat, "lon": lon,
                         "dms": coords.format_pair(lon, lat, dms=True)})


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
