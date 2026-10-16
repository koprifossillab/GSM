"""중국 지질도 1:400만 (2002) — 좌표 없는 스캔 한 장에 **우리가 좌표를 붙인다** (wetherilli P14·386).

《中国地质图》(第二版) 1:4 000 000. 程裕淇 主编, 中国地质科学院地质研究所 编制, 地质出版社 2002 년 12 월.
자료 기준은 지리 2002 년 말, 지질 2002 년 6 월이다. 원본은 300 dpi JPEG 한 장(14 521 × 10 261)이고 좌표가
없다. 상류가 아니라 **우리 디스크의 파일**이라 문이 아니다 — `requests` 가 없다. `peninsula.py` 와 같은 자리다.

**출판 지도라 이용 조건이 적혀 있지 않다** — 연구실 내부용(`views.LAB_ONLY`)이다. 원본·마스크·잘라 둔 타일
모두 저장소·이미지에 두지 않는다. 원본은 NAS `N:\\GSM\\sources\\china4m\\`.

좌표 — 도곽의 경위선으로 맞췄다
-------------------------------

도곽에 경위선 눈금(위 68°–148°, 아래 100°–124°, 좌우 28°–48°, 4° 간격)이 있고 지도 안에 같은 간격의 경위선이
하늘색 가는 선으로 그려져 있다. 그 선을 따라 짚은 점 24 000 개에 **람베르트 정각원추(표준위선 25°N·47°N)** 와
아핀 하나를 맞췄다. 남는 어긋남은 중앙값 0.06 px, 90 % 가 1.1 px(450 m) 안이다. 알베르스 등적원추로는
2 배 넘게 어긋나 버렸다.

- 표준위선을 풀어 두면 17.5°·53.6° 로 가지만 축척과 맞바꿔질 뿐 맞춤은 같다 — 중국 지도에 흔한 25°·47° 로 둔다
- 중앙경선은 스캔의 기울기와 수학적으로 겹친다(원추를 돌리는 것이 곧 그림을 돌리는 것). 105°E 로 두고
  아핀의 회전이 나머지를 맡는다. 도곽이 반듯한 것으로 보아 원도의 중앙경선은 106°E 쯤이다
- 가로·세로 축척이 같다(투영 평면에서 한 화소 423.3 m, 북위 35° 의 땅 위로 431 m) — 스캔이 찌그러지지 않았다.
  1:400만을 300 dpi 로 읽었다면 339 m 여야 한다 — 원도를 80 % 남짓으로 줄인 판을 스캔한 것이다
- 타원체는 WGS84 로 둔다. 원도가 쓴 크라소프스키와의 차이는 아핀이 흡수하고 남는 것은 화소 아래다

**경위선은 맞지만 그려진 땅은 2–10 km 어긋난다.** 도시 기호 열여섯·해안 곶 열여섯을 대 보니 종이 위 0.5–2.5 mm
— 1:400만 원도가 땅을 일반화해 그린 정도다. 방향이 제각각이라 고무판처럼 펴지 않는다.
"""
import io
import math
from pathlib import Path

from django.conf import settings

from . import crs

#: 원도의 투영 — 람베르트 정각원추. 원점 위도 0, 가산 없음, 미터
LAT1, LAT2, LON0 = 25.0, 47.0, 105.0
#: (동, 북)(m) → 원본 화소 (x, y).  x = a·동 + b·북 + c,  y = d·동 + e·북 + f
AFFINE = (0.002362134226172537, 2.43675081303265e-05, 6849.397556505154,
          2.448531433403248e-05, -0.002362136438657049, 15018.075813036525)

