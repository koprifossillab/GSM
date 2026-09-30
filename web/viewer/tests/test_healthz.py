"""`/healthz/` 를 시험한다 (koprifossillab 002).

볼 것은 셋 — 레이어가 없으면 unhealthy(503), 백업 기록이 없거나 멈췄거나 낡았으면 degraded(200),
다 괜찮으면 ok. 백업 기록은 `weekly_backup.sh` 가 적는 꼴 그대로 만든다.
"""
import datetime
import json
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from viewer.models import Layer, LayerGroup

URL = "/GSM/healthz/"


def _record(path: Path, *, days_ago: float = 0, **fields):
    at = datetime.datetime.now().astimezone() - datetime.timedelta(days=days_ago)
    record = {"at": at.isoformat(timespec="seconds"), "result": "ok", "step": "fetch", "note": "다 했다",
              "backup": "/data/GSM/backups/GSM.20260930.tar.gz", "built": "same",
              "nas": "ok", "tiles": "ok", "sources": "ok", "fetch": "fetch_kopri"}
    record.update(fields)
    path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")


class 헬스(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.status = Path(self.tmp.name) / "backup_status.json"
        patcher = override_settings(BACKUP_STATUS_FILE=str(self.status))
        patcher.enable()
        self.addCleanup(patcher.disable)

    def _layer(self):
        group = LayerGroup.objects.create(name="지질도")
        Layer.objects.create(name="L_250K_Geology_Map", title="25만 지질도", group=group)

    def get(self):
        response = self.client.get(URL)
        return response.status_code, response.json()

    def test_레이어가_없으면_unhealthy(self):
        _record(self.status)
        code, body = self.get()
        self.assertEqual(code, 503)
        self.assertEqual(body["status"], "unhealthy")

    def test_다_괜찮으면_ok(self):
        self._layer()
        _record(self.status, days_ago=1)
        code, body = self.get()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["db"]["layer"], 1)
        self.assertEqual(body["notes"], [])
        self.assertEqual(body["backup"]["age_days"], 1.0)

    def test_백업_기록이_없으면_degraded(self):
        self._layer()
        code, body = self.get()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "degraded")
        self.assertIsNone(body["backup"])

    def test_백업이_멈췄으면_degraded(self):
        self._layer()
        _record(self.status, result="fail", step="built", note="tar 실패")
        code, body = self.get()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "degraded")
        self.assertIn("built", body["notes"][0])

    def test_백업이_여드레를_넘으면_degraded(self):
        self._layer()
        _record(self.status, days_ago=9)
        _, body = self.get()
        self.assertEqual(body["status"], "degraded")

    def test_NAS_가_실패하면_degraded(self):
        self._layer()
        _record(self.status, nas="fail", tiles="fail")
        _, body = self.get()
        self.assertEqual(body["status"], "degraded")
        self.assertIn("nas, tiles", body["notes"][0])

    def test_깨진_기록도_죽지_않는다(self):
        self._layer()
        self.status.write_text("{깨진", encoding="utf-8")
        code, body = self.get()
        self.assertEqual(code, 200)
        self.assertEqual(body["status"], "degraded")

    def test_캐시하지_않는다(self):
        self._layer()
        _record(self.status)
        self.assertEqual(self.client.get(URL)["Cache-Control"], "no-store")
