"""NASA Moon Trek — 달의 문 (devlog 036, P05).

Trek 을 실제로 부르지 않는다. 응답의 꼴은 2026-09-29 에 받아 본 그대로다 — `identify` 는
열 이름을 `FIRST_Unit`·`FIRST_Un_1` 처럼 잘라 주고, 표고 `exportImage` 는 F32 TIFF 다.
"""
import io
import json
import tempfile
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import i18n, trek, views

#: identify 가 준 앞면의 바다 한 조각 (2026-09-29, 줄였다)
MARE = {"FID": "6735", "Shape": "Polygon", "FIRST_Unit": "Im2", "FIRST_Un_1": "Imbrian",
        "FIRST_Un_2": "Upper Mare Unit", "UnitDescri": "Forms flat, smooth surfaces.",
        "Interpreta": "Basaltic lava flows", "Shape_Area": "3626548556360"}


def response(body=None, *, status=200, ctype="application/json", content=None):
    content = content if content is not None else json.dumps(body).encode()
    return mock.Mock(status_code=status, headers={"content-type": ctype}, content=content,
                     url="https://trek.nasa.gov/moon/…", json=lambda: body)


def tiff(values, size=trek.DEM_SIZE):
    image = Image.new("F", (size, size))
    image.putdata(values)
    out = io.BytesIO()
    image.save(out, "TIFF")
    return out.getvalue()


class Grid(SimpleTestCase):
    """경위도 격자 — 줌 0 이 가로 2 장·세로 1 장이고 y 는 북쪽부터."""

    def test_줌_0_의_두_장(self):
        self.assertEqual(trek.tile_bbox(0, 0, 0), (-180.0, -90.0, 0.0, 90.0))
        self.assertEqual(trek.tile_bbox(0, 1, 0), (0.0, -90.0, 180.0, 90.0))

    def test_y_는_북쪽부터_센다(self):
        w, s, e, n = trek.tile_bbox(2, 4, 3)
        self.assertEqual((w, s, e, n), (0.0, -90.0, 45.0, -45.0))

    def test_격자_밖은_없다(self):
        self.assertTrue(trek.valid_tile(0, 1, 0))
        self.assertFalse(trek.valid_tile(0, 2, 0))
        self.assertFalse(trek.valid_tile(0, 0, 1))
        self.assertFalse(trek.valid_tile(trek.MAX_ZOOM + 1, 0, 0))


class Upstream(SimpleTestCase):

    def test_지질도는_달_경위도로_묻는다(self):
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            self.assertEqual(trek.get_tile("units", 1, 2, 0), b"png")
        url, params = get.call_args[0][0], get.call_args[1]["params"]
        self.assertTrue(url.endswith("/Unified_Global_Geologic_Map_of_the_Moon_Geologic_Units/MapServer/export"))
        self.assertEqual((params["bboxSR"], params["imageSR"]), (104903, 104903))
        self.assertEqual(params["bbox"], "0.0,0.0,90.0,90.0")

    def test_그림이_아니면_오류(self):
        with mock.patch("viewer.trek.requests.get", return_value=response({"error": {"message": "x"}})):
            with self.assertRaises(trek.TrekError):
                trek.get_tile("units", 0, 0, 0)

    def test_모르는_레이어는_묻지_않는다(self):
        with mock.patch("viewer.trek.requests.get") as get, self.assertRaises(trek.TrekError):
            trek.get_tile("craters", 0, 0, 0)
        get.assert_not_called()

    def test_속성은_단위_시대_이름_설명_해석(self):
        body = {"results": [{"layerId": 0, "attributes": MARE}]}
        with mock.patch("viewer.trek.requests.get", return_value=response(body)):
            hit = trek.identify(-15, 20)
        self.assertEqual(hit["unit"], "Im2")
        self.assertEqual([label for label, _ in hit["rows"]], ["단위", "시대", "이름", "설명", "해석"])
        self.assertEqual(hit["rows"][1][1], "Imbrian")

    def test_빈_자리는_None(self):
        with mock.patch("viewer.trek.requests.get", return_value=response({"results": []})):
            self.assertIsNone(trek.identify(0, 0))

    def test_ArcGIS_의_200_오류(self):
        with mock.patch("viewer.trek.requests.get", return_value=response({"error": {"message": "bad"}})):
            with self.assertRaises(trek.TrekError):
                trek.identify(0, 0)


class Dem(SimpleTestCase):

    def test_가장자리가_이웃과_겹치게_반_칸_넓혀_묻는다(self):
        raw = tiff([-1914.5] * trek.DEM_SIZE ** 2)
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/tiff", content=raw)) as get:
            png = trek.dem_tile(0, 0, 0)
        w, s, e, n = (float(v) for v in get.call_args[1]["params"]["bbox"].split(","))
        half = 180 / 64 / 2
        self.assertAlmostEqual(w, -180 - half)
        self.assertAlmostEqual(n, 90 + half)
        image = Image.open(io.BytesIO(png)).convert("RGB")
        self.assertEqual(image.size, (trek.DEM_SIZE, trek.DEM_SIZE))
        r, g, b = image.getpixel((10, 10))
        self.assertAlmostEqual(r * 256 + g + b / 256 - 32768, -1914.5, places=1)

    def test_자료_밖은_0_m(self):
        raw = tiff([-3.4e38] * trek.DEM_SIZE ** 2)
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/tiff", content=raw)):
            png = trek.dem_tile(0, 0, 0)
        r, g, b = Image.open(io.BytesIO(png)).convert("RGB").getpixel((0, 0))
        self.assertEqual(r * 256 + g + b / 256 - 32768, 0)


