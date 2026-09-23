"""올린 파일을 점묶음으로 읽는 자리.

현장에서 오는 표는 열 이름도 글자 인코딩도 제각각이다. 그 제각각을 여기서
받아내기로 했으므로(사람에게 고르라고 묻지 않는다), 받아내는 꼴마다 시험을 둔다.
"""
from django.test import SimpleTestCase

from viewer import pointsets


def utf8(text):
    return text.encode("utf-8")


class Csv(SimpleTestCase):
    def test_한글_열이름(self):
        points, notes = pointsets.parse("a.csv", utf8(
            "지점명,위도,경도,암상\n갑천,36.35,127.38,충적층\n"))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["lat"], 36.35)
        self.assertEqual(points[0]["lon"], 127.38)
        self.assertEqual(points[0]["label"], "갑천")
        self.assertEqual(points[0]["props"], {"암상": "충적층"})
        self.assertEqual(notes, [])

    def test_영문_열이름(self):
        points, _ = pointsets.parse("a.csv", utf8(
            "name,lat,lon\nsite1,36.35,127.38\n"))
        self.assertEqual(points[0]["label"], "site1")

    def test_x_y_도_위경도로_읽는다(self):
        points, _ = pointsets.parse("a.csv", utf8("y,x\n36.35,127.38\n"))
        self.assertEqual((points[0]["lat"], points[0]["lon"]), (36.35, 127.38))

    def test_cp949(self):
        raw = "지점명,위도,경도\n갑천,36.35,127.38\n".encode("cp949")
        points, _ = pointsets.parse("a.csv", raw)
        self.assertEqual(points[0]["label"], "갑천")

    def test_bom_이_붙은_utf8(self):
        raw = "﻿위도,경도\n36.35,127.38\n".encode("utf-8")
        points, _ = pointsets.parse("a.csv", raw)
        self.assertEqual(points[0]["lat"], 36.35)

    def test_탭으로_나뉜_것(self):
        points, _ = pointsets.parse("a.tsv", utf8("위도\t경도\n36.35\t127.38\n"))
        self.assertEqual(points[0]["lon"], 127.38)

    def test_도분초가_든_칸(self):
        points, _ = pointsets.parse("a.csv", utf8(
            "위도,경도\n36°21'00.0\"N,127°22'48.0\"E\n"))
        self.assertAlmostEqual(points[0]["lat"], 36.35, places=4)
        self.assertAlmostEqual(points[0]["lon"], 127.38, places=4)

    def test_못_읽는_줄은_건너뛰고_까닭을_남긴다(self):
        points, notes = pointsets.parse("a.csv", utf8(
            "위도,경도\n36.35,127.38\n,\n못읽음,127.0\n"))
        self.assertEqual(len(points), 1)
        self.assertTrue(notes)
        self.assertIn("건너뛰었다", notes[0])

    def test_위경도_열이_없으면_까닭을_말한다(self):
        with self.assertRaises(pointsets.UploadError) as caught:
            pointsets.parse("a.csv", utf8("이름,설명\n가,나\n"))
        message = str(caught.exception)
        self.assertIn("위경도 열을 찾지 못했다", message)
        self.assertIn("이름", message)      # 읽은 열을 되비춘다

    def test_좌표가_하나도_없으면_막는다(self):
        with self.assertRaises(pointsets.UploadError):
            pointsets.parse("a.csv", utf8("위도,경도\n,\n,\n"))


class GeoJson(SimpleTestCase):
    FEATURE = """
    {"type":"FeatureCollection","features":[
      {"type":"Feature","geometry":{"type":"Point","coordinates":[127.38,36.35]},
       "properties":{"이름":"갑천","암상":"충적층"}}]}
    """

    def test_점을_읽는다(self):
        points, _ = pointsets.parse("a.geojson", utf8(self.FEATURE))
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]["lat"], 36.35)
        self.assertEqual(points[0]["lon"], 127.38)
        self.assertEqual(points[0]["label"], "갑천")

    def test_확장자가_없어도_중괄호로_시작하면_geojson_이다(self):
        points, _ = pointsets.parse("a.txt", utf8(self.FEATURE))
        self.assertEqual(len(points), 1)

    def test_선_면은_건너뛰고_까닭을_남긴다(self):
        raw = """
        {"type":"FeatureCollection","features":[
          {"type":"Feature","geometry":{"type":"Point","coordinates":[127.0,36.0]},"properties":{}},
          {"type":"Feature","geometry":{"type":"LineString","coordinates":[[127,36],[128,37]]},"properties":{}}]}
        """
        points, notes = pointsets.parse("a.geojson", utf8(raw))
        self.assertEqual(len(points), 1)
        self.assertTrue(any("선·면" in n for n in notes))

    def test_점이_하나도_없으면_막는다(self):
        raw = """{"type":"FeatureCollection","features":[
          {"type":"Feature","geometry":{"type":"LineString","coordinates":[[127,36],[128,37]]},"properties":{}}]}"""
        with self.assertRaises(pointsets.UploadError):
            pointsets.parse("a.geojson", utf8(raw))

    def test_깨진_json(self):
        with self.assertRaises(pointsets.UploadError):
            pointsets.parse("a.geojson", utf8("{nope"))
