"""그린란드 정부 포털 — 점을 통째로 받는 네 번째 문.

포털을 실제로 부르지 않는다. 응답의 꼴은 2026-09-27 에 받아 본 그대로다
(`f=geojson`, 한 장에 2 000 점, 더 있으면 `exceededTransferLimit`).
"""
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import grportal, i18n, views
from viewer.models import Layer, LayerGroup


def feature(fid, lon=-22.3419997584601, lat=70.5526333267045, **props):
    base = {"sample_no": "05EH-15", "age_num": 397.3, "uncertaint": "       1.7",
            "formation": " ", "details": "http://data.geus.dk/gg_detail/?cat=gcr&id=59"}
    base.update(props)
    return {"type": "Feature", "id": fid,
            "geometry": {"type": "Point", "coordinates": [lon, lat]}, "properties": base}


def page(features, more=False):
    body = {"type": "FeatureCollection", "features": features}
    if more:
        body["properties"] = {"exceededTransferLimit": True}
    return mock.Mock(status_code=200, content=json.dumps(body).encode(), json=lambda: body)


class Compact(SimpleTestCase):
    fields = grportal.LAYERS["grportal:geochron"]["fields"]

    def test_빈칸을_떼고_빈_값은_뺀다(self):
        got = grportal.compact(feature(1), self.fields)
        self.assertEqual(got["properties"]["err"], "1.7")
        self.assertEqual(got["properties"]["age"], 397.3)
        self.assertNotIn("fm", got["properties"])                    # " " 뿐이었다
        self.assertEqual(got["geometry"]["coordinates"], [-22.342, 70.55263])

    def test_http_가_아닌_주소는_받지_않는다(self):
        got = grportal.compact(feature(1, details="javascript:alert(1)"), self.fields)
        self.assertNotIn("link", got["properties"])

    def test_점이_아니면_버린다(self):
        f = feature(1)
        f["geometry"] = None
        self.assertIsNone(grportal.compact(f, self.fields))

    def test_시료의_색은_rgb_에서(self):
        fields = grportal.LAYERS["grportal:samples"]["fields"]
        got = grportal.compact({"id": 1, "geometry": {"type": "Point", "coordinates": [0, 0]},
                                "properties": {"rgb": "220 220 0", "material_s": "   Black sand\r\nBlack sand"}},
                               fields)
        self.assertEqual(got["properties"]["color"], "#dcdc00")
        self.assertEqual(got["properties"]["mat"], "Black sand Black sand")


class Fetch(SimpleTestCase):
    def test_장을_넘기며_끝까지_받는다(self):
        pages = [page([feature(1), feature(2)], more=True), page([feature(3)])]
        with mock.patch.object(grportal, "PAGE", 2), \
                mock.patch.object(grportal.requests, "get", side_effect=pages) as get, \
                mock.patch.object(grportal.usage, "record"):
            got = grportal.fetch("grportal:geochron", pause=0)
        self.assertEqual([f["id"] for f in got], [1, 2, 3])
        self.assertEqual([c.kwargs["params"]["resultOffset"] for c in get.call_args_list], [0, 2])
        first = get.call_args_list[0]
        self.assertEqual(first.kwargs["headers"]["User-Agent"], "GSM/0.1")
        self.assertEqual(first.kwargs["params"]["outSR"], "4326")
        self.assertIn("geochron/FeatureServer/0/query", first.args[0])

    def test_200_에_실린_오류도_오류다(self):
        body = {"error": {"code": 400, "message": "Invalid query"}}
        resp = mock.Mock(status_code=200, content=json.dumps(body).encode(), json=lambda: body)
        with mock.patch.object(grportal.requests, "get", return_value=resp), \
                mock.patch.object(grportal.usage, "record"):
            with self.assertRaises(grportal.PortalError):
                grportal.fetch("grportal:geochron", pause=0)


