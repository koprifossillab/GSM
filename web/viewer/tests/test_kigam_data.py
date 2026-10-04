"""KIGAM 오픈플랫폼의 자료 — 모으기·자리·레이어 (wetherilli 169).

KIGAM·VWorld 를 실제로 부르지 않는다. 상세의 꼴은 2026-10-02 에 `/openapi/data/<id>` 로 받은 그대로다.
"""
import io
import json
import tempfile
from unittest import mock

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings

from viewer import kigam, kigamdata


def detail(i, collection, title, place, head=None, doi=None, stamp="2024-11-22T15:46:58.940+0900"):
    return {"id": i, "title": title, "collection": {"name": collection}, "license": "CC BY-NC", "doi": doi,
            "lastModified": stamp, "metadata": {"개요": head or {}, "위치정보": place},
            "bundles": [{"files": [{"name": "a.jpg"}, {"name": "b.pdf"}]}], "series": [{"id": "old"}]}


ID = "b58d44bc-dc68-431f-98bc-0a1510f836c1"
DETAILS = {
    ID: detail(ID, "GEO2", "화석(삼엽충(Trilobite)_F-138)",
               {"국가": "대한민국", "도,광역시": "강원도", "시군구": "태백시", "동,면": "장성동"},
               {"시료유형": "화석 표본", "시료 분류명": "화석", "생산기관": "미상"}),
    "2b2a21d5-ba7a-4ce5-846e-968a857c69bd": detail("2b2a21d5-ba7a-4ce5-846e-968a857c69bd", "GEO2", "호상편마암 (22Z나-10)",
                                                   {"좌표": "POINT (127.517971 37.634717)"},
                                                   {"시료유형": "암석 표본/시료", "시료 분류명": "변성암 Metamorphic rock"},
                                                   doi="10.22747/data.20201123.777"),
    "11111111-1111-1111-1111-111111111111": detail("11111111-1111-1111-1111-111111111111", "GEO2", "라타이트 반암_I-144",
                                                   {"국가": "미국", "도,광역시": "Montana"}),
    "22222222-2222-2222-2222-222222222222": detail("22222222-2222-2222-2222-222222222222", "GEO3", "수치지질도_5만축척_동두말",
                                                   {"좌표": "POLYGON ((128.750000 35.000000, 129.000000 35.000000, "
                                                            "129.000000 34.833333, 128.750000 34.833333, 128.750000 35.000000))"},
                                                   {"지도자료": "지질도", "저자": "황상구, 고경태", "발간일": "2021-12-31"}),
    "33333333-3333-3333-3333-333333333333": detail("33333333-3333-3333-3333-333333333333", "GEO3", "전국암석밀도분포도",
                                                   {"좌표": "POLYGON ((124 33, 131 33, 131 39, 124 39, 124 33))"},
                                                   {"지도자료": "지열주제도"}),
}


class Wkt(SimpleTestCase):
    def test_점은_경도_먼저(self):
        self.assertEqual(kigamdata.parse_wkt("POINT (127.084144 34.940229)"),
                         {"type": "Point", "coordinates": [127.084144, 34.940229]})

    def test_면(self):
        geom = kigamdata.parse_wkt(DETAILS["22222222-2222-2222-2222-222222222222"]["metadata"]["위치정보"]["좌표"])
        self.assertEqual(geom["type"], "Polygon")
        self.assertEqual(geom["coordinates"][0][0], [128.75, 35.0])

    def test_모르는_꼴(self):
        self.assertIsNone(kigamdata.parse_wkt("남한전체"))
        self.assertIsNone(kigamdata.parse_wkt(None))


class Places(SimpleTestCase):
    def test_행정구역_한_줄_나라_밖은_빈다(self):
        self.assertEqual(kigamdata.admin_text(kigamdata.trim(DETAILS[ID])), "강원도 태백시 장성동")
        self.assertEqual(kigamdata.admin_text(kigamdata.trim(DETAILS["11111111-1111-1111-1111-111111111111"])), "")

    def test_못_찾으면_끝_마디를_떼며(self):
        asked = []

        def geocode(text):
            asked.append(text)
            return {"lat": 37.17, "lon": 128.98} if text == "강원도 태백시" else None
        places = {}
        self.assertEqual(kigamdata.locate(places, "강원도 태백시 장성동", geocode), [37.17, 128.98])
        self.assertEqual(asked, ["강원도 태백시 장성동", "강원도 태백시"])
        kigamdata.locate(places, "강원도 태백시 장성동", geocode)              # 담아 둔 것 — 다시 묻지 않는다
        self.assertEqual(len(asked), 2)


