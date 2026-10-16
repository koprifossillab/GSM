"""중국 지질도 1:400만 스캔 — 경위선으로 맞춘 좌표 (wetherilli 386).

진짜 스캔(45 MB)은 쓰지 않는다. 좌표는 2026-10-16 에 스캔의 경위선 위에서 짚은 점으로 본다 — 맞춘 모형이 낸 값이
아니라 그림에서 잰 값이라, 상수를 잘못 옮기면 깨진다.
"""
import tempfile
import unittest
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import china4m, views
from viewer.models import Layer, LayerGroup

#: (경선이면 'lon'·위선이면 'lat', 도, 원본 화소 x, y) — 하늘색 경위선의 가운데를 짚은 것
GRATICULE = [
    ("lon", 76, 805.4, 4768.6),
    ("lon", 104, 6810.4, 1846.6),
    ("lon", 124, 10787.0, 4203.1),
    ("lon", 140, 14115.1, 3905.1),
    ("lat", 20, 8455.4, 9295.7),
    ("lat", 32, 13144.7, 5334.7),
    ("lat", 44, 8040.4, 3076.6),
    ("lat", 52, 7107.0, 986.4),
]
#: 한 화소(423 m)를 넘지 않게 — 위도 1° 는 111 km, 경도 1° 는 여기서 70–105 km
TOLERANCE_DEG = 0.004


class Coordinates(SimpleTestCase):
    def test_graticule(self):
        for kind, value, x, y in GRATICULE:
            lon, lat = china4m.to_lonlat(x, y)
            got = lon if kind == "lon" else lat
            with self.subTest(kind=kind, value=value):
                self.assertAlmostEqual(got, value, delta=TOLERANCE_DEG)

    def test_round_trip(self):
        for lon, lat in ((75.0, 40.0), (105.0, 35.0), (121.5, 25.0), (135.0, 48.0)):
            x, y = china4m.to_pixel(lon, lat)
            back = china4m.to_lonlat(x, y)
            self.assertAlmostEqual(back[0], lon, places=7)
            self.assertAlmostEqual(back[1], lat, places=7)

    def test_scale(self):
        """투영 평면의 한 화소는 423 m, 북위 35° 의 땅 위로는 431 m — 두 표준위선 사이라 축척 계수가 1 보다 작다."""
        x0, y0 = china4m.to_pixel(105.0, 35.0)
        x1, y1 = china4m.to_pixel(105.0, 36.0)
        self.assertAlmostEqual(111_000 / ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5, 431, delta=3)

    def test_on_map(self):
        self.assertTrue(china4m.on_map(*china4m.to_pixel(104.0, 30.7)))       # 청두
        self.assertFalse(china4m.on_map(*china4m.to_pixel(112.0, 10.0)))      # 남해제도 — 삽입도 자리 밖
        self.assertFalse(china4m.on_map(1000, 8000))                          # 범례
        self.assertFalse(china4m.on_map(100, 100))                            # 도곽 밖


@unittest.skipUnless(__import__("importlib").util.find_spec("numpy"), "numpy 가 없다 — 마스크는 호스트에서만 굽는다")
class MaskColours(SimpleTestCase):
    def test_classes(self):
        import numpy as np
        from viewer.management.commands.build_china4m_mask import background
        rgb = np.array([[[214, 230, 230], [229, 255, 254], [254, 126, 254], [254, 254, 202], [176, 255, 255]]])
        grey, sea, white, pink, teal, river = background(rgb)
        self.assertEqual(grey[0].tolist(), [True, False, False, False, False])
        self.assertEqual(pink[0].tolist(), [False, False, True, False, False])
        # 노란 제4계는 바탕이 아니다. 쥐라계 J3 의 청록은 바다 수심 색과 같다 — 그래서 색이 아니라 이어짐으로 가른다
        self.assertFalse((grey | sea | white | pink)[0, 3])
        self.assertTrue(sea[0, 4])


class Grid(SimpleTestCase):
    def test_range(self):
        self.assertTrue(china4m.valid_tile(3, 6, 3))                  # 온 중국이 든 z3 의 한 장
        self.assertFalse(china4m.valid_tile(2, 2, 1))                 # 첫 줌 밑
        self.assertFalse(china4m.valid_tile(10, 800, 400))            # 마지막 줌 위 — 화면이 늘린다
        self.assertFalse(china4m.valid_tile(5, 0, 0))                 # 범위 밖

    def test_factor(self):
        """원본 한 화소(431 m)보다 타일 한 화소가 두 배 넘게 거칠면 줄인 원본에서 편다."""
        self.assertEqual(china4m.factor_for(9), 1)
        self.assertEqual(china4m.factor_for(8), 1)
        self.assertEqual(china4m.factor_for(7), 2)
        self.assertEqual(china4m.factor_for(3), 32)


class Cut(SimpleTestCase):
    def test_땅_밖은_투명하고_다_비면_없다(self):
        """원본을 1/32 로 줄인 크기의 가짜 그림 — 오른쪽 반만 칠했다. z3 에서 서쪽(신장) 장은 비고 동쪽 장은 찬다."""
        w, h = china4m.SIZE[0] // 32 + 1, china4m.SIZE[1] // 32 + 1
        level = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        level.paste((200, 100, 50, 255), (w // 2, 0, w, h))
        level = level.convert("RGBa")
        west = china4m.tile_range(3)[0]
        self.assertIsNone(china4m.cut(level, 32, 3, west, 3))
        tile = china4m.cut(level, 32, 3, west + 1, 3)
        self.assertEqual(tile.size, (256, 256))
        self.assertEqual(tile.getpixel((255, 128)), (200, 100, 50, 255))


class TileView(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        patch = override_settings(CHINA4M_DIR=self.tmp.name, PUBLIC=False)
        patch.enable()
        self.addCleanup(patch.disable)

    def test_잘라_둔_것이_없으면_안내_타일(self):
        response = self.client.get("/GSM/china4m/3/6/3.webp")
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_잘라_둔_타일을_내준다(self):
        target = Path(self.tmp.name) / "tiles" / "3" / "6" / "3.webp"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"RIFF fake webp")
        response = self.client.get("/GSM/china4m/3/6/3.webp")
        self.assertEqual(response.content, b"RIFF fake webp")
        self.assertEqual(response["Content-Type"], "image/webp")
        # 중국 밖(잘라 두지 않은 자리)은 투명한 빈 타일
        self.assertEqual(self.client.get("/GSM/china4m/3/5/3.webp").content, views.tiles.blank_tile(256, 256))
        self.assertEqual(self.client.get("/GSM/china4m/3/0/0.webp").status_code, 404)

    def test_밖에_열면_닫는다(self):
        (Path(self.tmp.name) / "tiles").mkdir()
        with override_settings(PUBLIC=True):
            self.assertEqual(self.client.get("/GSM/china4m/3/6/3.webp").status_code, 404)

    def test_카탈로그가_타일을_알린다(self):
        group = LayerGroup.objects.create(name="중국 지질도 1:400만 (2002)", region="china")
        Layer.objects.create(name=china4m.NAME, title="중국 지질도 1:400만 (스캔)", group=group, upstream="china4m")
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        row = rows[china4m.NAME]
        self.assertEqual(row["projection"], "EPSG:3857")
        self.assertEqual(row["tiles"], "china4m/{z}/{x}/{y}.webp")
        self.assertEqual(row["maxZoom"], 9)
        with override_settings(PUBLIC=True):
            rows = {l["name"] for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
            self.assertNotIn(china4m.NAME, rows)
