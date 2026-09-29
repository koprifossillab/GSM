"""극지연구소 — 암석 시료·KPDC 자료·운석·기지·해안선 (053–057).

상류를 부르지 않는다. 받은 쪽(HTML·JSON)을 흉내 내 읽는 틀과, 모아 둔 파일을 화면에 내는 길을 본다.
"""
import json
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase, TestCase, override_settings

from viewer import kopri
from viewer.models import Layer, LayerGroup

ROCK_PAGE = """<table><tbody>
 <tr><td class="active"><a href='/rock/0714'>0714</a></td><td>2020-01-01</td><td>Antarctica Victoria Land</td>
 <td>plutonic</td><td></td><td>Cambrian</td><td>-74.4773,165.3399</td> </tr>
 <tr><td class="active"><a href='/rock/073001'>073001</a></td><td>2014-07-30</td><td>Arctic areas Svalbard</td>
 <td>Sedimentary</td><td>Wordiekammen Fm.</td><td>Carboniferous</td><td>78.65,16.4</td> </tr>
 <tr><td class="active"><a href='/rock/9'>9</a></td><td></td><td></td><td>IGNEOUS</td><td></td><td></td><td>0,0</td></tr>
</tbody></table>"""

LIST_PAGE = """<tbody>
<tr class="item result-item" data-id="55e44fc3-7bf0-487b-b1cb-cdf5b5850af4"
    data-title="Box Core &amp; more" data-coord="[[1,2]]">
 <td>1</td><td class="lt_title"><a href="/search/55e44fc3-7bf0-487b-b1cb-cdf5b5850af4">
 <span class="entry_id">[KOPRI-KPDC-00003172]</span>Box Core</a></td></tr>
</tbody>"""

DETAIL_PAGE = """
<dl><dt>Entry ID</dt><dd>KOPRI-KPDC-00003172</dd></dl>
<dl><dt>DOI</dt><dd>https://dx.doi.org/doi:10.22663/KOPRI-KPDC-00003172</dd></dl>
<dl><dt>Science Keyword</dt><dd>EARTH SCIENCE        &gt; OCEANS    &gt; MARINE SEDIMENTS  &gt; SEDIMENTATION</dd></dl>
<dl><dt>Research period</dt><dd>2019-01-01 ~ 2019-01-31</dd></dl>
<dl><dt>Location</dt><dd>OCEAN   &gt; SOUTHERN OCEAN  &gt; ROSS SEA   </dd></dl>
<dl class="dview_map_list"><dt>Spatial Coverage</dt><dd>
 <div class="point-block"><p class="point-header">POINT</p><ul class="point-list">
  <li><span class="text-muted">lat:</span>-75.088668, <span class="text-muted">lon:</span>-165.056272</li>
 </ul></div>
 <div class="point-block"><p class="point-header">POLYGON</p><ul class="point-list">
  <li><span class="text-muted">lat:</span>-72.0, <span class="text-muted">lon:</span>150.0</li>
  <li><span class="text-muted">lat:</span>-77.0, <span class="text-muted">lon:</span>170.0</li>
 </ul></div>
</dd></dl>
<dd><a href="https://koreamet.kopri.re.kr/db/178" target="_blank">x</a></dd>
"""


