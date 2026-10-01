"""소개 화면과 지도의 새 주소 (wetherilli 113).

뿌리(`/GSM/`)는 늘 소개이고 지도는 `map/` 이다. 지도에서 다른 갈래로 가는 주소가 `map/` 밑으로
새지 않는지, 소개가 부르는 그림이 두 언어 모두 있는지 본다.
"""
import re
from pathlib import Path

from django.test import TestCase
from django.urls import reverse

HERE = Path(__file__).resolve().parent.parent
SHOTS = HERE / "static" / "viewer" / "intro"


class IntroTests(TestCase):
    def get(self, name, lang="ko"):
        self.client.cookies["gsm_lang"] = lang
        response = self.client.get(reverse(name))
        self.assertEqual(response.status_code, 200)
        return response.content.decode("utf-8")

    def test_뿌리는_소개다(self):
        self.assertEqual(reverse("viewer:intro"), "/GSM/")
        self.assertEqual(reverse("viewer:map"), "/GSM/map/")
        html = self.get("viewer:intro")
        self.assertIn("intro.js", html)
        self.assertIn('id="skip"', html)
        # 건너뛰기 단추와 갈래 단추는 지도의 새 주소로 간다
        self.assertIn('href="/GSM/map/?region=korea"', html)
        self.assertIn('href="/GSM/map/?region=antarctica"', html)
        self.assertIn('href="/GSM/3d/"', html)

    def test_지도의_갈래는_뿌리_밑이다(self):
        html = self.get("viewer:map")
        for target in ("earth/", "moon/", "mars/", "3d/"):
            self.assertIn(f'href="/GSM/{target}"', html)
        self.assertNotIn('href="/GSM/map/earth/"', html)
        # 숨은 차림에서 소개로 돌아간다
        self.assertIn('class="intro-link" href="/GSM/"', html)

    def test_달_화성_온지구에서_지구는_지도로(self):
        for name in ("viewer:moon", "viewer:mars", "viewer:earth"):
            html = self.get(name)
            self.assertIn('href="/GSM/map/"', html, name)

    def test_영어판(self):
        html = self.get("viewer:intro", "en")
        self.assertIn('<html lang="en">', html)
        self.assertIn("<title>Great Stone Map</title>", html)
        self.assertIn("Go to the map", html)
        self.assertIn("/static/viewer/intro/en/", html)
        self.assertNotIn("/static/viewer/intro/ko/", html)

    def test_그림이_두_언어_모두_있다(self):
        html = (HERE / "templates" / "viewer" / "intro.html").read_text(encoding="utf-8")
        names = set(re.findall(r"shots\|add:'([\w.]+)'", html))
        self.assertTrue(names)
        for lang in ("ko", "en"):
            for name in names:
                self.assertTrue((SHOTS / lang / name).is_file(), f"{lang}/{name}")
