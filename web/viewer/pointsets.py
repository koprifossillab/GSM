"""올린 파일을 점묶음으로 읽는다. CSV 와 GeoJSON 둘뿐이다.

GeoJSON 은 **점·선·면을 다 받는다** (v0.5.1). 선·면은 `"geometry"` 를 단
항목으로 돌려주고, 뷰가 그것을 `Shape` 로 담는다. 점은 예전 그대로다.

**열 이름을 사람이 고르게 하지 않는다.** 위경도 열은 이름으로 알아낸다 —
현장에서 쓰는 표는 열 이름이 제각각이라(`lat`·`위도`·`Y`) 고르라고 물으면
올릴 때마다 묻게 된다. 못 알아내면 그때만 까닭을 적어 돌려준다.
"""
import csv
import io
import json

from . import coords
from .i18n import msg

#: 위도로 읽는 열 이름. 소문자로 견준다.
LAT_KEYS = ("lat", "latitude", "위도", "y", "lat_dd", "dd_lat", "북위")
LON_KEYS = ("lon", "lng", "long", "longitude", "경도", "x", "lon_dd", "dd_lon", "동경")
#: 이름표로 쓸 열. 없으면 이름표 없이 둔다.
LABEL_KEYS = ("label", "name", "이름", "이름표", "지점", "지점명", "site", "station", "id")


#: 선·면을 받는 GeoJSON 갈래. 여러 겹(Multi*)도 한 모양으로 둔다.
SHAPE_KINDS = {"LineString": "line", "MultiLineString": "line",
               "Polygon": "polygon", "MultiPolygon": "polygon"}
#: 꼭짓점 한도. 행정경계 한 장을 통째로 올리면 수십만 개다 — 그런 것은
#: 이 뷰어가 그릴 것이 아니라 상류 레이어로 볼 것이다.
MAX_VERTICES_PER_SHAPE = 50_000
MAX_VERTICES_TOTAL = 300_000


class UploadError(ValueError):
    """올린 것을 점묶음으로 읽지 못했을 때. 메시지는 사람에게 그대로 보인다."""


def parse(filename: str, raw: bytes):
    """(점 목록, 알림 목록) 을 돌려준다. 점 하나는 dict 다."""
    text = _decode(raw)
    if filename.lower().endswith((".geojson", ".json")) or text.lstrip().startswith("{"):
        return _from_geojson(text)
    return _from_csv(text)


