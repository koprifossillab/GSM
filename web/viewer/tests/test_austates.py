"""호주의 주 판 — 퀸즐랜드 GSQ·빅토리아 GSV·남호주 GSSA (wetherilli 225). 상류를 부르지 않는다.

속성·범례의 꼴은 2026-10-04 에 받은 그대로다(브리즈번 둘레의 identify, 멜버른 서쪽·애들레이드 둘레의 GetFeatureInfo JSON, 빅토리아의
`hideEmptyRules` 범례).
"""
import io
import tempfile
from unittest import mock

from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from viewer import austates
from viewer.models import Layer

QLD = {"Rock Unit Key (Surface)": "217", "Rock Unit Name": "Bunya Phyllite", "Map Symbol": "DCy",
       "Lithological Summary": "Slate, phyllite, arenite, metabasalt", "Dominant Rock": "PELITE",
       "Rock Type": "STRATIFIED UNIT (INCLUDING VOLCANIC AND METAMORPHIC)", "Age": "DEVONIAN - CARBONIFEROUS",
       "Rock Unit Key (Solid)": "-999", "OBJECTID": "124344"}
VIC = {"name": "Castlemaine Group - Bendigonian( Ocb): generic", "description": "Sandstone, mudstone, black shale",
       "rank": "Formation [biostratigraphic]", "lithology": " mudstone (significant); shale (significant)",
       "geologichistory": "Bendigonian to Bendigonian (water [process] - hemipelagic)",
       "representativeage_uri": "http://resource.geosciml.org/classifier/ics/ischart/LowerOrdovician",
       "representativelowerage_uri": "http://resource.geosciml.org/classifier/ics/ischart/LowerOrdovician",
       "representativeupperage_uri": "http://resource.geosciml.org/classifier/ics/ischart/LowerOrdovician"}
SA = {"name": "Pleistocene calcrete", "description": "Undifferentiated Pleistocene calcrete.", "rank": "palaeosol",
      "lithology": "calcareous carbonate sedimentary material", "geologicHistory": "Unnamed event",
      "numericOlderAge": 1.66, "numericYoungerAge": 0.011,
      "representativeOlderAge_uri": "http://resource.geosciml.org/classifier/ics/ischart/Pleistocene",
      "representativeYoungerAge_uri": "http://resource.geosciml.org/classifier/ics/ischart/Pleistocene"}
LEGEND = {"Legend": [{"layerName": "sg_geological_unit_250k", "rules": [
    {"name": "Bullengarook Gravel (Nxu)", "title": "Bullengarook Gravel (Nxu) (1)",
     "symbolizers": [{"Polygon": {"fill": "#FEEF00"}}]},
    {"name": "Bacchus Marsh Formation (Pxb)", "title": "Bacchus Marsh Formation (Pxb) (17)",
     "symbolizers": [{"Polygon": {"fill": "#92D0FE", "fill-opacity": "1.0"}}]},
    {"name": "", "title": "(3)", "symbolizers": [{"Polygon": {"fill": "#FFFFFF"}}]},
]}]}
MERC = {"crs": "EPSG:3857", "bbox": "17000000,-3200000,17040000,-3160000", "width": 256, "height": 256}


def answer(**kw):
    defaults = dict(status_code=200, content=b"\x89PNG", url="…", headers={"content-type": "image/png"})
    defaults.update(kw)
    return mock.Mock(**defaults)


class Friendly(SimpleTestCase):
    def test_퀸즐랜드(self):
        got = austates.gsq_friendly(QLD)
        self.assertEqual(got, {"기호": "DCy", "이름": "Bunya Phyllite", "암석": "Slate, phyllite, arenite, metabasalt",
                               "주 암석": "Pelite", "갈래": "Stratified unit (including volcanic and metamorphic)",
                               "지질시대": "데본기~석탄기"})
        self.assertEqual(austates.gsq_friendly(QLD, "en")["지질시대"], "Devonian - Carboniferous")

    def test_빅토리아는_ICS_주소에서_시대를(self):
        got = austates.gs_friendly(VIC)
        self.assertEqual(got["지질시대"], "오르도비스기 전기")                    # LowerOrdovician → Early Ordovician
        self.assertEqual(got["암석"], "mudstone (significant); shale (significant)")
        self.assertEqual(got["위계"], "Formation [biostratigraphic]")

    def test_남호주는_낙타_꼴_열과_숫자_연대(self):
        got = austates.gs_friendly(SA)
        self.assertEqual((got["이름"], got["지질시대"], got["연대 (Ma)"]), ("Pleistocene calcrete", "플라이스토세", "0.011–1.66"))

    def test_ICS_주소의_꼬리(self):
        self.assertEqual(austates.age_of_uri("http://x/ischart/UpperDevonian"), "Late Devonian")
        self.assertEqual(austates.age_of_uri("http://x/ischart/Pleistocene"), "Pleistocene")
        self.assertEqual(austates.age_of_uri(""), "")


