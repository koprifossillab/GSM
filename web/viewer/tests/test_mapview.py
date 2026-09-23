"""첫 화면 — CSS·JS 주소에 내용 표가 붙는지.

nginx 가 정적 파일을 7 일간 `immutable` 로 내보내므로, 주소가 그대로면
브라우저는 새로 배포한 CSS·JS 를 받지 않는다. v0.2.1 이 그렇게 옛 판으로 떴다.
"""
import re

from django.test import TestCase, override_settings
from django.urls import reverse

from viewer import views


@override_settings(DEBUG=False)
class AssetStampTests(TestCase):
    def setUp(self):
        views.asset_stamp.cache_clear()

    def test_css_and_js_carry_the_stamp(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        stamp = views.asset_stamp()
        self.assertRegex(stamp, r"^[0-9a-f]{10}$")
        self.assertIn("map.css?v=" + stamp, html)
        self.assertIn("map.js?v=" + stamp, html)

    def test_stamp_follows_content(self):
        before = views.asset_stamp()
        views.asset_stamp.cache_clear()
        original = views.STAMPED
        try:
            views.STAMPED = original[:1]
            self.assertNotEqual(views.asset_stamp(), before)
        finally:
            views.STAMPED = original
            views.asset_stamp.cache_clear()

    def test_splash_is_in_the_first_paint(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        self.assertTrue(re.search(r'<div id="splash"[^>]*>\s*<img[^>]*splash\.gif', html))
        self.assertIn("불러오는 중", html)