class Parse(SimpleTestCase):
    def test_암석_목록(self):
        rows = kopri.parse_rock_page(ROCK_PAGE)
        self.assertEqual([r["sample"] for r in rows], ["0714", "073001", "9"])
        self.assertEqual(rows[1]["strat"], "Wordiekammen Fm.")
        self.assertEqual(kopri.rock_coord(rows[0]["coord"]), (-74.4773, 165.3399))
        self.assertIsNone(kopri.rock_coord(rows[2]["coord"]))      # 0,0 은 좌표가 없는 것

    def test_암석_갈래는_접어서(self):
        self.assertEqual(kopri.rock_class("IGNEOUS"), "plutonic")
        self.assertEqual(kopri.rock_class("Sediment"), "sedimentary")
        self.assertEqual(kopri.rock_class(""), "other")

    def test_마지막_장을_되풀이하면_멈춘다(self):
        pages = []

        def fake(url, params=None, **kw):
            pages.append(params["page"])
            return mock.Mock(text=ROCK_PAGE)                       # 상류는 늘 같은 장을 준다
        with mock.patch.object(kopri, "_get", fake):
            rows = kopri.harvest_rock(pause=0)
        self.assertEqual(len(rows), 3)
        self.assertEqual(pages, [0, 1])

    def test_목록(self):
        self.assertEqual(kopri.parse_list_page(LIST_PAGE), [{
            "uuid": "55e44fc3-7bf0-487b-b1cb-cdf5b5850af4", "id": "KOPRI-KPDC-00003172", "title": "Box Core & more"}])

    def test_상세(self):
        d = kopri.parse_detail(DETAIL_PAGE)
        self.assertEqual(d["keywords"], ["EARTH SCIENCE > OCEANS > MARINE SEDIMENTS > SEDIMENTATION"])
        self.assertEqual(d["location"], ["OCEAN > SOUTHERN OCEAN > ROSS SEA"])
        self.assertEqual(d["period"], "2019-01-01 ~ 2019-01-31")
        self.assertEqual(d["shapes"], [["POINT", [(-75.088668, -165.056272)]],
                                       ["POLYGON", [(-72.0, 150.0), (-77.0, 170.0)]]])
        self.assertEqual(d["link"], "https://koreamet.kopri.re.kr/db/178")


class Shapes(SimpleTestCase):
    def test_주제(self):
        self.assertEqual(kopri.topic_of(["EARTH SCIENCE > OCEANS > MARINE SEDIMENTS > X"]), "sediment")
        self.assertEqual(kopri.topic_of(["EARTH SCIENCE > OCEANS > SALINITY"]), "ocean")
        self.assertEqual(kopri.topic_of(["Earth Science > Solid Earth > Rocks"]), "solid")
        self.assertEqual(kopri.topic_of([]), "other")

    def test_모서리_둘은_위선을_따라_휜_네모(self):
        g = kopri._shape_geometry("POLYGON", [(-72.0, 150.0), (-77.0, 170.0)])
        ring = g["coordinates"][0]
        self.assertEqual(ring[0], ring[-1])
        self.assertGreater(len(ring), 20)                         # 네 점이 아니다
        self.assertTrue(all(150 <= x <= 170 and -77 <= y <= -72 for x, y in ring))

    def test_날짜변경선을_넘는_네모(self):
        ring = kopri._shape_geometry("POLYGON", [(-72.0, 170.0), (-75.0, -170.0)])["coordinates"][0]
        self.assertTrue(all(x >= 170 or x <= -170 for x, _ in ring))

    def test_넓은_범위는_그리지_않는다(self):
        self.assertIsNone(kopri._shape_geometry("POLYGON", [(-85.0, 0.5), (-60.0, 180.0)]))
        self.assertEqual(kopri._shape_geometry("POINT", [(-85.0, 0.5), (-60.0, 180.0)])["type"], "MultiPoint")

    def test_기지(self):
        row = kopri._station({"geometry": {"type": "Point", "coordinates": [164.2008, -74.6153]},
                              "properties": {"facility_n": "Jang Bogo", "nationa_01": "KOR",
                                             "current_st": "Year-round", "notes": None}})
        self.assertEqual(row["properties"]["code"], "korea")
        self.assertNotIn("notes", row["properties"])
        row = kopri._station({"geometry": {"type": "Point", "coordinates": [0, -70]},
                              "properties": {"facility_n": "X", "current_st": "Seasonal"}})
        self.assertEqual(row["properties"]["code"], "season")


