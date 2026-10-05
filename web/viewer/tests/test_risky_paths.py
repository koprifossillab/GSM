"""시험이 지나가지 않던 위험한 길 (wetherilli 349) — 키·주소를 다루는 곳. coverage 로 찾았다.

상류를 부르지 않는다 — `requests.get` 과 이름 풀기를 갈아 끼운다. 지키는 것은 셋이다.
- 키는 오류 글·로그에 남지 않는다(예외 문구에 URL 이 실려 온다)
- 키가 없으면 묻지 않고, 묻지 않는 곳(GeoServer)에는 키를 싣지 않는다
- 연결 레이어의 문은 읽지 못하는 주소·이름·포트에서 멈추고, 끊기거나 넘겨받을 곳이 없을 때 까닭을 말한다
"""
import logging
from unittest import mock

import requests
from django.test import SimpleTestCase, override_settings

from viewer import kigam, linked, vworld
from viewer.tests.test_linked import HOSTS, Response, Session, resolves, sessions

KEY = "SECRET-KEY-1234"


def answer(status=200, ctype="image/png", content=b"\x89PNG", body=None):
    r = mock.Mock(status_code=status, headers={"content-type": ctype}, content=content, url="https://data.kigam.re.kr/openapi/wms?key=" + KEY,
                  text=(content or b"").decode("latin-1"), elapsed=None)
    if body is not None:
        r.json.return_value = body
    else:
        r.json.side_effect = ValueError("not json")
    return r


class KigamKey(SimpleTestCase):
    def setUp(self):
        for name, value in (("record", None), ("paused", 0)):
            p = mock.patch.object(kigam.usage, name, return_value=value)
            p.start()
            self.addCleanup(p.stop)

    @override_settings(KIGAM_KEY="", DEV_DIRECT_WMS=False)
    def test_키가_없으면_묻지_않는다(self):
        with mock.patch.object(kigam.requests, "get") as get, self.assertRaises(kigam.UpstreamError) as caught:
            kigam.get_map({"layers": "L_250K_Geology_Map"})
        get.assert_not_called()
        self.assertIn("인증키가 없다", str(caught.exception))

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=False)
    def test_닿지_못한_까닭에_키가_없다(self):
        boom = requests.ConnectionError(f"HTTPSConnectionPool: Max retries exceeded with url: /openapi/wms?key={KEY}&layers=x")
        with mock.patch.object(kigam.requests, "get", side_effect=boom), self.assertRaises(kigam.UpstreamError) as caught:
            kigam.get_map({"layers": "L_250K_Geology_Map"})
        self.assertNotIn(KEY, str(caught.exception))

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=True)
    def test_개발_스위치면_키를_싣지_않는다(self):
        with mock.patch.object(kigam.requests, "get", return_value=answer()) as get:
            kigam.get_map({"layers": "L_250K_Geology_Map"})
        self.assertNotIn("key", get.call_args.kwargs["params"])

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=False)
    def test_로그에_키가_없다(self):
        with mock.patch.object(kigam.requests, "get", return_value=answer()), self.assertLogs("viewer.kigam", logging.INFO) as logs:
            kigam.get_map({"layers": "L_250K_Geology_Map"})
        self.assertFalse([line for line in logs.output if KEY in line])

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=False)
    def test_그림이_아니면_오류(self):
        with mock.patch.object(kigam.requests, "get", return_value=answer(ctype="text/html", content=b"<html>error</html>")), \
             self.assertRaises(kigam.UpstreamError):
            kigam.get_map({"layers": "L_250K_Geology_Map"})
        with mock.patch.object(kigam.requests, "get", return_value=answer(ctype="text/html", content=b"<html/>")), \
             self.assertRaises(kigam.UpstreamError):
            kigam.get_legend("L_250K_Geology_Map")

    @override_settings(KIGAM_KEY=KEY, DEV_DIRECT_WMS=False)
    def test_속성은_키_없이_GeoServer_로_JSON_이_아니면_오류(self):
        with mock.patch.object(kigam.requests, "get", return_value=answer(ctype="text/html", content=b"<html/>")) as get, \
             self.assertRaises(kigam.UpstreamError):
            kigam.get_feature_info({"layers": "L_250K_Geology_Map", "query_layers": "L_250K_Geology_Map"})
        self.assertNotIn("key", get.call_args.kwargs["params"])
        with mock.patch.object(kigam.requests, "get", return_value=answer(status=500, ctype="text/html", content=b"x")), \
             self.assertRaises(kigam.UpstreamError):
            kigam.get_feature_info({"layers": "L_250K_Geology_Map"})

    def test_속성_길이_열렸는지_찔러보기(self):
        with override_settings(KIGAM_KEY=""):
            self.assertIn("인증키가 없어", kigam.probe_openapi_feature_info("L", "0,0,1,1"))
        with override_settings(KIGAM_KEY=KEY):
            with mock.patch.object(kigam.requests, "get", return_value=answer(ctype="application/json", body={"features": []})):
                self.assertTrue(kigam.probe_openapi_feature_info("L", "0,0,1,1").startswith("열렸다"))
            with mock.patch.object(kigam.requests, "get", return_value=answer(ctype="text/html", content=b"<html/>")):
                self.assertIn("아직 막혀 있다", kigam.probe_openapi_feature_info("L", "0,0,1,1"))
            with mock.patch.object(kigam.requests, "get", return_value=answer(status=500, ctype="text/html", content=b"x")):
                self.assertIn("status=500", kigam.probe_openapi_feature_info("L", "0,0,1,1"))
            boom = requests.ConnectionError(f"url: /openapi/wms?key={KEY}")
            with mock.patch.object(kigam.requests, "get", side_effect=boom):
                said = kigam.probe_openapi_feature_info("L", "0,0,1,1")
            self.assertIn("닿지 못했다", said)
            self.assertNotIn(KEY, said)


