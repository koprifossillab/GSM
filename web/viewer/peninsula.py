"""한반도 지질도 음영판 — 좌표가 박힌 QGIS PDF 한 장을 **우리가 잘라 낸다** (devlog 027).

026 의 "한반도 지질도 (스캔)" 과 같은 지도를 음영기복과 섞어 QGIS 3.44 로 뽑은
것이다(NAS `KimSunho/geomap!!!!.pdf`, 2026-07). 상류가 아니라 **우리 디스크의
파일**이라 문이 아니다 — `requests` 가 없다. `geomap.py`·`janmayen.py` 와 같은 자리다.

PDF 는 Geospatial PDF 다. 쪽 하나에 JPEG 한 장(9975×17310)이 꽉 차 있고, `/Measure`
가 네 모서리의 위경도와 좌표계(EPSG:5179, UTM-K)를 적었다. 네 모서리를 5179 로
옮기면 반듯한 사각형이 된다 — 곧 그림의 격자가 5179 격자다. 그래서 다시 굽지 않고
**5179 그대로 자르고**, 화면(OpenLayers)이 3857 로 옮겨 그린다. 026 의 카카오 격자와
같은 길이다.

    PDF 가 적은 범위(5179)   x 696 747.7 – 1 283 821.5,  y 1 546 278.6 – 2 564 814.9
    고쳐 쓰는 범위           x 697 193.1 – 1 283 478.6,  y 1 545 923.6 – 2 564 459.9
    격자                     원점은 왼쪽 위, 256 px, z7 이 원본 해상도, 한 줌 내릴 때마다 두 배

**PDF 의 좌표를 그대로 믿지 않는다.** 일곱 해안(부산·포항·삼척·태안·목포·인천·원산)에서
OSM 해안선과 대 보니 늘 **355 m 북쪽**에 앉았고, 가로로는 동해안이 +150~200 m ·
서해안이 −80~−310 m 로 0.134% 늘어나 있었다. 같은 자리에서 스캔판(026)은 오차가 ±0~290 m 로
한쪽에 몰리지 않았다. 그래서 가로는 한 줄(오차 = −1380.9 + 0.001343·x)로, 세로는 한 값으로
고쳐 범위를 다시 잡았다. 고친 뒤 남는 어긋남은 가로 ±70 m · 세로 ±120 m 남짓이다 —
재는 눈금(한 화소 80 m)과 1:100만 원도의 선 굵기 안이다 (devlog 027).

2천만 화소가 넘는 한 장을 요청마다 풀 수는 없어서 **미리 잘라 둔다**
(`manage.py build_peninsula`). 서버는 잘라 둔 파일을 내주기만 한다.

**출처를 모른다** — 연구실(KOPRI)이 그린 CorelDRAW 벡터가 원본으로 보이지만 그것이
어느 출판 지도를 따랐는지 모른다 (026 §4). 스캔판처럼 밖에 열지 않는다.
"""
import io
import math
import re
from pathlib import Path

from django.conf import settings

#: 화면이 레이어 곁에 적는 출처
ATTRIBUTION = "KOPRI · QGIS 2026-07"

LAYERS = {"peninsula:shaded"}

#: 잘라 둔 타일의 꼴. WebP 는 투명을 품고 PNG 의 몇 분의 일이다
FORMAT = "webp"

# ── 격자 (EPSG:5179) — 화면(`map.js` 의 peninsulaSource)은 카탈로그 행으로 받는다 ──

#: PDF 의 `/Measure` 가 적은 범위 — 판을 알아보는 데만 쓴다(`check_corners`)
PDF_X0, PDF_X1 = 696747.7005, 1283821.5458
PDF_Y0, PDF_Y1 = 1546278.5933, 2564814.9308
#: 해안선에 대 고친 범위 — 격자는 이것으로 짓는다. 고치면 타일을 다시 자른다
X0, X1 = 697193.0552, 1283478.5767
Y0, Y1 = 1545923.5933, 2564459.9308
WIDTH, HEIGHT = 9975, 17310          # 원본 그림의 화소
TILE = 256
MAX_ZOOM = 7                         # 원본 해상도. 2^7 × 256 > 17310 이라 z0 은 한 장이다
#: 격자의 해상도는 가로 화소를 따른다. 세로는 자를 때 원본의 세로 화소로 따로 잰다
RES = (X1 - X0) / WIDTH
#: PDF 가 적은 모서리가 이 범위에서 이만큼(m) 넘게 어긋나면 다른 지도로 보고 멈춘다
TOLERANCE = 1.0

