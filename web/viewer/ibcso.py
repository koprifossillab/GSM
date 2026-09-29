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

    # 3D 가 쓰는 것 — 원본의 9354 격자 그대로 자른 판(051, 아래 "수치 격자" 머리글)
    def wide_dir(self) -> Path:
        return root() / self.folder.replace("tiles-", "wide-")

    def wide_available(self) -> bool:
        return self.wide_dir().is_dir()

    def read_wide(self, level: int, x: int, y: int):
        try:
            return (self.wide_dir() / str(level) / str(x) / f"{y}.{FORMAT}").read_bytes()
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


# ── 수치 격자 — 3D 의 지형 (051) ──────────────────────────────────────
#
# 3D 는 표고를 Terrarium 타일로 받는다. 칠한 판은 색이라 표고로 되돌릴 수 없어, PANGAEA 의 **수치
# 격자**(`IBCSO_v2_bed.tif`·`IBCSO_v2_ice-surface.tif`, int16 미터, 빈 곳 −32768)를 따로 자른다.
#
# 이것은 3031 이 아니라 **원본의 9354 격자 그대로** 자른다. 2D 의 3031 격자(GeoMAP)는 ±3 333 km 라
# 남위 60° 언저리에서 끊기는데, 3D 는 남위 50° 까지를 한 번에 본다. 3D 는 어차피 서버가 3857 로
# 다시 펴므로(`warp.py`) 2D 의 격자를 따를 까닭이 없다. 단계 6 이 원본 그대로(500 m, 75×75 장)이고
# 한 단계 내려갈 때마다 두 배씩 거칠다. 줄일 때 빈 곳은 평균에서 뺀다.
#
# **3D 의 배경(칠한 판)도 같은 격자로 한 벌 더 자른다**(`wide-bed/`·`wide-ice/`, WebP). 2D 의 것을 펴면
# 남위 60° 언저리의 네모에서 배경이 끊기고 그 밖은 지형만 남는다.
#
# 타일은 16 비트 흑백 PNG 다 — 값은 `미터 + 32768`, **0 이 빈 곳**이다. 한 장에 30 KB 남짓이고
# 두 판을 합쳐 400 MB 쯤이다. Terrarium 으로 구워 두지 않은 것은 3857 로 펼 때 값을 섞어야 하기
# 때문이다 — 섞는 것은 미터여야 한다(Terrarium 의 세 띠를 따로 섞으면 값이 튄다).

DEM_FORMAT = "png"
DEM_MAX_LEVEL = 6
DEM_OFFSET = 32768
DEM_NODATA = -32768


def dem_res(level: int) -> float:
    """단계 `level` 의 한 화소 (9354 미터)."""
    return SOURCE_RES * 2 ** (DEM_MAX_LEVEL - level)


def dem_tiles(level: int) -> int:
    """단계 `level` 의 한 변 타일 수."""
    return math.ceil(SOURCE_SIZE / 2 ** (DEM_MAX_LEVEL - level) / TILE)


def dem_valid(level: int, x: int, y: int) -> bool:
    return 0 <= level <= DEM_MAX_LEVEL and 0 <= x < dem_tiles(level) and 0 <= y < dem_tiles(level)


def to_9354(lat: float, lon: float) -> tuple:
    """위경도 → EPSG:9354. 3031 을 배율로 나눈다(머리글)."""
    x, y = geomap.lonlat_to_3031(lon, lat)
    return x / SCALE, y / SCALE


@dataclass(frozen=True)
class DemSheet:
    kind: str           # bed | ice
    source: str
    folder: str

    def tiles_dir(self) -> Path:
        return root() / self.folder

    def available(self) -> bool:
        return self.tiles_dir().is_dir()

    def source_file(self):
        path = root() / self.source
        return path if path.is_file() else None

    def tile_path(self, level: int, x: int, y: int) -> Path:
        return self.tiles_dir() / str(level) / str(x) / f"{y}.{DEM_FORMAT}"

    def read_tile(self, level: int, x: int, y: int):
        try:
            return self.tile_path(level, x, y).read_bytes()
        except FileNotFoundError:
            return None


