"""시료 고도 (P03, devlog 031) — 표고 타일에서 점마다 고도를 읽는다.

망 없이 돈다. 상류는 합성 타일과 가짜 PGC 로 바꾼다.
"""
import io
import json
from unittest import mock

from django.test import SimpleTestCase, TestCase
from PIL import Image

from viewer import elevation, pointsets
from viewer.models import Point, PointSet, PointSetDeletion


def png(color):
    buf = io.BytesIO()
    Image.new("RGB", (256, 256), color).save(buf, "PNG")
    return buf.getvalue()


def terrarium_color(meters):
    v = meters + 32768
    r, rem = divmod(v, 256)
    g = int(rem)
    return (int(r), g, int(round((rem - g) * 256)))


class Decode(SimpleTestCase):
    def test_Terrarium(self):
        self.assertAlmostEqual(elevation.terrarium_value(terrarium_color(1708.5)), 1708.5, places=2)
        self.assertEqual(elevation.terrarium_value((128, 0, 0)), 0)

    def test_국토지리원(self):
        self.assertAlmostEqual(elevation.gsi_value((0, 0x93, 0x5A)), 377.22, places=2)
        self.assertIsNone(elevation.gsi_value((128, 0, 0)))                 # 자료 없음
        self.assertAlmostEqual(elevation.gsi_value((255, 255, 255)), -0.01)  # 2^24 − 1 → −1 cm

    def test_일본_경계(self):
        self.assertTrue(elevation.in_japan(35.36, 138.73))      # 후지산
        self.assertTrue(elevation.in_japan(34.4, 129.3))        # 쓰시마
        self.assertFalse(elevation.in_japan(35.1, 129.05))      # 부산
        self.assertFalse(elevation.in_japan(37.24, 131.87))     # 독도
        self.assertFalse(elevation.in_japan(37.5, 127.0))       # 서울


class Choose(SimpleTestCase):
    """점마다 출처를 고른다 — 극지는 PGC, 일본은 국토지리원, 나머지는 AWS."""

    def run_with(self, gsi=None, pgc=3210.3):
        aws = png(terrarium_color(1000.0))
        with mock.patch.object(elevation, "terrarium_tile", return_value=aws) as t, \
                mock.patch.object(elevation, "gsi_tile", return_value=gsi) as g, \
                mock.patch.object(elevation, "pgc_value", return_value=pgc) as p:
            got = elevation.elevations({"seoul": (37.5, 127.0), "fuji": (35.36, 138.73),
                                        "summit": (72.58, -38.46)}, pause=0)
        return got, t, g, p

    def test_출처를_고른다(self):
        gsi = png((0, 0x93, 0x5A))                             # 377.22 m
        got, _, _, p = self.run_with(gsi=gsi)
        self.assertEqual(got["summit"], (3210.3, "pgc-arcticdem-2m"))
        self.assertAlmostEqual(got["fuji"][0], 377.22, places=2)
        self.assertEqual(got["fuji"][1], "gsi-dem-10m")
        self.assertAlmostEqual(got["seoul"][0], 1000.0, places=1)
        self.assertEqual(got["seoul"][1], "aws-terrarium-z12")
        p.assert_called_once_with(72.58, -38.46)                 # 극지만 PGC 에 묻는다

    def test_못_주면_AWS_로_넘어간다(self):
        got, _, _, _ = self.run_with(gsi=None, pgc=None)
        self.assertEqual({k: v[1] for k, v in got.items()},
                         {k: "aws-terrarium-z12" for k in ("seoul", "fuji", "summit")})

    def test_타일은_한_번만_받는다(self):
        aws = png(terrarium_color(5.0))
        with mock.patch.object(elevation, "terrarium_tile", return_value=aws) as t:
            elevation.elevations({i: (37.5 + i * 1e-5, 127.0) for i in range(50)}, pause=0)
        self.assertEqual(t.call_count, 1)