_SOURCE_GLOB = "*.pdf"


def resolution(z: int) -> float:
    return RES * 2 ** (MAX_ZOOM - z)


def grid_size(z: int) -> tuple:
    """줌 z 의 (가로, 세로) 장 수."""
    span = TILE * resolution(z)
    return math.ceil((X1 - X0) / span), math.ceil((Y1 - Y0) / span)


def valid_tile(z: int, x: int, y: int) -> bool:
    if not 0 <= z <= MAX_ZOOM:
        return False
    cols, rows = grid_size(z)
    return 0 <= x < cols and 0 <= y < rows


def tile_bbox(z: int, x: int, y: int) -> tuple:
    """(서, 남, 동, 북) — 5179 미터."""
    span = TILE * resolution(z)
    west, north = X0 + x * span, Y1 - y * span
    return west, north - span, west + span, north


def grid() -> dict:
    """화면에 알릴 격자. 원점은 범위의 왼쪽 위다."""
    return {"extent": [X0, Y0, X1, Y1],
            "resolutions": [resolution(z) for z in range(MAX_ZOOM + 1)]}


# ── 자리 ──────────────────────────────────────────────────────────────

def root() -> Path:
    return Path(settings.PENINSULA_DIR)


def tiles_dir() -> Path:
    return root() / "tiles"


def available() -> bool:
    return tiles_dir().is_dir()


def tile_path(z: int, x: int, y: int) -> Path:
    return tiles_dir() / str(z) / str(x) / f"{y}.{FORMAT}"


def source_file():
    """잘라 낼 PDF. 여럿이면 이름이 가장 뒤인 것. 없으면 None."""
    found = sorted(root().glob(_SOURCE_GLOB)) if root().is_dir() else []
    return found[-1] if found else None


def read_tile(z: int, x: int, y: int):
    """잘라 둔 타일(바이트). 그 자리가 비어 있으면(바다) None."""
    try:
        return tile_path(z, x, y).read_bytes()
    except FileNotFoundError:
        return None


# ── PDF 읽기 — 공간 라이브러리 없이 (geomap.py 머리글과 같은 까닭) ──────────

def read_pdf(data: bytes) -> tuple:
    """Geospatial PDF 에서 (JPEG 바이트, 좌표계 번호, 모서리 위경도 넷) 을 꺼낸다.

    QGIS 가 쓴 꼴만 안다 — 쪽 하나에 `/DCTDecode` 그림 하나, `/Measure` 하나.
    다른 꼴이면 `PeninsulaError`.
    """
    m = re.search(rb"/Subtype\s*/Image(.{0,400}?)>>\s*stream\r?\n", data, re.S)
    if not m or b"/DCTDecode" not in m.group(1):
        raise PeninsulaError("PDF 에 JPEG 그림이 없다")
    start = m.end()
    length = re.search(rb"/Length\s+(\d+)(\s+0\s+R)?", m.group(1))
    if length and length.group(2):
        ref = re.search(rb"\b" + length.group(1) + rb"\s+0\s+obj\s*(\d+)", data)
        size = int(ref.group(1)) if ref else None
    else:
        size = int(length.group(1)) if length else None
    end = start + size if size else data.find(b"endstream", start)
    jpeg = data[start:end]
    if not jpeg.startswith(b"\xff\xd8"):
        raise PeninsulaError("PDF 의 그림이 JPEG 가 아니다")

    epsg = re.search(rb"/EPSG\s+(\d+)", data)
    gpts = re.search(rb"/GPTS\s*\[([^\]]+)\]", data)
    if not epsg or not gpts:
        raise PeninsulaError("PDF 에 좌표(/Measure)가 없다")
    nums = [float(v) for v in gpts.group(1).split()]
    if len(nums) != 8:
        raise PeninsulaError("PDF 의 모서리가 넷이 아니다")
    corners = [(nums[i], nums[i + 1]) for i in range(0, 8, 2)]      # (위도, 경도)
    return jpeg, int(epsg.group(1)), corners


