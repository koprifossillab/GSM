"""브라우저가 부르는 타일을 서버에서 똑같이 셈한다 — 미리 데우기가 쓴다.

**한 글자라도 다르면 캐시가 맞지 않는다.** 캐시 열쇠는 WMS 변수의 문자열
(`tilecache.key_for`)이라, 브라우저가 `BBOX=0,…` 을 보내는데 우리가
`BBOX=0.0,…` 으로 받아 두면 헛일이다. 그래서 OpenLayers 가 하는 셈을 그
차례 그대로 옮겼다.

- 격자: `ol.tilegrid.createXYZ({tileSize: 512})` (`map.js` 의 `wmsSource`)
- 해상도: `최대해상도 / 2^z`, 최대해상도 = 세계 폭 / 512
- 타일 범위: `minX = 원점X + x·512·해상도`, `minY = 원점Y − (y+1)·512·해상도`
  (OpenLayers 의 `getTileCoordExtent`, 곱하는 차례까지 같게)
- 숫자 적기: 자바스크립트 `Number` 의 문자열과 같게 — 정수면 `.0` 을 뗀다

2026-09-27 에 브라우저가 실제로 부른 타일 주소와 한 글자까지 대조했다
(`test_tilegrid`).
"""
import math

HALF = 20037508.342789244            # EPSG:3857 의 반 폭
WORLD = HALF * 2
TILE = 512
MAX_RES = WORLD / TILE


def resolution(z: int) -> float:
    return MAX_RES / math.pow(2, z)


def tile_extent(z: int, x: int, y: int) -> tuple:
    res = resolution(z)
    min_x = -HALF + x * TILE * res
    min_y = HALF - (y + 1) * TILE * res
    return (min_x, min_y, min_x + TILE * res, min_y + TILE * res)


def js_number(value: float) -> str:
    """자바스크립트가 숫자를 문자열로 적는 꼴. 이 범위의 값에서는 파이썬의
    `repr` 과 같되, 정수는 `.0` 을 붙이지 않는다."""
    if value == 0:
        return "0"
    if float(value).is_integer() and abs(value) < 1e21:
        return str(int(value))
    return repr(float(value))


def lonlat_to_3857(lon: float, lat: float) -> tuple:
    x = lon * HALF / 180
    lat = max(min(lat, 85.0511287798), -85.0511287798)
    y = math.log(math.tan((90 + lat) * math.pi / 360)) * HALF / math.pi
    return x, y


def tiles_for(bbox_lonlat, z: int):
    """위경도 범위 `(서, 남, 동, 북)` 를 덮는 줌 `z` 의 타일 `(z, x, y)` 들."""
    west, south, east, north = bbox_lonlat
    min_x, min_y = lonlat_to_3857(west, south)
    max_x, max_y = lonlat_to_3857(east, north)
    span = TILE * resolution(z)
    last = 2 ** z - 1
    x0 = max(0, int((min_x + HALF) // span))
    x1 = min(last, int((max_x + HALF) // span))
    y0 = max(0, int((HALF - max_y) // span))
    y1 = min(last, int((HALF - min_y) // span))
    for x in range(x0, x1 + 1):
        for y in range(y0, y1 + 1):
            yield z, x, y


def wms_params(layer: str, z: int, x: int, y: int) -> dict:
    """브라우저의 `TileWMS` 가 보내는 것과 같은 변수 (이름은 소문자로)."""
    return {
        "service": "WMS", "version": "1.3.0", "request": "GetMap",
        "format": "image/png", "transparent": "true", "layers": layer,
        "tiled": "true", "styles": "",
        "width": str(TILE), "height": str(TILE), "crs": "EPSG:3857",
        "bbox": ",".join(js_number(v) for v in tile_extent(z, x, y)),
    }
