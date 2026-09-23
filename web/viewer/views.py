"""화면 하나, 프록시 둘, 점묶음 넷.

프록시가 있는 까닭은 인증키다 — 브라우저는 키를 모른 채 `/wms/` 를 부르고,
여기서 키를 붙여 상류로 넘긴다. CLAUDE.md 의 "인증키" 를 볼 것.
"""
import json
import logging

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET, require_POST

from . import coords, kigam, pointsets, tiles
from .models import Layer, LayerGroup, Point, PointSet

log = logging.getLogger(__name__)

#: 레이어 하나가 팝업에 내놓는 속성 덩이의 최대 수. 겹친 폴리곤을 추린
#: 뒤에도 여럿 남을 수 있어 둔다 — 팝업이 길어지면 읽히지 않는다.
MAX_FEATURES = 3


# ── 화면 ──────────────────────────────────────────────────────────────

@require_GET
def map_view(request):
    return render(request, "viewer/map.html", {
        "catalog": json.dumps(_catalog(), ensure_ascii=False),
        "pointsets": json.dumps(_pointset_list(), ensure_ascii=False),
        "has_key": kigam.has_key(),
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

    if not kigam.has_key():
        return _tile(tiles.notice_tile(width, height, "인증키가 없다 — .env 의 GSM_KIGAM_KEY"))

    params.setdefault("format", "image/png")
    params.setdefault("transparent", "true")
    try:
        content, ctype = kigam.get_map(params)
    except kigam.UpstreamError as exc:
        log.warning("타일을 받지 못했다: %s", exc)
        return _tile(tiles.notice_tile(width, height, "상류가 지도를 주지 않았다"))

    response = HttpResponse(content, content_type=ctype)
    if settings.TILE_CACHE_SECONDS > 0:
        response["Cache-Control"] = f"public, max-age={settings.TILE_CACHE_SECONDS}"
    return response


def _tile(png: bytes):
    response = HttpResponse(png, content_type="image/png")
    response["Cache-Control"] = "no-store"     # 키가 생기면 곧바로 진짜가 뜨게 한다
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
        props = {k: v for k, v in (feature.get("properties") or {}).items()
                 if v not in (None, "", "null")}
        if not props:
            continue
        mark = tuple(sorted((k, str(v)) for k, v in props.items()))
        if mark in seen:
            continue
        seen.add(mark)
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
    if not kigam.has_key():
        return JsonResponse({"error": "인증키가 없다"}, status=503)
    try:
        content, ctype = kigam.get_legend(layer)
    except kigam.UpstreamError as exc:
        log.info("범례를 받지 못했다 (%s): %s", layer, exc)
        return JsonResponse({"error": str(exc)}, status=502)
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
