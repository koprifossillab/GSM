"""미리 데우기와 호출 세기.

`tilegrid` 의 요점은 **브라우저와 한 글자까지 같은 타일**을 셈하는 것이다.
아래 `BBOX` 는 2026-09-27 에 브라우저(OpenLayers 9.2.4)가 실제로 부른 값이다.
옆 타일의 오른쪽 끝(`…706`)과 이 타일의 왼쪽 끝(`…704`)이 끝자리가 다르다 —
곱하는 차례가 달라서다. 그 차이까지 맞아야 캐시가 맞는다.
"""
from django.test import SimpleTestCase, TestCase

from viewer import tilegrid, usage


class Grid(SimpleTestCase):
    SEEN = {
        (9, 436, 200): "14088873.053523686,4304933.433021126,14167144.570487706,4383204.9499851465",
        (10, 874, 401): "14167144.570487704,4304933.433021126,14206280.328969715,4344069.191503136",
        (8, 218, 101): "14088873.053523686,4070118.8821290657,14245416.087451726,4226661.916057107",
    }

    def test_브라우저가_부른_범위와_한_글자까지_같다(self):
        for (z, x, y), bbox in self.SEEN.items():
            self.assertEqual(tilegrid.wms_params("L", z, x, y)["bbox"], bbox, (z, x, y))

    def test_정수는_점을_붙이지_않는다(self):
        """자바스크립트는 0 을 `0` 으로 적는다. 파이썬은 `0.0` 이다."""
        self.assertEqual(tilegrid.js_number(0.0), "0")
        self.assertEqual(tilegrid.js_number(-20037508.342789244), "-20037508.342789244")
        z, x, y = 1, 1, 0                                   # 왼쪽 끝이 정확히 0
        self.assertTrue(tilegrid.wms_params("L", z, x, y)["bbox"].startswith("0,"))

    def test_범위를_덮는_타일(self):
        tiles = list(tilegrid.tiles_for((127.25, 36.33, 127.5, 36.5), 13))
        self.assertTrue(tiles)
        self.assertTrue(all(z == 13 for z, _, _ in tiles))
        # 대전(127.36, 36.37) 을 품은 타일이 들어 있다
        self.assertIn(13, {z for z, _, _ in tiles})

    def test_브라우저와_같은_변수(self):
        p = tilegrid.wms_params("L_50K_Geology_Map", 12, 3490, 1600)
        self.assertEqual((p["version"], p["crs"], p["width"], p["transparent"]),
                         ("1.3.0", "EPSG:3857", "512", "true"))


class Blocked(SimpleTestCase):
    def setUp(self):
        usage.reset()
        self.addCleanup(usage.reset)

    def test_차단의_얼굴(self):
        self.assertTrue(usage.looks_blocked(429))
        self.assertTrue(usage.looks_blocked(403))
        self.assertTrue(usage.looks_blocked(400, b"<H1>Request Blocked</H1>"))
        self.assertFalse(usage.looks_blocked(400, b"bad bbox"))
        self.assertFalse(usage.looks_blocked(500))

    def test_차단_조짐이_이어지면_쉰다(self):
        for _ in range(usage.BLOCK_LIMIT - 1):
            usage.record("kigam", ok=False, blocked=True)
        self.assertFalse(usage.paused())
        usage.record("kigam", ok=False, blocked=True)
        self.assertGreater(usage.paused(), 0)

    def test_쉬는_동안은_상류에_묻지_않는다(self):
        from unittest import mock

        from django.test import override_settings

        from viewer import kigam
        for _ in range(usage.BLOCK_LIMIT):
            usage.record("kigam", ok=False, blocked=True)
        with override_settings(KIGAM_KEY="abc", DEV_DIRECT_WMS=False), \
                mock.patch.object(kigam.requests, "get") as get:
            with self.assertRaises(kigam.UpstreamError):
                kigam.get_map({"layers": "a"})
        get.assert_not_called()


class Counting(TestCase):
    def test_날마다_센다(self):
        from viewer.models import UpstreamDay
        usage.record("kigam", ok=True)
        usage.record("kigam", ok=True)
        usage.record("kigam", ok=False)
        usage.record("vworld", ok=True, count=4)
        usage.reset()
        rows = {r.upstream: r for r in UpstreamDay.objects.all()}
        self.assertEqual((rows["kigam"].ok, rows["kigam"].fail), (2, 1))
        self.assertEqual(rows["vworld"].ok, 4)