class Places(SimpleTestCase):
    PLACES = [["Apollo", "Crater", -151.8, -36.1], ["Apollo 11", "Landing site", 23.48, 0.67],
              ["Tycho", "Crater", -11.36, -43.31], ["Tycho A", "Satellite Feature", -12.13, -39.94],
              ["Mare Tranquillitatis", "Mare", 31.4, 8.35]]

    def test_앞이_맞는_것이_먼저_착륙지가_맨_앞(self):
        got = trek.search_places(self.PLACES, "apollo")
        self.assertEqual([p["name"] for p in got], ["Apollo 11", "Apollo"])

    def test_들어_있는_것도_찾는다(self):
        self.assertEqual(trek.search_places(self.PLACES, "tranq")[0]["name"], "Mare Tranquillitatis")

    def test_빈_검색은_빈_답(self):
        self.assertEqual(trek.search_places(self.PLACES, "  "), [])

    def test_색인에서_지명과_착륙지를_추린다(self):
        docs = [
            {"itemType": "nomenclature", "title": "Tycho", "productType": "Crater, craters",
             "bbox": "-11.36,-43.31,-11.36,-43.31"},
            {"itemType": "nomenclature", "title": "Lacus Mortis", "productType": "Lacus, lac?à?½s",
             "bbox": "27.3,45,27.3,45"},
            {"itemType": "bookmark", "title": "Apollo 11", "bbox": "23.46,0.66,23.49,0.67"},
            {"itemType": "product", "title": "LRO WAC", "bbox": "-180,-90,180,90"},
            {"itemType": "nomenclature", "title": "Far", "productType": "Crater", "bbox": "200,10,200,10"},
        ]
        with mock.patch("viewer.trek.requests.get", return_value=response({"response": {"docs": docs}})):
            got = trek.fetch_places()
        self.assertEqual([p[0] for p in got], ["Apollo 11", "Far", "Lacus Mortis", "Tycho"])
        self.assertEqual(dict((p[0], p[1]) for p in got)["Lacus Mortis"], "Lacus")   # 깨진 복수는 버린다
        self.assertEqual(dict((p[0], p[2]) for p in got)["Far"], -160.0)             # 0–360 → −180–180


class MoonViews(TestCase):

    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-trek-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_지질도_타일은_캐시에_담고_다시_묻지_않는다(self):
        url = reverse("viewer:moon-tile", args=["units", 1, 2, 0])
        with mock.patch("viewer.trek.requests.get", return_value=response(ctype="image/png", content=b"png")) as get:
            first = self.client.get(url)
            second = self.client.get(url)
        self.assertEqual((first["X-GSM-Cache"], second["X-GSM-Cache"]), ("miss", "hit"))
        self.assertEqual(get.call_count, 1)

    def test_격자_밖_타일은_404(self):
        self.assertEqual(self.client.get(reverse("viewer:moon-tile", args=["units", 0, 5, 0])).status_code, 404)
        self.assertEqual(self.client.get(reverse("viewer:moon-tile", args=["nope", 0, 0, 0])).status_code, 404)

    def test_표고를_못_받으면_502(self):
        with mock.patch("viewer.trek.requests.get", return_value=response(status=500, ctype="text/html", content=b"")):
            self.assertEqual(self.client.get(reverse("viewer:moon-dem", args=[0, 0, 0])).status_code, 502)

    def test_한국어판은_시대를_옮긴다(self):
        body = {"results": [{"attributes": MARE}]}
        with mock.patch("viewer.trek.requests.get", return_value=response(body)):
            ko = self.client.get(reverse("viewer:moon-info"), {"lon": -15, "lat": 20}).json()
            self.client.cookies[i18n.COOKIE] = "en"
            en = self.client.get(reverse("viewer:moon-info"), {"lon": -15, "lat": 20}).json()
        self.assertIn(["시대", "임브리움기"], ko["rows"])
        self.assertIn(["Age", "Imbrian"], en["rows"])
        self.assertIn(["Name", "Upper Mare Unit"], en["rows"])       # 값은 옮기지 않는다

    def test_좌표가_없으면_400(self):
        self.assertEqual(self.client.get(reverse("viewer:moon-info"), {"lon": "x"}).status_code, 400)

    def test_지명_찾기는_저장소의_파일을_뒤진다(self):
        views._moon_places.cache_clear()
        self.addCleanup(views._moon_places.cache_clear)
        got = self.client.get(reverse("viewer:moon-places"), {"q": "apollo 11"}).json()["results"]
        self.assertEqual(got[0]["name"], "Apollo 11")
        self.assertEqual(got[0]["kind"], "Landing site")
