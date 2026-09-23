"""올린 파일을 점묶음으로 읽는다. CSV 와 GeoJSON 둘뿐이다.

**열 이름을 사람이 고르게 하지 않는다.** 위경도 열은 이름으로 알아낸다 —
현장에서 쓰는 표는 열 이름이 제각각이라(`lat`·`위도`·`Y`) 고르라고 물으면
올릴 때마다 묻게 된다. 못 알아내면 그때만 까닭을 적어 돌려준다.
"""
import csv
import io
import json

from . import coords

#: 위도로 읽는 열 이름. 소문자로 견준다.
LAT_KEYS = ("lat", "latitude", "위도", "y", "lat_dd", "dd_lat", "북위")
LON_KEYS = ("lon", "lng", "long", "longitude", "경도", "x", "lon_dd", "dd_lon", "동경")
#: 이름표로 쓸 열. 없으면 이름표 없이 둔다.
LABEL_KEYS = ("label", "name", "이름", "이름표", "지점", "지점명", "site", "station", "id")


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
    raise UploadError("글자를 읽지 못했다. UTF-8 이나 CP949 로 저장해 다시 올린다.")


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
        raise UploadError("첫 줄에 열 이름이 없다.")

    lat_col = _pick(reader.fieldnames, LAT_KEYS)
    lon_col = _pick(reader.fieldnames, LON_KEYS)
    if not lat_col or not lon_col:
        raise UploadError(
            "위경도 열을 찾지 못했다. 열 이름을 "
            f"{'·'.join(LAT_KEYS[:4])} / {'·'.join(LON_KEYS[:4])} 가운데 하나로 두고 "
            f"다시 올린다. (읽은 열: {', '.join(reader.fieldnames)})")
    label_col = _pick(reader.fieldnames, LABEL_KEYS)

    points, notes, skipped = [], [], 0
    for lineno, row in enumerate(reader, start=2):
        pair = _read_pair(row.get(lat_col), row.get(lon_col))
        if pair is None:
            skipped += 1
            if len(notes) < 5:
                notes.append(f"{lineno}째 줄 — 좌표를 읽지 못해 건너뛰었다")
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
        raise UploadError("좌표를 하나도 읽지 못했다.")
    if skipped > len(notes):
        notes.append(f"…모두 {skipped}줄을 건너뛰었다")
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


def _from_geojson(text: str):
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise UploadError(f"GeoJSON 이 깨져 있다: {exc}") from exc

    features = data.get("features") if isinstance(data, dict) else None
    if features is None:
        features = [data] if isinstance(data, dict) and data.get("type") == "Feature" else None
    if not features:
        raise UploadError("GeoJSON 에 features 가 없다.")

    points, notes, skipped = [], [], 0
    for feature in features:
        geom = (feature or {}).get("geometry") or {}
        if geom.get("type") != "Point":
            skipped += 1
            continue
        try:
            lon, lat = float(geom["coordinates"][0]), float(geom["coordinates"][1])
        except (KeyError, IndexError, TypeError, ValueError):
            skipped += 1
            continue
        props = {k: v for k, v in (feature.get("properties") or {}).items()
                 if v not in (None, "")}
        label = ""
        for key in LABEL_KEYS:
            for prop_key, value in props.items():
                if prop_key.lower() == key:
                    label = str(value)
                    break
            if label:
                break
        points.append({"lat": lat, "lon": lon, "label": label, "props": props})

    if not points:
        raise UploadError("Point 를 하나도 찾지 못했다. 선·면은 아직 받지 않는다.")
    if skipped:
        notes.append(f"Point 가 아닌 것 {skipped}개를 건너뛰었다 — 선·면은 아직 받지 않는다")
    return points, notes
