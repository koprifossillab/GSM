"""다누리 KMAG 궤적 (wetherilli 377) — KPDS 의 문과 줄여 담은 sqlite."""
import io
import tempfile
import zipfile

import json
from datetime import timedelta
from unittest import mock
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings

from viewer import kmag, kpds

URL = "https://kpds.test/kpds"
HEAD = "UTC,X_SEL,Y_SEL,Z_SEL,Bx_SEL,By_SEL,Bz_SEL,X_SSE,Y_SSE,Z_SSE,Bx_SSE,By_SSE,Bz_SSE\n"


def day_csv(start="2025-03-31T00:00:00", n=40):
    """적도 위 고도 60 km 를 동쪽으로 도는 궤도 — 4 초마다 0.05°."""
    import math
    from datetime import datetime, timedelta
    t0 = datetime.fromisoformat(start)
    lines = [HEAD]
    for k in range(n):
        lon = math.radians(10 + 0.05 * k)
        r = kmag.RADIUS + 60
        b = "-99999,-99999,-99999" if k == 8 else "3,4,0"
        lines.append(f"{(t0 + timedelta(seconds=4 * k)).isoformat()}.000,{r * math.cos(lon):.2f},{r * math.sin(lon):.2f},0,"
                     f"{b},0,0,0,0,0,0\n")
    return "".join(lines)


class Parse(SimpleTestCase):
    def test_32_초마다_한_점(self):
        pts = kmag.parse(day_csv())
        self.assertEqual(len(pts), 5)                              # 40 행 × 4 초 = 160 초
        sec, lon, lat, alt, b = pts[0]
        self.assertAlmostEqual(lon, 10.0, places=3)
        self.assertAlmostEqual(lat, 0.0, places=3)
        self.assertAlmostEqual(alt, 60.0, places=1)
        self.assertEqual(b, 5.0)
        self.assertIsNone(pts[1][4])                               # 빈 값은 |B| 만 비운다

    def test_달에서_먼_자리는_버린다(self):
        far = HEAD + "2022-09-02T00:00:00.000,300000,0,0,1,1,1,0,0,0,0,0,0\n"
        self.assertEqual(kmag.parse(far), [])


class Store(SimpleTestCase):
    def setUp(self):
        patch = override_settings(KPDS_DIR=tempfile.mkdtemp(prefix="gsm-kmag-"))
        patch.enable()
        self.addCleanup(patch.disable)

    def test_없으면_비었다(self):
        self.assertFalse(kmag.available())
        self.assertEqual(kmag.tracks(-180, -90, 180, 90), [])
        self.assertIsNone(kmag.nearest(0, 0))
        self.assertEqual(kmag.stamp(), "")

    def test_더하고_읽는다(self):
        conn = kmag.connect(write=True)
        self.assertEqual(kmag.add_day(conn, "A", kmag.parse(day_csv())), 5)
        self.assertEqual(kmag.add_day(conn, "A", kmag.parse(day_csv())), 0)      # 같은 날은 한 번만
        kmag.add_day(conn, "B", kmag.parse(day_csv("2025-03-31T01:00:00")))
        conn.close()
        lines = kmag.tracks(0, -5, 20, 5)
        self.assertEqual(len(lines), 2)                            # 한 시간 벌어진 두 궤적은 잇지 않는다
        hit = kmag.nearest(10.05, 0.01)
        self.assertEqual(hit["b"], 5.0)
        self.assertEqual(hit["alt"], 60.0)
        self.assertTrue(hit["time"].startswith("2025-03-31 00:00:"))
        self.assertIsNone(kmag.nearest(100, 50))
        self.assertEqual(kmag.summary()["days"], 2)


class Answer:
    def __init__(self, body):
        self.content = body if isinstance(body, bytes) else json.dumps(body).encode() if not isinstance(body, str) else body.encode()
        self.status_code = 200
        self.elapsed = timedelta(seconds=0.1)

    def json(self):
        return json.loads(self.content)


def fake_kpds(listing, files):
    """KPDS 를 흉내 낸다 — 부른 것을 `calls` 에 적는다."""
    calls = []

    def request(self, method, url, **kw):
        calls.append((method, url, kw))
        if url.endswith("/search_view/levelproduct"):
            return Answer("ok")
        if url.endswith("/search/dataTableList"):
            return Answer(listing)
        name = url.rsplit("/", 1)[-1]
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for fname, body in files[name].items():
                z.writestr(fname, body)
        return Answer(buf.getvalue())
    return calls, mock.patch.object(kpds.requests.Session, "request", request)


@override_settings(KPDS_URL=URL)
class Door(SimpleTestCase):
    def test_목록은_썸네일을_버리고_내려받기는_zip_을_푼다(self):
        listing = {"recordsFiltered": 1, "data": [
            {"_id": ["7"], "identifierS": "urn:kari:kpds:kplo.kmag:data.cal:x", "metaFileName": ["X_CAL_M_01.xml"],
             "startDate": ["2025-03-31T00:00:00Z"], "allFileSize": [10], "imgSrc": "data:image/png;base64,AAAA"}]}
        calls, patch = fake_kpds(listing, {"X_CAL_M_01": {"X_CAL_M_01.csv": "a,b\n"}})
        with patch:
            s = kpds.session()
            total, rows = kpds.search(s, "kmag", "Calibrated")
            got = kpds.download(s, "X_CAL_M_01.xml")
        self.assertEqual(total, 1)
        self.assertEqual(rows[0]["meta"], "X_CAL_M_01.xml")
        self.assertNotIn("imgSrc", rows[0])
        self.assertEqual(calls[1][2]["data"]["param[processing_level_ss]"], "(Calibrated)")
        self.assertEqual(calls[1][2]["data"]["param[_txt]"], "(*kmag*)")
        self.assertEqual(got, {"X_CAL_M_01.csv": b"a,b\n"})

    def test_명령은_새_날만_받는다(self):
        listing = {"recordsFiltered": 1, "data": [{"_id": ["7"], "metaFileName": ["D1_CAL_M_01.xml"]}]}
        calls, patch = fake_kpds(listing, {"D1_CAL_M_01": {"D1_CAL_M_01.csv": day_csv()}})
        with patch, override_settings(KPDS_DIR=tempfile.mkdtemp(prefix="gsm-kmag-")):
            call_command("fetch_kmag", stdout=io.StringIO())
            call_command("fetch_kmag", stdout=io.StringIO())
            self.assertEqual(kmag.summary()["points"], 5)
        self.assertEqual(len([c for c in calls if "/download/" in c[1]]), 1)
