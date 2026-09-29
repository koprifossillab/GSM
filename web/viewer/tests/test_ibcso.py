"""남극 IBCSO v2 — 9354 원본을 3031 격자로 자르기 (047).

두 평사도법은 표준위도만 달라 곱셈 하나로 오간다. 그 배율이 맞으면 원본의 화소가 제자리에 간다.
"""
import io
import math
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import geomap, ibcso


def ps_south(lat, lon, lat_ts):
    """남극 평사도법 (WGS84, 경도 0 이 위) — 표준위도만 바꿔 부른다."""
    a, e = 6378137.0, geomap._E
    phi, pc = math.radians(-lat), math.radians(lat_ts)
    t = lambda p: math.tan(math.pi / 4 - p / 2) / ((1 - e * math.sin(p)) / (1 + e * math.sin(p))) ** (e / 2)
    m = lambda p: math.cos(p) / math.sqrt(1 - (e * math.sin(p)) ** 2)
    rho = a * m(pc) * t(phi) / t(pc)
    lam = math.radians(lon)
    return rho * math.sin(lam), rho * math.cos(lam)


class Grid(SimpleTestCase):
    def test_배율은_3031_과_9354_의_거리_비(self):
        for lat, lon in [(-77.85, 166.67), (-62.22, -58.79), (-89.0, 45.0)]:
            x31, y31 = geomap.lonlat_to_3031(lon, lat)
            x93, y93 = ps_south(lat, lon, 65.0)
            self.assertAlmostEqual(x31 / x93, ibcso.SCALE, places=9)
            self.assertAlmostEqual(y31 / y93, ibcso.SCALE, places=9)

    def test_한_점이_원본의_제_화소에_간다(self):
        lat, lon, z = -77.85, 166.67, 6                     # 맥머도
        x31, y31 = geomap.lonlat_to_3031(lon, lat)
        tx, ty = geomap.tile_of(z, x31, y31)
        left, top, right, bottom = ibcso.source_box(z, tx, ty)
        x93, y93 = ps_south(lat, lon, 65.0)
        col, row = (x93 + 4800000) / 500, (4800000 - y93) / 500
        self.assertTrue(left <= col <= right and top <= row <= bottom)

    def test_z0_은_원본의_가운데를_덮는다(self):
        left, top, right, bottom = ibcso.source_box(0, 0, 0)
        self.assertAlmostEqual((left + right) / 2, 9600, places=6)
        self.assertAlmostEqual((top + bottom) / 2, 9600, places=6)
        self.assertLess(left, 9600 - 6000)                  # 남위 60° 넘어까지

    def test_자르기_밖은_투명(self):
        level = Image.new("RGBa", (600, 600), (40, 80, 120, 255))     # 원본의 1/32
        tile = ibcso.cut(level, 32, 0, 0, 0)
        self.assertEqual(tile.size, (256, 256))
        self.assertEqual(tile.getpixel((128, 128))[3], 255)
        self.assertIsNone(ibcso.cut(Image.new("RGBa", (600, 600), (0, 0, 0, 0)), 32, 0, 0, 0))


class View(TestCase):
    def test_잘라_두지_않았으면_안내_타일(self):
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            r = self.client.get("/GSM/ibcso/bed/3/2/2.webp")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Cache-Control"], "no-store")

    def test_잘라_둔_것을_내고_없는_자리는_빈_타일(self):
        with tempfile.TemporaryDirectory() as d, override_settings(IBCSO_DIR=d):
            p = Path(d) / "tiles-ice" / "3" / "2" / "2.webp"
            p.parent.mkdir(parents=True)
            buf = io.BytesIO()
            Image.new("RGBA", (256, 256), (1, 2, 3, 255)).save(buf, "WEBP")
            p.write_bytes(buf.getvalue())
            r = self.client.get("/GSM/ibcso/ice/3/2/2.webp")
            self.assertEqual(r["Content-Type"], "image/webp")
            r = self.client.get("/GSM/ibcso/ice/3/0/0.webp")
            self.assertEqual(r["Content-Type"], "image/png")

    def test_줌_밖과_모르는_판은_404(self):
        self.assertEqual(self.client.get("/GSM/ibcso/bed/7/0/0.webp").status_code, 404)
        self.assertEqual(self.client.get("/GSM/ibcso/bed/2/4/0.webp").status_code, 404)
        self.assertEqual(self.client.get("/GSM/ibcso/nope/2/0/0.webp").status_code, 404)
