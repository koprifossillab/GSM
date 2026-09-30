"""그때 그 자리 — PALEOMAP 2016 판 회전 (wetherilli 087).

저장소의 `data/paleomap2016.json` 을 그대로 읽는다(125 KB). 기대값은 2026-09-30 에 EarthThruTime3D 의
`scripts/rotation_model.py` 로 원본 `.rot` 을 읽어 셈한 것과 맞춘 값이다(차이 0.01° 안).
"""
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import macrostrat, paleo
from viewer.management.commands import build_paleomap


class Carry(SimpleTestCase):
    def setUp(self):
        self.m = paleo.model()

    def test_오늘은_그대로(self):
        got = self.m.carry(126.98, 37.57, 0)
        self.assertEqual((got["lon"], got["lat"]), (126.98, 37.57))

    def test_서울은_250_Ma_에(self):
        got = self.m.carry(126.98, 37.57, 250)
        self.assertAlmostEqual(got["lon"], 105.01, delta=0.02)
        self.assertAlmostEqual(got["lat"], 30.58, delta=0.02)
        self.assertEqual((got["pid"], got["reach"]), (604, 1100.0))

    def test_런던의_판은_600_Ma_까지(self):
        got = self.m.carry(-0.13, 51.5, 800)
        self.assertEqual((got["reason"], got["reach"]), ("beyond", 600.0))
        self.assertIn("lon", self.m.carry(-0.13, 51.5, 500))

    def test_바다_밑은_옮기지_못한다(self):
        self.assertEqual(self.m.carry(-150, 0, 100)["reason"], "ocean")

    def test_남극점_가까이도(self):
        # 극을 두른 다각형 — 경위도로 재면 틀리는 자리다
        self.assertEqual(self.m.plate_at(0, -85)["pid"], 802)


class Inside(SimpleTestCase):
    def test_날짜변경선을_넘는_고리(self):
        ring = [170, -10, -170, -10, -170, 10, 170, 10]
        self.assertTrue(paleo.inside(179.5, 0, ring))
        self.assertTrue(paleo.inside(-179.5, 0, ring))
        self.assertFalse(paleo.inside(100, 0, ring))
        # 대척점은 감김으로 못 가른다 — 대륙의 가운데를 바라보는지로 가른다
        self.assertTrue(paleo.inside(0, 0, ring))
        self.assertFalse(paleo.holds({"rings": [ring]}, 0, 0))
        self.assertTrue(paleo.holds({"rings": [ring]}, 179.5, 0))

    def test_극을_두른_고리(self):
        ring = [lon for k in range(0, 360, 30) for lon in (k - 180, -70)]
        self.assertTrue(paleo.inside(45, -89, ring))
        self.assertFalse(paleo.inside(45, -60, ring))


GPML = """<gml:featureMember><gpml:UnclassifiedFeature>
<gpml:reconstructionPlateId><gpml:ConstantValue><gpml:value>604</gpml:value></gpml:ConstantValue></gpml:reconstructionPlateId>
<gml:validTime><gml:TimePeriod><gml:begin><gml:TimeInstant><gml:timePosition>4500</gml:timePosition></gml:TimeInstant></gml:begin>
<gml:end><gml:TimeInstant><gml:timePosition gml:frame="http://gplates.org/TRS/flat">http://gplates.org/times/distantFuture</gml:timePosition></gml:TimeInstant></gml:end></gml:TimePeriod></gml:validTime>
<gml:posList gml:dimension="2">30 120 30 130 40 130 40 120 30 120</gml:posList>
</gpml:UnclassifiedFeature></gml:featureMember>
<gml:featureMember><gpml:UnclassifiedFeature>
<gpml:reconstructionPlateId><gpml:ConstantValue><gpml:value>999</gpml:value></gpml:ConstantValue></gpml:reconstructionPlateId>
<gml:validTime><gml:TimePeriod><gml:begin><gml:TimeInstant><gml:timePosition>0</gml:timePosition></gml:TimeInstant></gml:begin>
<gml:end><gml:TimeInstant><gml:timePosition>0</gml:timePosition></gml:TimeInstant></gml:end></gml:TimePeriod></gml:validTime>
<gml:posList gml:dimension="2">-80 -180 -80 180 80 180 80 -180 -80 -180</gml:posList>
</gpml:UnclassifiedFeature></gml:featureMember>"""
ROT = "604 0.0 90.0 0.0 0.0 000 !\n604 100.0 10.0 20.0 30.0 000 !\n604 100.0 10.0 20.0 30.0 000 ! 거듭\n"


