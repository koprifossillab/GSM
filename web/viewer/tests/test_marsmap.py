"""화성 옛 지질도 — 우리가 굽는 파일 (devlog 068).

원본(20 MB)을 시험에 들고 오지 않는다. 굽는 표와 같은 꼴의 작은 sqlite 를 손으로 만들어 그리기·읽기를 본다.
"""
import io
import sqlite3
import tempfile
from pathlib import Path

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from PIL import Image

from viewer import marsmap, moonmap
from viewer.tests.test_moonmap import square


def tiny_db(path, units, lines=()):
    """`units`: [(symbol, name, color, [[ring, …], …])], `lines`: [(kind, flat)]."""
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE units (id INTEGER PRIMARY KEY, map TEXT, draw INTEGER, symbol TEXT, name TEXT, color TEXT,
                            geom BLOB);
        CREATE VIRTUAL TABLE units_rtree USING rtree(id, minx, maxx, miny, maxy);
        CREATE TABLE lines (id INTEGER PRIMARY KEY, map TEXT, kind TEXT, geom BLOB);
        CREATE VIRTUAL TABLE lines_rtree USING rtree(id, minx, maxx, miny, maxy);
    """)
    for symbol, name, color, polygons in units:
        cur = db.execute("INSERT INTO units (map, draw, symbol, name, color, geom) VALUES ('I-1802',0,?,?,?,?)",
                         (symbol, name, color, moonmap.pack(polygons)))
        db.execute("INSERT INTO units_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *moonmap._bbox(polygons)))
    for kind, flat in lines:
        cur = db.execute("INSERT INTO lines (map, kind, geom) VALUES ('I-1802',?,?)", (kind, moonmap.pack([[flat]])))
        db.execute("INSERT INTO lines_rtree VALUES (?,?,?,?,?)", (cur.lastrowid, *moonmap._bbox([[flat]])))
    db.commit()
    db.close()


class Ages(SimpleTestCase):
    """시대 열이 없어 기호 앞머리에서 읽는다."""

    def test_기호_앞머리가_시대(self):
        self.assertEqual(marsmap.age_of("Api"), "Amazonian")
        self.assertEqual(marsmap.age_of("HNu"), "Hesperian and Noachian")
        self.assertEqual(marsmap.age_of("Nplh"), "Noachian")
        self.assertEqual(marsmap.age_of("cs"), "")                 # 크레이터 물질 — 여러 시대

    def test_장은_누른_자리로(self):
        self.assertEqual(marsmap.sheet_of("I-1802", -133, 18), "A")
        self.assertEqual(marsmap.sheet_of("I-1802", 137, -5), "B")
        self.assertEqual(marsmap.sheet_of("I-1802", 10, 80), "C")

    def test_색은_USGS_의_색표(self):
        self.assertEqual(marsmap.unit_color("Api"), "#ffffff")
        self.assertEqual(len(marsmap.styles()["units"]), 95)
        self.assertEqual(marsmap.line_style("Graben, undiff")["color"], "#1a1a1a")


class Drawing(TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-marsmap-")
        patch = override_settings(MARS_DIR=self.dir, TILE_CACHE_DIR=self.dir)
        patch.enable()
        self.addCleanup(patch.disable)
        tiny_db(Path(self.dir) / marsmap.FILENAME, [
            ("Aos", "Olympus Mons Formation, shield member", "#ea6132", [[square(-140, 10, -126, 26)]]),
            ("Api", "polar ice deposits", "#ffffff", [[square(-180, 80, 180, 89.9)]]),
            ("s", "impact crater material, smooth floor", "#c8c8c8", [[square(179, -1, 181, 1)]]),
        ], [("Wrinkle ridge", [-130.0, 0.0, -120.0, 5.0])])

    def test_누르면_단위와_시대(self):
        hit = marsmap.identify(-133.8, 18.4)
        self.assertEqual((hit["unit"], hit["age"], hit["map"]), ("Aos", "Amazonian", "I-1802-A"))
        self.assertIsNone(marsmap.identify(0, 0))

    def test_날짜_변경선을_넘은_단위(self):
        self.assertEqual(marsmap.identify(-179.5, 0)["unit"], "s")

    def test_경위도와_극_타일(self):
        png = marsmap.render_tile("orig-units", 1, 0, 0)          # 서경 180–90°, 북위 90–0°
        self.assertIsNotNone(Image.open(io.BytesIO(png)).getbbox())
        png = marsmap.render_tile("orig-lines", 2, 1, 1)
        self.assertIsNotNone(Image.open(io.BytesIO(png)).getbbox())
        png = marsmap.render_polar_tile("orig-units", "n", 0, 0, 0)
        img = Image.open(io.BytesIO(png)).convert("RGBA")
        self.assertEqual(img.getpixel((128, 128))[:3], (255, 255, 255))   # 극점에 극관
        self.assertIsNone(Image.open(io.BytesIO(marsmap.render_polar_tile("orig-units", "s", 0, 0, 0))).getbbox())

    def test_누르기와_범례의_길(self):
        rows = dict(self.client.get(reverse("viewer:mars-info"), {"lon": -133.8, "lat": 18.4, "layer": "orig"}).json()["rows"])
        self.assertEqual((rows["단위"], rows["시대"], rows["원도"]), ("Aos", "아마조니스기", "I-1802-A — 서쪽 적도"))
        legend = self.client.get(reverse("viewer:mars-legend"), {"layer": "orig"}).json()
        self.assertEqual({u["unit"]: u["age"] for u in legend["units"]}["s"], "")
        self.assertEqual(legend["lines"][0]["label"], "그라벤")
        r = self.client.get(reverse("viewer:mars-tile", args=["orig-units", 1, 0, 0]))
        self.assertEqual(r["X-GSM-Cache"], "miss")
        self.assertEqual(self.client.get(reverse("viewer:mars-tile", args=["orig-units", 1, 0, 0]))["X-GSM-Cache"], "hit")

    def test_파일이_없으면_안내(self):
        with override_settings(MARS_DIR=self.dir + "/none"):
            r = self.client.get(reverse("viewer:mars-polar-tile", args=["n", "orig-units", 0, 0, 0]))
            self.assertEqual(r["Cache-Control"], "no-store")
            note = self.client.get(reverse("viewer:mars-info"), {"lon": 1, "lat": 1, "layer": "orig"}).json()
            self.assertEqual(note["rows"], [])
