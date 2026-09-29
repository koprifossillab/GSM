"""평면 격자 타일을 3857 로 다시 펴기 — 3D 가 한반도 지질도를 얹는 길.

원본이 우리 격자의 어디에 떨어지는지만 맞으면 그림이 제자리에 간다. 합성 격자(한 칸이
한 색인 원본)를 펴서, 3857 타일의 한 점이 원본의 알맞은 칸 색을 받는지 본다.
"""
import io
import math

from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import warp


def lonlat_tile(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def solid(color):
    buf = io.BytesIO()
    Image.new("RGBA", (256, 256), color).save(buf, "PNG")
    return buf.getvalue()


class Render(SimpleTestCase):
    def grid(self):
        """5179 에 원점을 둔 가짜 격자 — 한 픽셀 100 m, 타일 번호마다 다른 색."""
        self.fetched = []
        ox, oy = 900000.0, 2000000.0

        def fetch(level, tx, ty):
            self.fetched.append((level, tx, ty))
            return solid(((tx * 40) % 256, (ty * 40) % 256, 90, 255))

        return warp.Grid(levels=[0], res=lambda level: 100.0, origin=lambda level: (ox, oy),
                         project=warp.to_5179, fetch=fetch)

    def test_한_점이_제_타일의_색을_받는다(self):
        lat, lon, z = 37.5, 127.0, 9
        fx, fy = lonlat_tile(lat, lon, z)
        x, y = int(fx), int(fy)
        png = warp.render(self.grid(), z, x, y)
        image = Image.open(io.BytesIO(png)).convert("RGBA")
        px, py = int((fx - x) * 256), int((fy - y) * 256)
        east, north = warp.to_5179(lat, lon)
        tx, ty = int((east - 900000) // 25600), int((2000000 - north) // 25600)
        self.assertEqual(image.getpixel((px, py))[:2], ((tx * 40) % 256, (ty * 40) % 256))

    def test_원본이_없으면_None(self):
        grid = self.grid()
        grid.fetch = lambda level, tx, ty: None
        self.assertIsNone(warp.render(grid, 9, 436, 199))

    def test_단계는_땅_해상도보다_촘촘한_것_가운데_가장_거친_것(self):
        grid = warp.Grid(levels=range(7, 14), res=lambda l: 2.0 ** (l - 3), origin=None,
                         project=None, fetch=None)
        self.assertEqual(grid.pick(120), 9)        # 64 m
        self.assertEqual(grid.pick(30), 7)         # 16 m
        self.assertEqual(grid.pick(5), 7)          # 가장 촘촘한 것도 모자라면 그것

    def test_카카오_격자는_번호를_뒤집어_넘긴다(self):
        asked = []
        grid = warp.kakao_grid((7, 13), (-30000, -60000), (2, 5),
                               lambda level, x, y: asked.append((level, x, y)))
        grid.fetch(13, 0, 0)                       # 위에서 첫 줄 = 아래에서 다섯째 줄
        self.assertEqual(asked, [(13, 0, 4)])
        self.assertEqual(grid.origin(13), (-30000, -60000 + 5 * 256 * 1024))


class WarpView(TestCase):
    def test_밖에_열면_닫힌다(self):
        with override_settings(PUBLIC=True):
            r = self.client.get("/GSM/warp/peninsula/shaded/10/873/396.png")
        self.assertEqual(r.status_code, 404)

    def test_모르는_레이어와_먼_줌은_404(self):
        self.assertEqual(self.client.get("/GSM/warp/peninsula/nope/10/873/396.png").status_code, 404)
        self.assertEqual(self.client.get("/GSM/warp/peninsula/shaded/3/1/1.png").status_code, 404)