#: 원본 그림의 크기. 다르면 다른 스캔이다
SIZE = (14521, 10261)
#: 도곽 안쪽 선 (x0, y0, x1, y1) — 이 밖은 여백·눈금 글자다
NEATLINE = (166, 166, 14352, 9878)
#: 도곽 안이지만 지도가 아닌 것 (x0, y0, x1, y1) — 범례 둘, 남해제도 삽입도(축척이 다르다), 연대표, 제목
NOT_MAP = (
    (0, 6440, 2180, 10261),         # 图例 왼쪽 칸 (지층)
    (2160, 7380, 4990, 10261),      # 图例 오른쪽 칸 (화성암·무늬·부호)
    (12420, 7040, 14521, 10261),    # 南海诸岛 삽입도
    (13040, 4930, 14521, 7110),     # 지질시대 연대표
    (3900, 350, 9100, 1300),        # 제목 "中国地质图"
)

SOURCE = "GeoChina400*.jpg"
MASK = "GeoChina400_mask.png"


def root() -> Path:
    return Path(settings.CHINA4M_DIR)


def source_file():
    """원본 스캔. 여럿이면 이름이 가장 뒤인 것. 없으면 None."""
    found = sorted(root().glob(SOURCE)) if root().is_dir() else []
    return found[-1] if found else None


def mask_file() -> Path:
    return root() / MASK


# ── 좌표 ──────────────────────────────────────────────────────────────

def to_pixel(lon: float, lat: float) -> tuple:
    """위경도 → 원본 화소 (x, y). 화소의 왼쪽 위가 0 이다."""
    east, north = crs.latlon_to_lcc(lat, lon, LON0, LAT1, LAT2)
    a, b, c, d, e, f = AFFINE
    return a * east + b * north + c, d * east + e * north + f


def to_lonlat(x: float, y: float) -> tuple:
    """원본 화소 (x, y) → 위경도 (경도, 위도)."""
    a, b, c, d, e, f = AFFINE
    det = a * e - b * d
    dx, dy = x - c, y - f
    east, north = (e * dx - b * dy) / det, (a * dy - d * dx) / det
    lat, lon = crs.lcc_to_latlon(east, north, LON0, LAT1, LAT2)
    return lon, lat


def on_map(x: float, y: float) -> bool:
    """도곽 안이고 범례·삽입도·제목 자리가 아닌가."""
    x0, y0, x1, y1 = NEATLINE
    if not (x0 <= x < x1 and y0 <= y < y1):
        return False
    return not any(bx0 <= x < bx1 and by0 <= y < by1 for bx0, by0, bx1, by1 in NOT_MAP)


# ── 3857 타일 (wetherilli 387) ───────────────────────────────────────
#
# 원도의 람베르트 격자를 화면에 알리지 않고 **3857 z/x/y 로 다시 굽는다** — 중국 탭(3857)과 3D 가 그대로 쓴다.
# 굽는 데는 Pillow 의 `MESH` 변환만 쓴다. 타일을 8×8 칸으로 나눠 칸의 네 귀만 원본 화소로 옮기고
# 칸 안은 네 귀를 잇는 사변형으로 편다. 한 칸이 32 px 이라 원추의 휨이 칸 안에서 0.01 px 도 안 된다.

NAME = "china4m:geology"
FORMAT = "webp"
TILE = 256
HALF = 20037508.342789244
#: 마지막 줌 — 북위 35° 에서 한 화소 250 m 라 원본(431 m)을 조금 늘린다. 그 위는 화면이 늘린다
MAX_ZOOM = 9
#: 첫 줌 — 온 중국이 네 장
MIN_ZOOM = 3
#: 마스크가 덮는 범위(서, 남, 동, 북)에 반 화소 남짓 — 2026-10-16 의 마스크로 쟀다
BBOX = (72.5, 17.9, 136.5, 54.3)
#: 칸 수 — 한 변을 이만큼 나눠 네 귀만 옮긴다
MESH = 8
#: 화면이 레이어 곁에 적는 출처
ATTRIBUTION = "中国地质科学院地质研究所 · 地质出版社 2002"


def tiles_dir() -> Path:
    return root() / "tiles"


