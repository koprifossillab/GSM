"""남극 해저·빙저 지형 — IBCSO v2 의 칠한 판을 **우리가 잘라 낸다** (devlog 047).

IBCSO v2(International Bathymetric Chart of the Southern Ocean, Dorschel et al. 2022,
doi:10.1594/PANGAEA.937574, CC BY 4.0)는 남위 50° 남쪽을 500 m 격자로 담은 해저지형도다.
PANGAEA 가 수치 격자와 함께 **미리 칠한 RGB GeoTIFF** 를 준다 — 그것을 배경으로 쓴다.
상류가 아니라 **우리 디스크의 파일**이라 문이 아니다 — `requests` 가 없다. `peninsula.py`
와 같은 자리다.

    판        원본                          레이어        그리는 것
    해저면    IBCSO_v2_bed_RGB.tif          ibcso:bed     얼음 밑 기반암까지 (빙붕·빙상을 걷어 낸 것)
    얼음 위   IBCSO_v2_ice-surface_RGB.tif  ibcso:ice     빙붕·빙상의 윗면

원본은 19200×19200 화소, 한 화소 500 m, 범위 ±4 800 000 m 이고 투영은 EPSG:9354
(WGS84 남극 평사도법, **표준위도 −65°**)다. 화면의 3031 은 표준위도만 −71° 로 다르다.
평사도법에서 표준위도는 축척만 바꾸므로 **두 좌표는 곱셈 하나로 오간다** —
`x₃₀₃₁ = SCALE · x₉₃₅₄`(y 도 같다). 다시 투영할 것 없이 늘여 자르면 된다.

격자는 GeoMAP 의 3031 격자(`geomap.py` 머리글) 그대로다 — 남극 화면의 줌이 곧 타일의
줌이다. 원본 한 화소는 3031 에서 510 m 라 줌 6(407 m)까지 자른다. 그 위는 화면이 늘린다.

바깥(남위 50° 북쪽)은 원본이 255 로 칠해 두었다(`GDAL_NODATA`). 빨강의 최댓값이 254 라
세 띠가 모두 255 인 곳만 비어 있다 — 투명하게 한다.
"""
import io
import math
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from . import geomap

FORMAT = "webp"
TILE = geomap.TILE
MAX_ZOOM = 6

#: 원본(EPSG:9354)의 격자
SOURCE_SIZE = 19200
SOURCE_RES = 500.0
SOURCE_HALF = 4800000.0

#: 화면이 레이어 곁에 적는 출처. CC BY 라 반드시 보여야 한다
ATTRIBUTION = ("IBCSO v2 (Dorschel et al., 2022, "
               '<a href="https://doi.org/10.1594/PANGAEA.937574" target="_blank" rel="noopener">'
               "doi:10.1594/PANGAEA.937574</a>, CC BY 4.0)")


def _scale() -> float:
    """3031 과 9354 의 축척 비 — 같은 점의 극에서 떨어진 거리를 견준다."""
    e = geomap._E

    def k(lat_ts_deg):
        p = math.radians(lat_ts_deg)
        m = math.cos(p) / math.sqrt(1 - (e * math.sin(p)) ** 2)
        t = math.tan(math.pi / 4 - p / 2) / ((1 - e * math.sin(p)) / (1 + e * math.sin(p))) ** (e / 2)
        return m / t

    return k(71.0) / k(65.0)


#: x₃₀₃₁ / x₉₃₅₄ — 1.0205 남짓
SCALE = _scale()


@dataclass(frozen=True)
class Sheet:
    name: str           # 레이어 이름
    source: str         # 원본 파일 이름 (`GSM_IBCSO_DIR` 안)
    folder: str         # 잘라 둔 것이 드는 폴더

    def tiles_dir(self) -> Path:
        return root() / self.folder

    def available(self) -> bool:
        return self.tiles_dir().is_dir()

    def source_file(self):
        path = root() / self.source
        return path if path.is_file() else None

    def tile_path(self, z: int, x: int, y: int) -> Path:
        return self.tiles_dir() / str(z) / str(x) / f"{y}.{FORMAT}"

    def read_tile(self, z: int, x: int, y: int):
        """잘라 둔 타일(바이트). 그 자리가 비어 있으면(자료 밖) None."""
        try:
            return self.tile_path(z, x, y).read_bytes()
        except FileNotFoundError:
            return None


BED = Sheet(name="ibcso:bed", source="IBCSO_v2_bed_RGB.tif", folder="tiles-bed")
ICE = Sheet(name="ibcso:ice", source="IBCSO_v2_ice-surface_RGB.tif", folder="tiles-ice")
SHEETS = {s.name: s for s in (BED, ICE)}


def root() -> Path:
    return Path(settings.IBCSO_DIR)


def valid_tile(z: int, x: int, y: int) -> bool:
    return 0 <= z <= MAX_ZOOM and 0 <= x < 2 ** z and 0 <= y < 2 ** z


def source_box(z: int, x: int, y: int) -> tuple:
    """3031 타일 (z, x, y) 가 원본에서 차지하는 화소 네모 (왼, 위, 오른, 아래). 원본 밖으로 나갈 수 있다."""
    west, south, east, north = geomap.tile_bbox(z, x, y)

    def col(v):
        return (v / SCALE + SOURCE_HALF) / SOURCE_RES

    def row(v):
        return (SOURCE_HALF - v / SCALE) / SOURCE_RES

    return col(west), row(north), col(east), row(south)


# ── 자르기 ────────────────────────────────────────────────────────────

def open_source(path):
    """원본을 열어 크기를 확인하고, 비어 있는 곳(255,255,255)을 투명하게 한 RGBa(미리 곱한 것)를 낸다."""
    from PIL import Image, ImageChops
    image = Image.open(path)
    if image.size != (SOURCE_SIZE, SOURCE_SIZE):
        raise IbcsoError(f"그림이 {image.size} 다 — {SOURCE_SIZE}×{SOURCE_SIZE} 를 기다렸다")
    rgb = image.convert("RGB")
    del image
    r, g, b = rgb.split()
    full = ImageChops.multiply(ImageChops.multiply(r.point(lambda v: 255 if v == 255 else 0),
                                                   g.point(lambda v: 255 if v == 255 else 0)),
                               b.point(lambda v: 255 if v == 255 else 0))
    alpha = ImageChops.invert(full)
    del r, g, b, full
    out = rgb.convert("RGBA")
    del rgb
    out.putalpha(alpha)
    # 줄일 때 투명한 가장자리가 희게 번지지 않게 미리 곱해 둔다 (peninsula 와 같다)
    return out.convert("RGBa")


def cut(level_image, factor: int, z: int, x: int, y: int):
    """줌 z 의 타일 한 장(RGBA). `level_image` 는 원본을 `factor` 배 줄인 것이다.
    원본 밖·자료 밖은 투명하다. 다 투명하면 None."""
    from PIL import Image
    left, top, right, bottom = (v / factor for v in source_box(z, x, y))
    w, h = level_image.size
    cl, ct, cr, cb = max(left, 0), max(top, 0), min(right, w), min(bottom, h)
    if cr <= cl or cb <= ct:
        return None
    px, py = TILE / (right - left), TILE / (bottom - top)
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


class IbcsoError(RuntimeError):
    pass
