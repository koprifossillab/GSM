"""지도에서 찍은 점을 **목록으로 저장하는** 뷰를 시험한다.

파일 업로드와 달리 여기 들어오는 것은 브라우저가 만든 JSON 이라 꼴이 고를
것 같지만, 그렇지 않다. 저장 단추는 사람이 아무 때나 누르고(점이 하나도 없을
때도), 본문은 요청 하나로 얼마든 커질 수 있다. 그래서 **막는 자리마다**
시험을 둔다 — 버릴 좌표, 빈 목록, 못 읽는 본문, 너무 많은 점.

DB 에 행이 **생기는** 것을 보므로 `TestCase` 를 쓴다.
"""
import json
from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from viewer.models import Point, PointSet


class 점묶음_저장(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("viewer:pointset-create")

    def post(self, payload):
        return self.client.post(
            self.url, json.dumps(payload), content_type="application/json")

    # ── 저장되는 것 ───────────────────────────────────────────────────

    def test_점_두_개를_보내면_점묶음이_생긴다(self):
        response = self.post({"name": "답사 지점", "color": "#112233", "points": [
            {"lat": 36.35, "lon": 127.38, "label": "갑천"},
            {"lat": 37.0, "lon": 128.0, "label": "둘째"},
        ]})
        self.assertEqual(response.status_code, 200)
        body = response.json()["pointset"]
        self.assertEqual(body["count"], 2)
        self.assertEqual(body["name"], "답사 지점")
        self.assertEqual(body["color"], "#112233")

        pointset = PointSet.objects.get(pk=body["id"])
        self.assertEqual(pointset.points.count(), 2)
        first = pointset.points.first()
        self.assertEqual((first.lat, first.lon, first.label),
                         (36.35, 127.38, "갑천"))
        self.assertEqual(Point.objects.count(), 2)

    def test_이름을_안_주면_기본_이름이_붙는다(self):
        response = self.post({"points": [{"lat": 36.35, "lon": 127.38}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pointset"]["name"], "찍은 점")

    def test_빈_이름도_기본_이름이_붙는다(self):
        response = self.post({"name": "   ",
                              "points": [{"lat": 36.35, "lon": 127.38}]})
        self.assertEqual(response.json()["pointset"]["name"], "찍은 점")

    def test_색을_안_주면_기본_색이_붙는다(self):
        response = self.post({"points": [{"lat": 36.35, "lon": 127.38}]})
        self.assertEqual(response.json()["pointset"]["color"], "#27456f")

    def test_이름표가_200자를_넘으면_잘린다(self):
        response = self.post({"points": [
            {"lat": 36.35, "lon": 127.38, "label": "가" * 250}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Point.objects.get().label, "가" * 200)

    # ── 버리는 것 ─────────────────────────────────────────────────────

    def test_위경도_범위를_벗어난_점은_버리고_나머지만_담는다(self):
        response = self.post({"points": [
            {"lat": 36.35, "lon": 127.38},
            {"lat": 100.0, "lon": 127.38},     # 위도가 90 을 넘는다
            {"lat": 36.0, "lon": 200.0},       # 경도가 180 을 넘는다
            {"lat": 37.0, "lon": 128.0},
        ]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pointset"]["count"], 2)
        self.assertEqual(
            sorted(p.lat for p in Point.objects.all()), [36.35, 37.0])

    def test_좌표가_숫자가_아니거나_빠진_점도_버린다(self):
        response = self.post({"points": [
            {"lat": 36.35, "lon": 127.38},
            {"lat": "못읽음", "lon": 127.38},
            {"lon": 127.38},                   # 위도가 없다
            {"lat": None, "lon": None},
        ]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pointset"]["count"], 1)

    # ── 막는 것 ───────────────────────────────────────────────────────

    def test_쓸_만한_좌표가_하나도_없으면_막는다(self):
        response = self.post({"points": [
            {"lat": 100.0, "lon": 127.38},
            {"lat": "못읽음", "lon": "못읽음"},
        ]})
        self.assertEqual(response.status_code, 400)
        self.assertIn("쓸 만한 좌표가 없다", response.json()["error"])
        self.assertEqual(PointSet.objects.count(), 0)
        self.assertEqual(Point.objects.count(), 0)

    def test_점이_비면_막는다(self):
        response = self.post({"name": "빈 것", "points": []})
        self.assertEqual(response.status_code, 400)
        self.assertIn("저장할 점이 없다", response.json()["error"])
        self.assertEqual(PointSet.objects.count(), 0)

    def test_points_가_아예_없어도_막는다(self):
        response = self.post({"name": "빈 것"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("저장할 점이 없다", response.json()["error"])

    def test_본문이_json_이_아니면_막는다(self):
        response = self.client.post(
            self.url, "점이 아니다", content_type="application/json")
        self.assertEqual(response.status_code, 400)
        self.assertIn("읽지 못했다", response.json()["error"])
        self.assertEqual(PointSet.objects.count(), 0)

    def test_한_번에_저장할_수_있는_수를_넘으면_막는다(self):
        rows = [{"lat": 36.0 + i / 100, "lon": 127.0} for i in range(3)]
        with patch("viewer.views.MAX_SAVED_POINTS", 2):
            response = self.post({"points": rows})
        self.assertEqual(response.status_code, 400)
        self.assertIn("2점까지", response.json()["error"])
        self.assertEqual(PointSet.objects.count(), 0)

    def test_한계까지는_저장된다(self):
        rows = [{"lat": 36.0 + i / 100, "lon": 127.0} for i in range(2)]
        with patch("viewer.views.MAX_SAVED_POINTS", 2):
            response = self.post({"points": rows})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["pointset"]["count"], 2)

    def test_get_으로_부르면_막는다(self):
        self.assertEqual(self.client.get(self.url).status_code, 405)