def check_corners(epsg: int, corners) -> None:
    """모서리가 이 모듈의 범위와 맞는지 본다. 격자는 화면과 약속한 것이라 바꾸지 않는다."""
    from . import crs
    if epsg != 5179:
        raise PeninsulaError(f"좌표계가 5179 가 아니다 ({epsg})")
    # 모서리 하나하나가 범위의 네 귀 가운데 하나에 붙어야 한다 — 두른 사각형만 보면
    # 한 귀가 안쪽으로 비틀린 것을 놓친다
    want = [(PDF_X0, PDF_Y0), (PDF_X0, PDF_Y1), (PDF_X1, PDF_Y0), (PDF_X1, PDF_Y1)]
    worst = 0.0
    for lat, lon in corners:
        x, y = crs.from_latlon("5179", lat, lon)
        worst = max(worst, min(max(abs(x - wx), abs(y - wy)) for wx, wy in want))
    if worst > TOLERANCE:
        raise PeninsulaError(f"PDF 의 범위가 격자와 {worst:.1f} m 어긋난다 — 다른 판이다")


# ── 자르기 ────────────────────────────────────────────────────────────

#: 이보다 밝고 무채색이면 빈 자리(PDF 의 흰 바탕)로 보고 투명하게 한다
WHITE = 248
GREY = 6


def transparent_white(image):
    """흰 바탕을 투명하게 한 RGBA. JPEG 라 바탕이 255 에서 조금씩 흔들린다."""
    from PIL import Image, ImageChops
    rgb = image.convert("RGB")
    r, g, b = rgb.split()
    low = ImageChops.darker(ImageChops.darker(r, g), b)
    high = ImageChops.lighter(ImageChops.lighter(r, g), b)
    bright = low.point(lambda v: 255 if v >= WHITE else 0)
    flat = ImageChops.subtract(high, low).point(lambda v: 255 if v <= GREY else 0)
    alpha = ImageChops.invert(ImageChops.multiply(bright, flat))
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    return out


def cut(level_image, factor: int, z: int, x: int, y: int):
    """줌 z 의 타일 한 장(RGBA). `level_image` 는 원본을 `factor` 배 줄인 것이다.
    그림 밖은 투명하다. 다 투명하면 None."""
    from PIL import Image
    west, south, east, north = tile_bbox(z, x, y)
    sx = RES * factor                              # 줄인 그림의 가로 한 화소(m)
    sy = (Y1 - Y0) / HEIGHT * factor
    w, h = level_image.size
    left, top = (west - X0) / sx, (Y1 - north) / sy
    right, bottom = (east - X0) / sx, (Y1 - south) / sy
    # 그림 밖을 잘라 내고, 남은 조각이 타일의 어디에 앉는지 잰다
    cl, ct, cr, cb = max(left, 0), max(top, 0), min(right, w), min(bottom, h)
    if cr <= cl or cb <= ct:
        return None
    px = TILE / (right - left)
    py = TILE / (bottom - top)
    ox, oy = round((cl - left) * px), round((ct - top) * py)
    ow, oh = round((cr - left) * px) - ox, round((cb - top) * py) - oy
    if ow < 1 or oh < 1:
        return None
    piece = level_image.resize((ow, oh), Image.LANCZOS, box=(cl, ct, cr, cb))
    tile = Image.new("RGBa", (TILE, TILE), (0, 0, 0, 0))
    tile.paste(piece, (ox, oy))
    tile = tile.convert("RGBA")
    if tile.getchannel("A").getbbox() is None:
        return None
    return tile


def encode(tile) -> bytes:
    buf = io.BytesIO()
    tile.save(buf, format="WEBP", quality=82, method=4)
    return buf.getvalue()


class PeninsulaError(RuntimeError):
    pass