class Files(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.enterContext(override_settings(KOPRI_DIR=self.dir.name))
        kopri.save("rock", {"rows": kopri.parse_rock_page(ROCK_PAGE)})
        detail = kopri.parse_detail(DETAIL_PAGE)
        kopri.save("kpdc", {"records": {
            "u1": dict(detail, c="KPDC", id="KOPRI-KPDC-1", title="Box core"),
            "u2": dict(detail, c="KPDC", keywords=["EARTH SCIENCE > ATMOSPHERE > X"],
                       shapes=[["POLYGON", [(-85.0, 0.5), (-60.0, 180.0)]]]),
            "u3": dict(detail, c="KoreaMet", title="Thiel Mountains 06004",
                       shapes=[["POINT", [(-85.1572, -94.5418)]]]),
        }})

    def test_암석은_지역마다_갈라_싣는다(self):
        south = json.loads(kopri.file_body("kopri:rock_antarctica"))
        north = json.loads(kopri.file_body("kopri:rock_svalbard"))
        self.assertEqual([f["id"] for f in south["features"]], ["0714"])
        self.assertEqual([f["id"] for f in north["features"]], ["073001"])
        self.assertEqual(south["style"], "class")
        self.assertEqual(south["features"][0]["properties"]["age"], "캄브리아기")
        en = json.loads(kopri.file_body("kopri:rock_antarctica", "en"))
        self.assertEqual(en["features"][0]["properties"]["age"], "Cambrian")

    def test_KPDC_는_주제마다(self):
        sed = json.loads(kopri.file_body("kopri:kpdc_sediment"))
        self.assertEqual(sorted(f["geometry"]["type"] for f in sed["features"]), ["Point", "Polygon"])
        props = sed["features"][0]["properties"]
        self.assertEqual(props["page"], "https://kpdc.kopri.re.kr/search/u1")
        self.assertIn("page", sed["links"])
        atmo = json.loads(kopri.file_body("kopri:kpdc_atmo"))
        self.assertEqual((len(atmo["features"]), atmo["wide"]), (0, 1))

    def test_운석(self):
        met = json.loads(kopri.file_body("kopri:meteorites"))
        self.assertEqual(len(met["features"]), 1)
        self.assertEqual(met["features"][0]["properties"]["db"], "https://koreamet.kopri.re.kr/db/178")
        self.assertEqual(met["legend"][0]["count"], 1)


class View(TestCase):
    def setUp(self):
        group = LayerGroup.objects.create(name="극지연구소 시료", region="antarctica")
        Layer.objects.create(name="kopri:rock_antarctica", title="암석 시료", group=group, upstream="kopri")
        Layer.objects.create(name="kopri:coast_change", title="해안선 변화", group=group, upstream="kopri")

    def test_모으지_않았으면_503(self):
        with tempfile.TemporaryDirectory() as d, override_settings(KOPRI_DIR=d):
            r = self.client.get("/GSM/points/?layer=kopri:rock_antarctica")
        self.assertEqual(r.status_code, 503)
        self.assertIn("fetch_kopri", r.json()["error"])

    def test_모아_둔_것을_낸다(self):
        with tempfile.TemporaryDirectory() as d, override_settings(KOPRI_DIR=d):
            kopri.save("rock", {"rows": kopri.parse_rock_page(ROCK_PAGE)})
            r = self.client.get("/GSM/points/?layer=kopri:rock_antarctica")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(json.loads(r.content)["features"]), 1)

    def test_카탈로그(self):
        rows = {l["name"]: l for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]}
        self.assertEqual(rows["kopri:rock_antarctica"]["kind"], "points")
        self.assertEqual(rows["kopri:rock_antarctica"]["style"], "class")
        self.assertEqual(rows["kopri:coast_change"]["projection"], "EPSG:3031")

    def test_밖에_열면_내린다(self):
        with override_settings(PUBLIC=True):
            names = [l["name"] for g in self.client.get("/GSM/catalog/").json()["groups"] for l in g["layers"]]
            self.assertNotIn("kopri:rock_antarctica", names)
            self.assertEqual(self.client.get("/GSM/points/?layer=kopri:rock_antarctica").status_code, 404)

    def test_WMS_는_레이어명만_바꿔_넘긴다(self):
        sent = {}

        def fake(url, params=None, **kw):
            sent.update(params, url=url)
            return mock.Mock(content=b"\x89PNG", headers={"content-type": "image/png"})
        with mock.patch.object(kopri, "_get", fake), override_settings(TILE_CACHE_DIR=tempfile.mkdtemp()):
            r = self.client.get("/GSM/wms/", {"layers": "kopri:coast_change", "bbox": "0,0,1,1", "width": 256,
                                              "height": 256, "srs": "EPSG:3031", "request": "GetMap"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(sent["layers"], "kpdc:antarctic_coastline_coast_change")
        self.assertTrue(sent["url"].endswith("/geoserver/kpdc/wms"))
