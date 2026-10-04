"""높이 그래프 밑의 지질 띠 (wetherilli 180). 문이 아니다 — 우리 디스크의 파일만 읽는다.

잰 선을 높이 그래프와 **같은 점**으로 나눠(`crs.great_circle_points` — 달·화성·수성의 `trek.profile_points` 와 경위도가
같다) 점마다 드는 지질 단위를 읽는다. 점마다 속성을 물어야 하므로 **상류에 묻는 레이어는 띠를 내지 않는다** — 한 선에
수백 번이라 호출 제한(devlog 010)에 걸린다. 그래서 파일로 그리는 다섯만 받는다: 남극 GeoMAP, 중국 geo3al(연구실 내부용),
달 원도·화성 옛 지질도·수성 지질도.

돌려주는 꼴은 `{"layer", "band": [단위 번호 또는 None…], "units": [{"label", "color"}…]}` — 띠는 점의 차례 그대로다.
"""
from . import crs, geo3al, geomap, marsmap, mercurymap, moonmap

#: 한 선에 찍는 점의 수 끝 — 높이 그래프(`elevation`·`trek` 의 `PROFILE_MAX_POINTS`)와 같다
MAX_POINTS = 512
MAX_VERTICES = 200

#: 몸이 지구가 아닌 레이어 — 화면(`moon.js`·`mars.js`·`mercury.js`)이 부르는 이름
BODY_LAYERS = {"moon:orig-units": "moon", "mars:orig-units": "mars", "mercury:units": "mercury"}


class BandError(RuntimeError):
    pass


def knows(layer: str) -> bool:
    return layer in geomap.BAND_LAYERS or geo3al.knows(layer) or layer in BODY_LAYERS


def available(layer: str) -> bool:
    if layer in geomap.BAND_LAYERS:
        return geomap.available()
    if geo3al.knows(layer):
        return geo3al.available()
    return {"moon": moonmap, "mars": marsmap, "mercury": mercurymap}[BODY_LAYERS[layer]].available()


def _moon(info):
    return (" · ".join(v for v in (info["unit"], info.get("name")) if v), info["color"])


def _mars(info):
    return (" · ".join(v for v in (info["unit"], info.get("name")) if v), info["color"])


def _mercury(info):
    return (" · ".join(v for v in (info["unit"], (info.get("group") or "").capitalize()) if v), info["color"])


def _identify(module, label, points):
    out = []
    for lon, lat in points:
        info = module.identify(lon, lat)
        out.append(label(info) if info else None)
    return out


def band(layer: str, vertices: list, n: int, lang: str = "ko") -> dict:
    n = max(2, min(int(n), MAX_POINTS))
    points = [(lon, lat) for lon, lat, _ in crs.great_circle_points(vertices, n)]
    try:
        if layer in geomap.BAND_LAYERS:
            rules = geomap.style_of(layer).rules
            hits = [None if r is None else (rules[r].get("label") or "", geomap.band_color(rules[r]))
                    for r in geomap.units_along(layer, [geomap.lonlat_to_3031(lon, lat) for lon, lat in points])]
        elif geo3al.knows(layer):
            hits = geo3al.units_along(layer, points, lang)
        elif layer == "moon:orig-units":
            hits = _identify(moonmap, _moon, points)
        elif layer == "mars:orig-units":
            hits = _identify(marsmap, _mars, points)
        elif layer == "mercury:units":
            hits = _identify(mercurymap, _mercury, points)
        else:
            raise BandError(f"띠를 그리지 않는 레이어다: {layer}")
    except (geomap.GeomapError, geo3al.Geo3alError, moonmap.MoonMapError, marsmap.MarsMapError,
            mercurymap.MercuryMapError, OSError) as exc:
        raise BandError(str(exc)) from exc
    units, index = [], {}
    for hit in hits:
        if hit is not None and hit not in index:
            index[hit] = len(units)
            units.append({"label": hit[0], "color": hit[1]})
    return {"layer": layer, "band": [None if h is None else index[h] for h in hits], "units": units}