def available() -> bool:
    return tiles_dir().is_dir()


def tile_range(z: int) -> tuple:
    """줌 z 에서 `BBOX` 를 덮는 (x0, y0, x1, y1) — 끝을 넣는다."""
    west, south, east, north = BBOX
    n = 2 ** z

    def col(lon):
        return int((lon + 180.0) / 360.0 * n)

    def row(lat):
        y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))
        return int((1 - y / math.pi) / 2 * n)

    return col(west), row(north), col(east), row(south)


def valid_tile(z: int, x: int, y: int) -> bool:
    if not MIN_ZOOM <= z <= MAX_ZOOM:
        return False
    x0, y0, x1, y1 = tile_range(z)
    return x0 <= x <= x1 and y0 <= y <= y1


def tile_path(z: int, x: int, y: int) -> Path:
    return tiles_dir() / str(z) / str(x) / f"{y}.{FORMAT}"


def read_tile(z: int, x: int, y: int):
    """잘라 둔 타일(바이트). 그 자리가 비어 있으면(중국 밖) None."""
    try:
        return tile_path(z, x, y).read_bytes()
    except FileNotFoundError:
        return None


def merc_to_lonlat(mx: float, my: float) -> tuple:
    return mx / HALF * 180.0, math.degrees(2 * math.atan(math.exp(my / 6378137.0)) - math.pi / 2)


def factor_for(z: int) -> int:
    """줌 z 를 구울 때 원본을 몇 분의 일로 줄여 쓰나 — 2 의 거듭제곱. 줄여 둔 그림에서 펴야 계단이 지지 않는다.
    북위 35° 에서 타일 한 화소가 원본 몇 화소인지로 고른다."""
    ground = 2 * HALF / TILE / 2 ** z * math.cos(math.radians(35))
    ratio = ground / 431.0
    factor = 1
    while factor * 2 <= ratio:
        factor *= 2
    return factor


def mesh(z: int, x: int, y: int, factor: int = 1) -> list:
    """`Image.transform(…, Image.MESH, 이것)` 에 줄 칸 목록 — (타일 안 네모, 원본(줄인 것) 안 네 귀)."""
    size = 2 * HALF / 2 ** z
    west, north = -HALF + x * size, HALF - y * size
    step = TILE // MESH
    corners = {}
    for i in range(MESH + 1):
        for j in range(MESH + 1):
            lon, lat = merc_to_lonlat(west + i * step / TILE * size, north - j * step / TILE * size)
            px, py = to_pixel(lon, lat)
            corners[i, j] = (px / factor, py / factor)
    out = []
    for i in range(MESH):
        for j in range(MESH):
            ul, ll, lr, ur = corners[i, j], corners[i, j + 1], corners[i + 1, j + 1], corners[i + 1, j]
            out.append(((i * step, j * step, (i + 1) * step, (j + 1) * step), (*ul, *ll, *lr, *ur)))
    return out


def cut(level_image, factor: int, z: int, x: int, y: int):
    """줌 z 의 타일 한 장(RGBA). `level_image` 는 땅 밖이 투명한 원본을 `factor` 배 줄인 것(RGBa, 미리 곱한 것)이다.
    다 투명하면 None."""
    from PIL import Image
    tile = level_image.transform((TILE, TILE), Image.MESH, mesh(z, x, y, factor), Image.BILINEAR)
    tile = tile.convert("RGBA")
    if tile.getchannel("A").getbbox() is None:
        return None
    return tile


def encode(tile) -> bytes:
    buf = io.BytesIO()
    tile.save(buf, format="WEBP", quality=82, method=4)
    return buf.getvalue()


class China4mError(RuntimeError):
    pass


#: 이 파일이 여는 상류 — `doors.py` 가 모아 views·prewarm·화면의 표를 짓는다 (wetherilli 371)
REGISTRY = [
    {"upstream": "china4m", "tag": "LAB", "title": "연구실 자료"},
]