class Harvest(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-kigamdata-")
        patch = override_settings(KIGAM_DATA_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)

    def lists(self, stamps):
        return lambda page: {"totalPages": 1, "content": [{"id": i, "lastModified": s} for i, s in stamps.items()]}

    def test_처음은_다_다음은_바뀐_것만(self):
        stamps = {i: d["lastModified"] for i, d in DETAILS.items()}
        with mock.patch.object(kigam, "data_list", side_effect=self.lists(stamps)), \
             mock.patch.object(kigam, "data_detail", side_effect=lambda i: DETAILS[i]) as got:
            first = kigamdata.harvest(log=lambda *_: None, pause=0)
            self.assertEqual((first["listed"], first["fetched"]), (5, 5))
            stamps[ID] = "2026-10-02T00:00:00.000+0900"
            del stamps["33333333-3333-3333-3333-333333333333"]
            second = kigamdata.harvest(log=lambda *_: None, pause=0)
        self.assertEqual((second["fetched"], second["gone"]), (1, 1))
        self.assertEqual(got.call_count, 6)
        item = kigamdata.load()["items"][ID]
        self.assertEqual(item["files"], 2)
        self.assertNotIn("series", item)

    def test_1_초보다_잦게는_묻지_않는다(self):
        with self.assertRaises(CommandError):
            call_command("fetch_kigam_data", pause=0.5, stdout=io.StringIO())


class Layers(SimpleTestCase):
    def setUp(self):
        self.data = {"items": {i: kigamdata.trim(d) for i, d in DETAILS.items()}}
        self.places = {"강원도 태백시 장성동": [37.17, 128.98]}

    def test_시료_좌표와_행정구역_가운데(self):
        feats, wide = kigamdata.features("kigam_data:samples", self.data, self.places)
        codes = {f["properties"]["title"]: f["properties"]["code"] for f in feats}
        self.assertEqual(codes, {"화석(삼엽충(Trilobite)_F-138)": "approx", "호상편마암 (22Z나-10)": "rock"})
        rock = next(f for f in feats if f["properties"]["code"] == "rock")
        self.assertEqual(rock["properties"]["doi"], "https://doi.org/10.22747/data.20201123.777")
        self.assertTrue(rock["properties"]["page"].startswith("https://data.kigam.re.kr/data/"))
        fossil = next(f for f in feats if f["properties"]["code"] == "approx")
        self.assertEqual(fossil["geometry"]["coordinates"], [128.98, 37.17])
        self.assertNotIn("maker", fossil["properties"])                    # "미상" 은 싣지 않는다

    def test_주제도는_면_넓은_것은_뺀다(self):
        feats, wide = kigamdata.features("kigam_data:maps", self.data, self.places)
        self.assertEqual([f["properties"]["code"] for f in feats], ["geology"])
        self.assertEqual(wide, 1)

    def test_범례_이름은_영어가_있다(self):
        from viewer import i18n
        for name in kigamdata.LAYERS:
            for _, label, _, _ in kigamdata.classes(name):
                self.assertIn(label, {**i18n.EN, **i18n.PROP_EN}, label)
        for label in kigamdata.LABELS.values():
            self.assertIn(label, {**i18n.EN, **i18n.PROP_EN}, label)


class View(TestCase):
    def setUp(self):
        from django.core.management import call_command as cc
        cc("seed_catalog", stdout=io.StringIO())
        self.dir = tempfile.mkdtemp(prefix="gsm-kigamdata-v-")
        patch = override_settings(KIGAM_DATA_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)

    def test_모으기_전에는_까닭을(self):
        r = self.client.get("/GSM/points/", {"layer": "kigam_data:samples"})
        self.assertEqual(r.status_code, 503)

    def test_모은_것을_덩이로(self):
        kigamdata.save({"items": {i: kigamdata.trim(d) for i, d in DETAILS.items()}, "harvested": "2026-10-02 16:00"})
        kigamdata.save({"강원도 태백시 장성동": [37.17, 128.98]}, kigamdata.PLACES_FILE)
        body = self.client.get("/GSM/points/", {"layer": "kigam_data:samples"}).json()
        self.assertEqual(body["style"], "class")
        self.assertEqual({r["code"] for r in body["legend"]}, {"rock", "approx"})
        self.assertIn("page", body["links"])

    def test_목록에_선다(self):
        html = self.client.get("/GSM/map/").content.decode()
        self.assertIn("kigam_data:samples", html)


class Door(SimpleTestCase):
    @override_settings(KIGAM_KEY="비밀-키")
    def test_키는_로그에_남지_않는다(self):
        answer = mock.MagicMock(status_code=200, url="https://data.kigam.re.kr/openapi/data?page=0&size=100&key=비밀-키",
                                content=b"{}")
        answer.json.return_value = {"response": {"totalPages": 1, "content": []}}
        with mock.patch.object(kigam.requests, "get", return_value=answer) as get, \
             mock.patch.object(kigam.usage, "record"), self.assertLogs("viewer.kigam", "INFO") as logs:
            kigam.data_list(0)
        self.assertEqual(get.call_args.kwargs["params"]["key"], "비밀-키")
        self.assertNotIn("비밀-키", "\n".join(logs.output))

    def test_자료_번호의_꼴(self):
        with self.assertRaises(kigam.UpstreamError):
            kigam.data_detail("../../etc")