class Words(SimpleTestCase):
    """팝업 이름·레이어·레이어군의 영어가 표에 있다 (CLAUDE.md "영어판")."""

    def test_팝업_이름은_모두_PROP_EN_에(self):
        for name in grportal.LAYERS:
            for label in grportal.labels(name).values():
                self.assertIn(label, i18n.PROP_EN, label)

    def test_레이어와_레이어군(self):
        seed = json.loads((views.settings.GRPORTAL_CATALOG_SEED).read_text(encoding="utf-8"))
        for row in seed["레이어"]:
            self.assertIn(row["name"], i18n.LAYER_EN)
            self.assertIn(row["name"], grportal.LAYERS)              # 씨앗과 문이 짝이 맞다
        for group in seed["레이어군순서"]:
            self.assertIn(group, i18n.GROUP_EN)


class View(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-grp-"),
                                  TILE_CACHE_MIN_FREE_BYTES=0)
        patch.enable()
        self.addCleanup(patch.disable)
        g = LayerGroup.objects.create(name="시료·연대 (정부 포털)", region="greenland")
        Layer.objects.create(name="grportal:geochron", title="연대측정", group=g, upstream="grportal")

    def test_카탈로그에_점_레이어라고_적는다(self):
        layer = views._catalog()[0]["layers"][0]
        self.assertEqual(layer["kind"], "points")
        self.assertFalse(layer["queryable"])                        # /featureinfo/ 를 부르지 않는다
        self.assertEqual(layer["style"], "age")
        self.assertIn("6ddb07fed184429cab4c8a3f1326d644", layer["source"])

    def test_한_번_받으면_다시_묻지_않는다(self):
        with mock.patch.object(grportal, "fetch", return_value=[grportal.compact(
                feature(7), grportal.LAYERS["grportal:geochron"]["fields"])]) as up:
            r1 = self.client.get("/GSM/points/", {"layer": "grportal:geochron"})
            r2 = self.client.get("/GSM/points/", {"layer": "grportal:geochron"})
        self.assertEqual(up.call_count, 1)
        self.assertEqual(r1.status_code, 200)
        data = json.loads(r2.content)
        self.assertEqual(data["features"][0]["id"], 7)
        self.assertEqual(data["labels"]["age"], "연대 (Ma)")
        self.assertEqual(data["style"], "age")

    def test_줄여서_보낸다(self):
        # 점이 넉넉해야 한다. Django 는 줄인 것에 무작위 바이트를 덧대어(BREACH 막이)
        # 짧은 본문은 줄인 쪽이 더 길어지는 때가 있고, 그러면 줄이지 않고 보낸다
        rows = [grportal.compact(feature(i), grportal.LAYERS["grportal:geochron"]["fields"])
                for i in range(50)]
        with mock.patch.object(grportal, "fetch", return_value=rows):
            r = self.client.get("/GSM/points/", {"layer": "grportal:geochron"},
                                HTTP_ACCEPT_ENCODING="gzip")
        self.assertEqual(r["Content-Encoding"], "gzip")

    def test_상류가_못_주면_옛것을_낸다(self):
        with mock.patch.object(grportal, "fetch", return_value=[]):
            views.point_features("grportal:geochron")
        with mock.patch.object(grportal, "fetch", side_effect=grportal.PortalError("x")):
            data = views.point_features("grportal:geochron", refresh=True)
        self.assertEqual(data, b"[]")

    def test_옛것도_없으면_502(self):
        with mock.patch.object(grportal, "fetch", side_effect=grportal.PortalError("x")):
            r = self.client.get("/GSM/points/", {"layer": "grportal:geochron"})
        self.assertEqual(r.status_code, 502)

    def test_모르는_레이어는_404(self):
        r = self.client.get("/GSM/points/", {"layer": "L_50K_Geology_Map"})
        self.assertEqual(r.status_code, 404)


class Seed(TestCase):
    def test_씨앗이_그린란드에_점_레이어를_넣는다(self):
        call_command("seed_catalog", stdout=mock.Mock())
        layer = Layer.objects.get(name="grportal:samples")
        self.assertEqual(layer.upstream, "grportal")
        self.assertEqual(layer.group.region, "greenland")
        self.assertEqual(layer.group.name, "시료·연대 (정부 포털)")
