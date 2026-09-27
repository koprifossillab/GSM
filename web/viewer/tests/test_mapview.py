"""첫 화면 — CSS·JS 주소에 내용 표가 붙는지.

nginx 가 정적 파일을 7 일간 `immutable` 로 내보내므로, 주소가 그대로면
브라우저는 새로 배포한 CSS·JS 를 받지 않는다. v0.2.1 이 그렇게 옛 판으로 떴다.
"""
import json
import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from viewer import views
from viewer.models import Layer, LayerGroup


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


class PolarProjectionTests(TestCase):
    """극지 화면 (devlog 017). 투영은 브라우저가 바꾸지만, 그러려면 서버가
    proj4 를 싣고 레이어마다 상류를 알려 줘야 한다."""

    def test_proj4_is_loaded_between_ol_and_map_js(self):
        html = self.client.get(reverse("viewer:map")).content.decode()
        self.assertIn("vendor/proj4.js", html)
        self.assertLess(html.index("vendor/ol.js"), html.index("vendor/proj4.js"))
        self.assertLess(html.index("vendor/proj4.js"), html.index("viewer/map.js"))

    def test_catalog_rows_carry_upstream(self):
        """화면은 상류를 보고 레이어를 만든다 — WMS 인가 구운 타일(geomap)인가."""
        g = LayerGroup.objects.create(name="지질도", region="greenland")
        Layer.objects.create(name="grl_g500_lithostr_search", title="50만", group=g, upstream="geus")
        k = LayerGroup.objects.create(name="지질도", region="korea")
        Layer.objects.create(name="L_50K_Geology_Map", title="5만", group=k)
        rows = {l["name"]: l for grp in views._catalog() for l in grp["layers"]}
        self.assertEqual(rows["grl_g500_lithostr_search"]["upstream"], "geus")
        self.assertEqual(rows["L_50K_Geology_Map"]["upstream"], "kigam")

    def test_every_seed_upstream_has_a_layer_maker(self):
        """씨앗의 상류(`_상류`)가 map.js 의 `LAYER_KINDS` 에 없으면 그 레이어는
        KIGAM WMS 로 잘못 불린다. 씨앗을 새로 더해도 여기서 걸린다."""
        js = (Path(views.__file__).parent / "static/viewer/map.js").read_text(encoding="utf-8")
        block = re.search(r"var LAYER_KINDS = \{(.*?)\n  \};", js, re.S).group(1)
        kinds = set(re.findall(r"^\s*(\w+):", block, re.M))
        used = {"kigam"}
        for seed in (settings.REPO_DIR / "data").glob("*_layers.json"):
            used.add(json.loads(seed.read_text(encoding="utf-8")).get("_상류", "kigam"))
        self.assertLessEqual(used, kinds)
        self.assertIn("geomap", kinds)