class JapanTerrarium(SimpleTestCase):
    def test_빈_칸은_AWS_로_메운다(self):
        gsi = Image.new("RGB", (256, 256), (0, 0x93, 0x5A))
        gsi.putpixel((0, 0), (128, 0, 0))
        buf = io.BytesIO()
        gsi.save(buf, "PNG")
        aws = png(terrarium_color(-12.0))
        with mock.patch.object(elevation, "gsi_tile", return_value=buf.getvalue()), \
                mock.patch.object(elevation, "terrarium_tile", return_value=aws), \
                mock.patch.object(elevation.tilecache, "get", return_value=None), \
                mock.patch.object(elevation.tilecache, "put"):
            out = Image.open(io.BytesIO(elevation.japan_terrarium(10, 900, 400))).convert("RGB")
        self.assertAlmostEqual(elevation.terrarium_value(out.getpixel((5, 5))), 377.22, places=1)
        self.assertAlmostEqual(elevation.terrarium_value(out.getpixel((0, 0))), -12.0, places=1)


class Stored(TestCase):
    def setUp(self):
        self.ps = PointSet.objects.create(name="시험")
        self.p = Point.objects.create(pointset=self.ps, lat=37.5, lon=127.0, label="KP-1",
                                      props={"고도": "812"})

    def fill(self):
        with mock.patch.object(elevation, "elevations",
                               return_value={self.p.id: (1691.72, "aws-terrarium-z12")}):
            return self.client.post(f"/GSM/pointsets/{self.ps.id}/elevation/")

    def test_채우면_제_칸에_들고_원본_열은_그대로(self):
        r = self.fill()
        self.assertEqual(r.status_code, 200)
        self.assertEqual((r.json()["filled"], r.json()["missed"]), (1, 0))
        self.p.refresh_from_db()
        self.assertEqual((self.p.elev, self.p.elev_source, self.p.elev_datum),
                         (1691.7, "aws-terrarium-z12", "egm96"))
        self.assertEqual(self.p.props, {"고도": "812"})
        props = self.client.get(f"/GSM/pointsets/{self.ps.id}/geojson/").json()["features"][0]["properties"]
        self.assertEqual((props["표고(DEM)"], props["표고 출처"], props["고도"]),
                         (1691.7, "aws-terrarium-z12", "812"))

    def test_되살리면_두_칸이_제자리로(self):
        self.fill()
        self.client.post(f"/GSM/pointsets/{self.ps.id}/delete/")
        gone = PointSetDeletion.objects.get()
        ps, _, _ = pointsets.restore(gone)
        p = ps.points.get()
        self.assertEqual((p.elev, p.elev_source, p.elev_datum), (1691.7, "aws-terrarium-z12", "egm96"))
        self.assertEqual(p.props, {"고도": "812"})

    def test_많으면_명령으로_넘긴다(self):
        Point.objects.bulk_create([Point(pointset=self.ps, lat=78.0, lon=15.0) for _ in range(101)])
        r = self.client.post(f"/GSM/pointsets/{self.ps.id}/elevation/")
        self.assertEqual(r.status_code, 400)
        self.assertIn(f"fill_elevation {self.ps.id}", r.json()["error"])

    def test_높이_기준표가_두_곳에서_같다(self):
        self.assertEqual(pointsets.ELEV_DATUMS, {k: v[1] for k, v in elevation.SOURCES.items()})


class JapanDemView(SimpleTestCase):
    def test_일본_밖이면_AWS_로_넘긴다(self):
        with mock.patch.object(elevation, "japan_terrarium", return_value=None):
            r = self.client.get("/GSM/dem/12/3490/1587.png")
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r["Location"], elevation.TERRARIUM_URL.format(z=12, x=3490, y=1587))

    def test_z14_너머는_없다(self):
        self.assertEqual(self.client.get("/GSM/dem/15/1/1.png").status_code, 404)
