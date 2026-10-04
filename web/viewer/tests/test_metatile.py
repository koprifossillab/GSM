"""메타타일 — 큰 장을 한 번 받아 칸으로 잘라 담는다 (wetherilli 282). 상류는 바꿔 끼운다."""
import io
import tempfile
import threading
import time
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from PIL import Image

from viewer import metatile, sgm, views

R = metatile.R


def wms(z, x, y, px=512, layer="sgm:datos:7"):
    """OpenLayers `createXYZ` 격자의 한 칸을 브라우저처럼 — 소수 자리는 JS 가 쓰는 꼴(17 자리)과 다를 수 있다"""
    span = 2 * R / 2 ** z
    w, n = -R + x * span, R - y * span
    return {"layers": layer, "crs": "EPSG:3857", "bbox": f"{w:.10f},{n - span:.10f},{w + span:.10f},{n:.10f}",
            "width": str(px), "height": str(px), "format": "image/png", "transparent": "true", "version": "1.3.0"}


def quadrants(px):
    """2×2 칸마다 다른 색 — 어느 조각이 어디서 잘렸는지 본다"""
    big = Image.new("RGBA", (px * 2, px * 2))
    for j in range(2):
        for i in range(2):
            big.paste((40 + 100 * i, 40 + 100 * j, 0, 255), (i * px, j * px, (i + 1) * px, (j + 1) * px))
    buf = io.BytesIO()
    big.save(buf, "PNG")
    return buf.getvalue()


class Metatile(SimpleTestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-meta-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_격자의_칸(self):
        self.assertEqual(metatile.tile_of(wms(8, 57, 112)), (8, 57, 112, 512))
        off = wms(8, 57, 112)
        w, s, e, n = (float(v) for v in off["bbox"].split(","))
        off["bbox"] = f"{w + 100},{s},{e + 100},{n}"                                # 격자에서 어긋났다
        self.assertIsNone(metatile.tile_of(off))
        self.assertIsNone(metatile.tile_of(dict(wms(8, 57, 112), crs="EPSG:4326")))

    def test_한_번_받아_넷으로(self):
        calls = []

        def fetch(bbox, w, h):
            calls.append((bbox, w, h))
            return quadrants(512), "image/png"
        a = metatile.serve("L", wms(8, 57, 113), fetch)                               # 메타타일 (56,112) 의 오른쪽 아래
        b = metatile.serve("L", wms(8, 56, 112), fetch)                               # 왼쪽 위 — 캐시에서
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1:], (1024, 1024))
        self.assertEqual(Image.open(io.BytesIO(a)).convert("RGBA").getpixel((5, 5)), (140, 140, 0, 255))
        self.assertEqual(Image.open(io.BytesIO(b)).convert("RGBA").getpixel((5, 5)), (40, 40, 0, 255))
        w, s, e, n = (float(v) for v in calls[0][0].split(","))
        span = 2 * R / 2 ** 8
        self.assertAlmostEqual(w, -R + 56 * span, places=3)
        self.assertAlmostEqual(n, R - 112 * span, places=3)
        self.assertAlmostEqual(e - w, 2 * span, places=3)

    def test_동시에_두_번_받지_않는다(self):
        calls = []

        def fetch(bbox, w, h):
            calls.append(bbox)
            time.sleep(0.3)
            return quadrants(512), "image/png"
        out = []
        threads = [threading.Thread(target=lambda t=t: out.append(metatile.serve("L", wms(9, 100 + t % 2, 200), fetch)))
                   for t in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(out), 4)
        self.assertTrue(all(out))


class View(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-meta-view-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=open("/dev/null", "w"))

    def test_지자기는_메타타일로(self):
        sent = []

        def fake(url, params=None, **kw):
            sent.append(params)
            return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=quadrants(512), url=url)
        with mock.patch.object(sgm.requests, "get", side_effect=fake), \
             mock.patch.object(sgm.usage, "record"), mock.patch.object(sgm.usage, "paused", return_value=0):
            first = self.client.get("/GSM/wms/", {k.upper(): v for k, v in wms(8, 56, 112).items()} | {"SERVICE": "WMS", "REQUEST": "GetMap"})
            second = self.client.get("/GSM/wms/", {k.upper(): v for k, v in wms(8, 57, 112).items()} | {"SERVICE": "WMS", "REQUEST": "GetMap"})
        self.assertEqual((first.status_code, second.status_code), (200, 200))
        self.assertEqual(len(sent), 1)                                                # 이웃 칸은 상류를 타지 않는다
        self.assertEqual(sent[0]["size"], "1024,1024")
        rows = {l["name"]: l for g in views._catalog("ko") for l in g["layers"]}
        self.assertEqual((rows["sgm:datos:7"]["minZoom"], rows["sgm:datos:7"]["queryable"]), (8, False))

    def test_다른_레이어는_그대로(self):
        sent = []

        def fake(url, params=None, **kw):
            sent.append(params)
            return mock.Mock(status_code=200, headers={"content-type": "image/png"}, content=quadrants(256), url=url)
        with mock.patch.object(sgm.requests, "get", side_effect=fake), \
             mock.patch.object(sgm.usage, "record"), mock.patch.object(sgm.usage, "paused", return_value=0):
            self.client.get("/GSM/wms/", {k.upper(): v for k, v in wms(8, 56, 112, layer="sgm:8").items()} | {"SERVICE": "WMS", "REQUEST": "GetMap"})
        self.assertEqual(sent[0]["size"], "512,512")