class Build(SimpleTestCase):
    def test_GPML_은_위도가_먼저(self):
        f = list(build_paleomap.features(GPML))[0]
        self.assertEqual((f["pid"], f["from"], f["to"]), (604, 4500.0, -1e9))
        self.assertEqual(f["rings"][0][:4], [120.0, 30.0, 130.0, 30.0])

    def test_거듭_적힌_때는_하나만(self):
        self.assertEqual(build_paleomap.rotations(ROT), {"604:0": [0.0, 90.0, 0.0, 0.0, 100.0, 10.0, 20.0, 30.0]})

    def test_0_Ma_에만_있는_다각형은_버린다(self):
        # 온 지구를 덮는 순간의 다각형 — 두면 바다 밑도 판을 얻는다
        out = Path(tempfile.mkdtemp()) / "pm.json"
        zpath = Path(tempfile.mkdtemp()) / "a.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr(build_paleomap.ROTATION, ROT)
            zf.writestr(build_paleomap.POLYGONS, GPML)
        with mock.patch.dict(build_paleomap.SHA256, {build_paleomap.ROTATION: __import__("hashlib").sha256(ROT.encode()).hexdigest()}):
            call_command("build_paleomap", str(zpath), out=str(out), stdout=io.StringIO())
        self.assertEqual([f["pid"] for f in json.loads(out.read_text())["features"]], [604])

    def test_확인값이_다르면_멈춘다(self):
        zpath = Path(tempfile.mkdtemp()) / "a.zip"
        with zipfile.ZipFile(zpath, "w") as zf:
            zf.writestr(build_paleomap.ROTATION, ROT)
            zf.writestr(build_paleomap.POLYGONS, GPML)
        with self.assertRaises(CommandError):
            call_command("build_paleomap", str(zpath), out=str(zpath) + ".json", stdout=io.StringIO())


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-paleo-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_옛_위치(self):
        data = self.client.get(reverse("viewer:earth-paleo"), {"lon": 126.98, "lat": 37.57, "age": 250}).json()
        self.assertTrue(data["text"].startswith("북위 30.5"), data["text"])
        self.assertEqual(data["model"], "Scotese 2016 PALEOMAP")
        self.assertEqual(self.client.get(reverse("viewer:earth-paleo"), {"lon": 1}).status_code, 400)

    def test_누르면_단위의_연대마다_한_줄(self):
        seoul = {"source_id": 154, "name": "Precambrian crystalline metamorphic rocks", "b_int_name": "Precambrian",
                 "t_int_name": "Precambrian", "b_age": 4000, "t_age": 541, "color": "#F04370"}
        hit = {"units": [macrostrat.unit_row(seoul, "tiny")], "refs": {}}
        with mock.patch.object(macrostrat, "identify", return_value=hit):
            rows = dict(self.client.get(reverse("viewer:earth-info"), {"lon": 126.98, "lat": 37.57, "z": 8})
                        .json()["units"][0]["rows"])
        self.assertTrue(rows["그때의 자리 (541 Ma)"].startswith("북위 13."))
        self.assertEqual(rows["그때의 자리 (4000 Ma)"], "이 판은 1100 Ma 까지만 거슬러 옮긴다")

    def test_파일이_없으면_그_줄_없이(self):
        paleo.model.cache_clear()
        self.addCleanup(paleo.model.cache_clear)
        with override_settings(PALEOMAP_FILE="/nonexistent/pm.json"):
            self.assertEqual(self.client.get(reverse("viewer:earth-paleo"),
                                             {"lon": 1, "lat": 1, "age": 1}).status_code, 503)
