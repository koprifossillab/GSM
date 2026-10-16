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


class China4mError(RuntimeError):
    pass