DEM_BED = DemSheet(kind="bed", source="IBCSO_v2_bed.tif", folder="dem-bed")
DEM_ICE = DemSheet(kind="ice", source="IBCSO_v2_ice-surface.tif", folder="dem-ice")
DEMS = {s.kind: s for s in (DEM_BED, DEM_ICE)}


def open_dem(path):
    """수치 원본 → (값 F, 채움 F). 빈 곳은 값 0·채움 0 이다 — 줄일 때 평균에서 빼려고 나눠 둔다."""
    from PIL import Image, ImageMath
    image = Image.open(path)
    if image.size != (SOURCE_SIZE, SOURCE_SIZE):
        raise IbcsoError(f"격자가 {image.size} 다 — {SOURCE_SIZE}×{SOURCE_SIZE} 를 기다렸다")
    image.load()
    if image.mode not in ("I", "I;16S"):
        raise IbcsoError(f"뜻밖의 격자다 ({image.mode}) — int16 을 기다렸다")
    image = image.convert("I")
    fill = ImageMath.lambda_eval(lambda a: a["float"](a["notequal"](a["v"], DEM_NODATA)), v=image)
    value = ImageMath.lambda_eval(lambda a: a["float"](a["v"]) * a["f"], v=image, f=fill)
    return value, fill


def halve(value, fill):
    """한 단계 거칠게 — 2×2 를 평균하되 빈 곳은 빼고 센다. (값, 채움)을 낸다."""
    from PIL import ImageMath
    v, f = value.reduce(2), fill.reduce(2)             # 둘 다 넷의 평균
    out = ImageMath.lambda_eval(lambda a: a["v"] / a["max"](a["f"], 1e-6) * a["float"](a["f"] > 0),
                                v=v, f=f)
    return out, ImageMath.lambda_eval(lambda a: a["float"](a["f"] > 0), f=f)


def cut_dem(value, fill, x: int, y: int):
    """한 단계의 (값, 채움) 에서 타일 한 장 — 16 비트 흑백(`I;16`). 다 비었으면 None."""
    from PIL import Image, ImageMath
    box = (x * TILE, y * TILE, (x + 1) * TILE, (y + 1) * TILE)   # 밖은 0(빈 곳)으로 채워진다
    f = fill.crop(box)
    if f.getextrema()[1] <= 0:
        return None
    v = value.crop(box)
    # 0 은 빈 곳이다. 값은 −8 400 m ~ +4 800 m 라 부호 없는 16 비트 안에 들고 0 이 되지 않는다
    code = ImageMath.lambda_eval(
        lambda a: a["int"]((a["v"] + (DEM_OFFSET + 0.5)) * a["float"](a["f"] > 0)), v=v, f=f)
    return code.convert("I;16")


def encode_dem(tile) -> bytes:
    buf = io.BytesIO()
    tile.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def decode_dem(data: bytes):
    """16 비트 PNG → (값 F 미터, 채움 F 0·1)."""
    from PIL import Image, ImageMath
    raw = Image.open(io.BytesIO(data))
    raw = raw.convert("I") if raw.mode != "I" else raw
    fill = ImageMath.lambda_eval(lambda a: a["float"](a["c"] > 0), c=raw)
    value = ImageMath.lambda_eval(lambda a: (a["float"](a["c"]) - DEM_OFFSET) * a["f"], c=raw, f=fill)
    return value, fill


def cut_wide(level_image, x: int, y: int):
    """9354 격자 한 단계(RGBa, 미리 곱한 것)에서 3D 배경 타일 한 장(RGBA). 다 투명하면 None."""
    from PIL import Image
    box = (x * TILE, y * TILE, (x + 1) * TILE, (y + 1) * TILE)
    piece = level_image.crop(box)                   # 밖은 투명으로 채워진다
    tile = Image.new("RGBa", (TILE, TILE), (0, 0, 0, 0))
    tile.paste(piece, (0, 0))
    tile = tile.convert("RGBA")
    if tile.getchannel("A").getbbox() is None:
        return None
    return tile