class Views(TestCase):
    def setUp(self):
        patch = override_settings(TILE_CACHE_DIR=tempfile.mkdtemp(prefix="gsm-austates-"))
        patch.enable()
        self.addCleanup(patch.disable)
        call_command("seed_catalog", stdout=io.StringIO())
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(austates.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)
        self.layers = {l["name"]: l for g in self.client.get(reverse("viewer:catalog")).json()["groups"]
                       for l in g["layers"]}

    def test_씨앗과_지역(self):
        for name, upstream in (("gsq:state", "gsq"), ("gsv:250k", "gsv"), ("gssa:units", "gssa")):
            layer = Layer.objects.get(name=name)
            self.assertEqual((layer.group.region, layer.upstream), ("australia", upstream))
        self.assertEqual(self.layers["gsq:detailed"]["minZoom"], 9)
        self.assertNotIn("minZoom", self.layers["gsq:state"])
        self.assertEqual((self.layers["gsv:250k"]["legend"], self.layers["gsv:250k"]["legendUrl"]), ("extent", "gsv/legend/"))
        self.assertIs(self.layers["gssa:units"]["noLegend"], True)
        self.assertIn("CC BY 4.0", self.layers["gssa:units"]["attribution"])

    def test_퀸즐랜드는_REST_export(self):
        with mock.patch.object(austates.requests, "get", return_value=answer()) as get:
            r = self.client.get(reverse("viewer:wms"), {"layers": "gsq:detailed", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(get.call_args.args[0].endswith("/GeologyDetailed/MapServer/export"))
        sent = get.call_args.kwargs["params"]
        self.assertEqual((sent["layers"], sent["bboxSR"], sent["size"]), ("show:15", 3857, "256,256"))

    def test_퀸즐랜드_속성은_identify(self):
        body = {"results": [{"layerId": 15, "attributes": QLD}]}
        with mock.patch.object(austates.requests, "get", return_value=answer(json=lambda: body)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "gsq:detailed", "query_layers": "gsq:detailed", "i": 128, "j": 128, "request": "GetFeatureInfo",
                **MERC}).json()
        self.assertTrue(get.call_args.args[0].endswith("/identify"))
        self.assertEqual(data["features"][0]["props"]["이름"], "Bunya Phyllite")

    def test_빅토리아_남호주는_GeoServer_에_열만(self):
        body = {"type": "FeatureCollection", "features": [{"type": "Feature", "id": "x", "properties": SA}]}
        with mock.patch.object(austates.requests, "get", return_value=answer(json=lambda: body)) as get:
            data = self.client.get(reverse("viewer:featureinfo"), {
                "layers": "gssa:units", "query_layers": "gssa:units", "i": 128, "j": 128, "request": "GetFeatureInfo",
                **MERC}).json()
        sent = get.call_args.kwargs["params"]
        self.assertEqual((get.call_args.args[0], sent["query_layers"]),
                         ("https://sarigdata.pir.sa.gov.au/geoserver/ows", "gsmlp:GeologicUnitView"))
        self.assertIn("numericOlderAge", sent["propertyName"])
        self.assertEqual(data["features"][0]["props"]["지질시대"], "플라이스토세")
        with mock.patch.object(austates.requests, "get", return_value=answer()) as get:
            self.client.get(reverse("viewer:wms"), {"layers": "gsv:50k", "version": "1.3.0", "request": "GetMap", **MERC})
        self.assertEqual(get.call_args.kwargs["params"]["layers"], "open-data-platform:sg_geological_unit_50k")

    def test_빅토리아_범례는_보는_범위의_칸(self):
        with mock.patch.object(austates.requests, "get", return_value=answer(json=lambda: LEGEND)) as get:
            first = self.client.get(reverse("viewer:gsv-legend"), {"layer": "gsv:250k", "bbox": "144.1,-37.7,144.5,-37.3"}).json()
            self.client.get(reverse("viewer:gsv-legend"), {"layer": "gsv:250k", "bbox": "144.1,-37.7,144.5,-37.3"})
        get.assert_called_once()                                                  # 두 번째는 담아 둔 것
        self.assertEqual(get.call_args.kwargs["params"]["legend_options"], "countMatched:true;hideEmptyRules:true")
        self.assertEqual([(r["lithology"], r["color"]) for r in first["rows"]],
                         [("Bacchus Marsh Formation (Pxb)", "#92D0FE"), ("Bullengarook Gravel (Nxu)", "#FEEF00")])
        wide = self.client.get(reverse("viewer:gsv-legend"), {"layer": "gsv:250k", "bbox": "141,-39,150,-34"})
        self.assertEqual(wide.status_code, 422)
        self.assertEqual(self.client.get(reverse("viewer:gsv-legend"), {"layer": "gssa:units", "bbox": "1,1,2,2"}).status_code, 400)