@override_settings(VWORLD_KEY=KEY)
class VWorldKey(SimpleTestCase):
    def test_국가중점데이터가_닿지_못한_까닭에_키가_없다(self):
        boom = requests.ConnectionError(f"Max retries exceeded with url: /ned/data/ladfrlList?key={KEY}&pnu=1")
        with mock.patch.object(vworld.requests, "get", side_effect=boom), self.assertRaises(vworld.VWorldError) as caught:
            vworld._ned(vworld.LAND_URL, {"pnu": "1"})
        self.assertNotIn(KEY, str(caught.exception))

    def test_국가중점데이터가_알아볼_수_없는_것을_주면(self):
        bad = mock.Mock(status_code=502, url=f"https://api.vworld.kr/ned?key={KEY}")
        bad.json.side_effect = ValueError("no")
        with mock.patch.object(vworld.requests, "get", return_value=bad), self.assertLogs("viewer.vworld", logging.INFO) as logs, \
             self.assertRaises(vworld.VWorldError):
            vworld._ned(vworld.LAND_URL, {"pnu": "1"})
        self.assertFalse([line for line in logs.output if KEY in line])


@override_settings(LINKED_ALLOW=[])
class LinkedEdges(SimpleTestCase):
    def setUp(self):
        for name in ("record",):
            p = mock.patch.object(linked.usage, name)
            p.start()
            self.addCleanup(p.stop)

    def test_읽지_못하는_주소·포트·이름(self):
        with self.assertRaises(linked.LinkedError) as caught:
            linked.check_url("http://[::1")                       # 닫히지 않은 IPv6 괄호
        self.assertEqual(caught.exception.status, 400)
        with self.assertRaises(linked.LinkedError) as caught:
            linked.check_url("http://api.example.org:99999/x")     # 포트가 범위 밖
        self.assertEqual(caught.exception.status, 400)
        with resolves(HOSTS), self.assertRaises(linked.LinkedError) as caught:
            linked.check_url("https://nowhere.example.org/x")
        self.assertEqual(caught.exception.status, 502)
        with mock.patch("viewer.linked.socket.getaddrinfo", return_value=[(2, 1, 6, "", ("not-an-ip", 443))]), \
             self.assertRaises(linked.LinkedError) as caught:
            linked.check_url("https://odd.example.org/x")          # 풀린 것이 IP 가 아니다
        self.assertEqual(caught.exception.status, 502)

    def test_머리·질의_방식으로_키를_싣는다(self):
        headers = {}
        self.assertEqual(linked._with_auth("https://a/x", {"mode": "header", "name": "X-Api-Key", "key": KEY}, headers), "https://a/x")
        self.assertEqual(headers["X-Api-Key"], KEY)
        url = linked._with_auth("https://a/x?key=old&q=1", {"mode": "query", "name": "key", "key": KEY}, {})
        self.assertIn(f"key={KEY}", url)
        self.assertNotIn("old", url)                               # 같은 이름의 옛 값은 갈아 끼운다
        self.assertEqual(linked.redact("http://[::1", None), "?")

    def test_닿지_못하면_로그에_키_없이(self):
        auth = {"mode": "query", "name": "token", "key": KEY}
        boom = mock.Mock()
        boom.get.side_effect = requests.ConnectionError("down")
        boom.__enter__ = lambda s: s
        boom.__exit__ = lambda s, *a: False
        with resolves(HOSTS), mock.patch("viewer.linked._session", return_value=boom), \
             self.assertLogs("viewer.linked", logging.INFO) as logs, self.assertRaises(linked.LinkedError):
            linked.fetch("https://api.example.org/data.json", auth)
        self.assertFalse([line for line in logs.output if KEY in line])

    def test_빈_곳으로_넘기거나_주지_않으면_까닭을_말한다(self):
        with resolves(HOSTS), sessions({"https://api.example.org/a": Response(302, b"", {})}), \
             self.assertRaises(linked.LinkedError) as caught:
            linked.fetch("https://api.example.org/a", {"mode": "none"})
        self.assertIn("빈 곳", str(caught.exception.args[0].template))
        with resolves(HOSTS), sessions({"https://api.example.org/b": Response(500, b"oops")}), \
             self.assertRaises(linked.LinkedError) as caught:
            linked.fetch("https://api.example.org/b", {"mode": "none"})
        self.assertIn("주지 않았다", str(caught.exception.args[0].template))

    def test_받다가_끊기면(self):
        class Broken(Response):
            def iter_content(self, size):
                yield b"{"
                raise requests.ConnectionError("reset")
        with resolves(HOSTS), sessions({"https://api.example.org/c": Broken(200, b"")}), \
             self.assertRaises(linked.LinkedError) as caught:
            linked.fetch("https://api.example.org/c", {"mode": "none"})
        self.assertIn("끊겼다", str(caught.exception.args[0].template))
        self.assertTrue(Session.calls)