def _decode(raw: bytes) -> str:
    """한글이 든 CSV 는 UTF-8 이거나 CP949 다. BOM 도 흔하다."""
    for encoding in ("utf-8-sig", "utf-8", "cp949", "euc-kr"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UploadError(msg("글자를 읽지 못했다. UTF-8 이나 CP949 로 저장해 다시 올린다."))


def _pick(fieldnames, wanted):
    lowered = {(f or "").strip().lower(): f for f in fieldnames}
    for key in wanted:
        if key in lowered:
            return lowered[key]
    return None


def _from_csv(text: str):
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        dialect = csv.excel                       # 열 하나뿐이면 재지 못한다
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        raise UploadError(msg("첫 줄에 열 이름이 없다."))

    lat_col = _pick(reader.fieldnames, LAT_KEYS)
    lon_col = _pick(reader.fieldnames, LON_KEYS)
    if not lat_col or not lon_col:
        raise UploadError(msg(
            "위경도 열을 찾지 못했다. 열 이름을 {lat} / {lon} 가운데 하나로 두고 "
            "다시 올린다. (읽은 열: {cols})",
            lat="·".join(LAT_KEYS[:4]), lon="·".join(LON_KEYS[:4]),
            cols=", ".join(reader.fieldnames)))
    label_col = _pick(reader.fieldnames, LABEL_KEYS)

    points, notes, skipped = [], [], 0
    for lineno, row in enumerate(reader, start=2):
        pair = _read_pair(row.get(lat_col), row.get(lon_col))
        if pair is None:
            skipped += 1
            if len(notes) < 5:
                notes.append(msg("{line}째 줄 — 좌표를 읽지 못해 건너뛰었다", line=lineno))
            continue
        lat, lon = pair
        # 위경도와 이름표로 쓴 열은 속성에서 뺀다. 넣어 두면 팝업에
        # 이름표가 두 번 뜬다 — 위에 한 번, 표 안에 또 한 번.
        used = (lat_col, lon_col, label_col)
        props = {k: v for k, v in row.items()
                 if k not in used and v not in (None, "")}
        points.append({"lat": lat, "lon": lon,
                       "label": (row.get(label_col) or "").strip() if label_col else "",
                       "props": props})

    if not points:
        raise UploadError(msg("좌표를 하나도 읽지 못했다."))
    if skipped > len(notes):
        notes.append(msg("…모두 {n}줄을 건너뛰었다", n=skipped))
    return points, notes


def _read_pair(lat_raw, lon_raw):
    """십진도가 먼저다. 안 되면 도분초로 읽어 본다."""
    if lat_raw is None or lon_raw is None:
        return None
    lat_raw, lon_raw = str(lat_raw).strip(), str(lon_raw).strip()
    if not lat_raw or not lon_raw:
        return None
    try:
        lat, lon = float(lat_raw), float(lon_raw)
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except ValueError:
        pass
    return coords.parse(f"{lat_raw} {lon_raw}")


def _clean_coords(coords, depth, counter):
    """좌표를 숫자·범위로 걸러 소수 일곱째 자리(약 1 cm)에서 자른다.

    `depth` 는 겹 수다 — LineString 2, Polygon 3, MultiPolygon 4.
    잘못된 것이 하나라도 있으면 None.
    """
    if depth == 1:
        try:
            lon, lat = float(coords[0]), float(coords[1])
        except (TypeError, ValueError, IndexError):
            return None
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            return None
        counter[0] += 1
        return [round(lon, 7), round(lat, 7)]
    if not isinstance(coords, list) or not coords:
        return None
    out = []
    for c in coords:
        got = _clean_coords(c, depth - 1, counter)
        if got is None:
            return None
        out.append(got)
    return out


DEPTH = {"LineString": 2, "MultiLineString": 3, "Polygon": 3, "MultiPolygon": 4}


def _shape_from(geom):
    """GeoJSON 기하 하나를 모양으로. 못 읽으면 None, 너무 크면 UploadError."""
    gtype = geom.get("type")
    counter = [0]
    coords = _clean_coords(geom.get("coordinates"), DEPTH[gtype], counter)
    if coords is None or counter[0] < 2:
        return None
    if counter[0] > MAX_VERTICES_PER_SHAPE:
        raise UploadError(msg("모양 하나의 꼭짓점이 {n}개로 너무 많다 (한도 {max}개).",
                              n=counter[0], max=MAX_VERTICES_PER_SHAPE))
    flat = []

    def walk(c):
        if isinstance(c[0], (int, float)):
            flat.append(c)
        else:
            for x in c:
                walk(x)
    walk(coords)
    lons = [c[0] for c in flat]
    lats = [c[1] for c in flat]
    return {"kind": SHAPE_KINDS[gtype],
            "geometry": {"type": gtype, "coordinates": coords},
            "lat": (min(lats) + max(lats)) / 2, "lon": (min(lons) + max(lons)) / 2,
            "vertices": counter[0]}


def _label_of(props):
    for key in LABEL_KEYS:
        for prop_key, value in props.items():
            if prop_key.lower() == key:
                return str(value)
    return ""


def _from_geojson(text: str):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UploadError(msg("GeoJSON 이 깨져 있다: {err}", err=exc)) from exc

    features = data.get("features") if isinstance(data, dict) else None
    if features is None:
        features = [data] if isinstance(data, dict) and data.get("type") == "Feature" else None
    if not features:
        raise UploadError(msg("GeoJSON 에 features 가 없다."))

    points, notes, skipped, vertices = [], [], 0, 0
    for feature in features:
        geom = (feature or {}).get("geometry") or {}
        gtype = geom.get("type")
        props = {k: v for k, v in ((feature or {}).get("properties") or {}).items()
                 if v not in (None, "")}
        label = _label_of(props)
        if gtype == "Point":
            try:
                lon, lat = float(geom["coordinates"][0]), float(geom["coordinates"][1])
            except (KeyError, IndexError, TypeError, ValueError):
                skipped += 1
                continue
            points.append({"lat": lat, "lon": lon, "label": label, "props": props})
        elif gtype == "MultiPoint":
            for c in geom.get("coordinates") or []:
                try:
                    points.append({"lat": float(c[1]), "lon": float(c[0]),
                                   "label": label, "props": props})
                except (IndexError, TypeError, ValueError):
                    skipped += 1
        elif gtype in SHAPE_KINDS:
            shape = _shape_from(geom)
            if shape is None:
                skipped += 1
                continue
            vertices += shape.pop("vertices")
            if vertices > MAX_VERTICES_TOTAL:
                raise UploadError(msg("꼭짓점이 모두 {max}개를 넘는다. 파일을 나눠 올린다.",
                                      max=MAX_VERTICES_TOTAL))
            shape.update(label=label, props=props)
            points.append(shape)
        else:
            skipped += 1

    if not points:
        raise UploadError(msg("점·선·면을 하나도 찾지 못했다."))
    if skipped:
        notes.append(msg("읽지 못한 것 {n}개를 건너뛰었다 (기하가 없거나 깨졌거나 GeometryCollection)",
                         n=skipped))
    return points, notes
