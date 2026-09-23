"""받아온 타일을 디스크에 두는 자리.

여기서 지키는 것은 셋이다 — **인증키가 열쇠에 섞이지 않는 것**(섞이면 키가
나온 날 받아둔 것을 전부 버린다), **캐시가 깨져도 뷰어가 멈추지 않는 것**,
그리고 **자리가 모자라면 스스로 줄어드는 것**.
"""
import os
import tempfile
import time
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from viewer import tilecache

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200


class CacheCase(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="gsm-tiles-")
        patch = override_settings(
            TILE_CACHE_DIR=self.dir,
            TILE_CACHE_MAX_AGE_DAYS=30,
            TILE_CACHE_MAX_BYTES=10 * 1024 * 1024,
        )
        patch.enable()
        self.addCleanup(patch.disable)

    def files(self):
        return list(Path(self.dir).rglob("*.png"))


class Key(CacheCase):
    MAP = {"layers": "L_50K_Geology_Map", "bbox": "1,2,3,4",
           "width": "256", "height": "256", "srs": "EPSG:3857"}

    def test_같은_요청은_같은_열쇠(self):
        self.assertEqual(tilecache.key_for("map", self.MAP),
                         tilecache.key_for("map", dict(self.MAP)))

    def test_인증키는_열쇠에_섞이지_않는다(self):
        """키가 없을 때 받아둔 타일을, 키가 생긴 뒤에도 그대로 쓴다."""
        with_key = dict(self.MAP, key="SECRET")
        self.assertEqual(tilecache.key_for("map", self.MAP),
                         tilecache.key_for("map", with_key))

    def test_범위가_다르면_열쇠도_다르다(self):
        other = dict(self.MAP, bbox="9,9,9,9")
        self.assertNotEqual(tilecache.key_for("map", self.MAP),
                            tilecache.key_for("map", other))

    def test_레이어가_다르면_열쇠도_다르다(self):
        other = dict(self.MAP, layers="L_250K_Geology_Map")
        self.assertNotEqual(tilecache.key_for("map", self.MAP),
                            tilecache.key_for("map", other))

    def test_대소문자와_빈칸은_같은_것으로_본다(self):
        other = dict(self.MAP, layers=" l_50k_geology_map ")
        self.assertEqual(tilecache.key_for("map", self.MAP),
                         tilecache.key_for("map", other))

    def test_지도와_범례는_섞이지_않는다(self):
        self.assertNotEqual(tilecache.key_for("map", {"layer": "a"}),
                            tilecache.key_for("legend", {"layer": "a"}))


class PutGet(CacheCase):
    def test_넣고_꺼낸다(self):
        tilecache.put("a" * 64, PNG)
        self.assertEqual(tilecache.get("a" * 64), PNG)

    def test_없으면_None(self):
        self.assertIsNone(tilecache.get("b" * 64))

    def test_두자씩_갈라_담는다(self):
        key = "abcd" + "0" * 60
        tilecache.put(key, PNG)
        self.assertTrue((Path(self.dir) / "ab" / "cd" / f"{key}.png").exists())

    def test_빈_것은_넣지_않는다(self):
        tilecache.put("c" * 64, b"")
        self.assertEqual(self.files(), [])

    def test_늙으면_없는_셈_친다(self):
        key = "d" * 64
        tilecache.put(key, PNG)
        old = time.time() - 31 * 86400
        os.utime(tilecache._path(key), (old, old))
        self.assertIsNone(tilecache.get(key))

    def test_반쯤_쓰다_만_파일을_남기지_않는다(self):
        tilecache.put("e" * 64, PNG)
        self.assertEqual([p.suffix for p in self.files()], [".png"])

    @override_settings(TILE_CACHE_DIR="")
    def test_꺼두면_아무_일도_하지_않는다(self):
        self.assertFalse(tilecache.enabled())
        tilecache.put("f" * 64, PNG)          # 터지지 않는다
        self.assertIsNone(tilecache.get("f" * 64))

    def test_쓸_수_없는_자리여도_멈추지_않는다(self):
        """캐시는 덤이다. 디스크가 막혀도 뷰어는 돌아야 한다."""
        with override_settings(TILE_CACHE_DIR="/proc/못쓰는자리"):
            tilecache.put("g" * 64, PNG)      # 예외가 새어나오면 안 된다
            self.assertIsNone(tilecache.get("g" * 64))


class Prune(CacheCase):
    def test_늙은_것을_버린다(self):
        fresh, old = "1" * 64, "2" * 64
        tilecache.put(fresh, PNG)
        tilecache.put(old, PNG)
        stamp = time.time() - 40 * 86400
        os.utime(tilecache._path(old), (stamp, stamp))

        result = tilecache.prune()
        self.assertEqual(result["removed_age"], 1)
        self.assertIsNotNone(tilecache.get(fresh))
        self.assertFalse(tilecache._path(old).exists())

    def test_자리가_모자라면_오래_안_쓰인_것부터_버린다(self):
        keys = [str(i) * 64 for i in range(1, 5)]
        for i, key in enumerate(keys):
            tilecache.put(key, PNG)
            stamp = time.time() - (100 - i)     # 앞의 것일수록 오래 안 쓰였다
            os.utime(tilecache._path(key), (stamp, time.time()))

        # 두 장만 들어갈 만큼으로 조인다
        result = tilecache.prune(max_bytes=len(PNG) * 2, max_age_days=0)
        self.assertEqual(result["count"], 2)
        self.assertFalse(tilecache._path(keys[0]).exists())
        self.assertTrue(tilecache._path(keys[-1]).exists())

    def test_한계_안이면_버리지_않는다(self):
        tilecache.put("3" * 64, PNG)
        result = tilecache.prune()
        self.assertEqual((result["removed_age"], result["removed_size"]), (0, 0))
        self.assertEqual(result["count"], 1)


class Stats(CacheCase):
    def test_수와_크기를_센다(self):
        tilecache.put("4" * 64, PNG)
        tilecache.put("5" * 64, PNG)
        got = tilecache.stats()
        self.assertEqual(got["count"], 2)
        self.assertEqual(got["bytes"], len(PNG) * 2)
