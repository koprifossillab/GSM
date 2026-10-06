"""받은 차례의 기록 — store.sqlite 의 fetch_log (jikhanjung P02 2 단계).

지키는 것 — 명령이 끝나면 한 줄(된 것·깨진 것 모두), 명령이 아는 것을 보탤 수 있다, 호스트는 sqlite 에 쓰지 않는다,
호스트가 남긴 것을 옮겨 적되 두 번 적지 않는다, 장부가 깨져도 명령은 돈다.
"""
import io
import json
import os
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.test import SimpleTestCase, override_settings

from viewer import fetchlog, sources


class Base(SimpleTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        seed = self.dir / "seed.json"
        seed.write_text(json.dumps({"sources": [
            {"id": "demo", "name": {"ko": "시험", "en": "Demo"}, "kind": "fetch", "commands": ["fetch_demo"],
             "runs_on": "container", "schedule": "manual", "license": "x"},
            {"id": "wind", "name": {"ko": "바람", "en": "Wind"}, "kind": "fetch", "commands": ["fetch_gfs_wind"],
             "runs_on": "host", "schedule": "hourly", "license": "x"},
        ]}), encoding="utf-8")
        over = override_settings(STORE_PATH=str(self.dir / "store.sqlite"), SOURCES_PATH=str(self.dir / "none.json"),
                                 SOURCES_SEED=seed, FETCH_LOG=True)
        over.enable()
        self.addCleanup(over.disable)
        sources._cache.update(key=None, spec=None)
        self.addCleanup(lambda: sources._cache.update(key=None, spec=None))
        env = mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "container"})
        env.start()
        self.addCleanup(env.stop)

    def rows(self):
        db = sqlite3.connect(self.dir / "store.sqlite")
        db.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in db.execute("SELECT * FROM fetch_log ORDER BY id")]
        finally:
            db.close()


class Record(Base):
    def test_된_것을_적고_마지막_말과_보탠_칸을_남긴다(self):
        with fetchlog.record("demo", "fetch_demo") as tail:
            tail.write("받는다 …\n\n  1 234 곳을 구웠다\n")
            fetchlog.note(rows=1234, expected=1234, raw_path="earth/x.csv", 엉뚱한="버린다")
        [row] = self.rows()
        self.assertEqual((row["source"], row["result"], row["rows"], row["expected"]), ("demo", "ok", 1234, 1234))
        self.assertEqual(row["note"], "1 234 곳을 구웠다")
        self.assertEqual(row["raw_path"], "earth/x.csv")
        self.assertEqual(row["origin"], "container")

    def test_깨지면_fail_과_까닭을_적고_다시_던진다(self):
        with self.assertRaises(CommandError):
            with fetchlog.record("demo", "fetch_demo"):
                raise CommandError("상류가 500 을 줬다")
        [row] = self.rows()
        self.assertEqual(row["result"], "fail")
        self.assertIn("상류가 500", row["note"])

    def test_장부가_깨져도_명령은_돈다(self):
        with override_settings(STORE_PATH="/proc/못쓰는자리/store.sqlite"):
            with fetchlog.record("demo", "fetch_demo"):
                done = True
        self.assertTrue(done)

    def test_호스트는_sqlite_에_쓰지_않는다(self):
        with mock.patch.dict(os.environ, {"GSM_RUN_PLACE": "host"}):
            with fetchlog.record("wind", "fetch_gfs_wind", "hourly"):
                pass                                         # 매시 일 — hourly_status.json 이 남긴다
            with fetchlog.record("era5", "build_era5_wind", "manual"):
                pass                                         # 사람이 부른 일 — jsonl 에 한 줄
        self.assertFalse((self.dir / "store.sqlite").exists())
        lines = (self.dir / "fetch_log_host.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual([json.loads(x)["source"] for x in lines], ["era5"])


class Sync(Base):
    def test_hourly_status_와_호스트_기록을_한_번만_옮겨_적는다(self):
        (self.dir / "hourly_status.json").write_text(json.dumps({"jobs": {
            "fetch_gfs_wind": {"at": "2026-10-06T16:40:02+09:00", "result": "ok", "seconds": 1, "note": "할 일 없음"},
            "fetch_모르는것": {"at": "2026-10-06T16:40:02+09:00", "result": "ok"},
        }}), encoding="utf-8")
        (self.dir / "fetch_log_host.jsonl").write_text(json.dumps(
            {"source": "era5", "command": "build_era5_wind", "started_at": "2026-10-05T10:00:00+09:00",
             "result": "ok", "seconds": 60}) + "\n깨진 줄\n", encoding="utf-8")
        self.assertEqual(fetchlog.sync(), 2)
        self.assertEqual(fetchlog.sync(), 0)             # 두 번 적지 않는다
        got = {(r["source"], r["origin"]) for r in self.rows()}
        self.assertEqual(got, {("wind", "hourly"), ("era5", "host")})

    def test_자료원마다_마지막과_마지막으로_된_것(self):
        for at, result in (("2026-10-01T00:00:00+09:00", "ok"), ("2026-10-02T00:00:00+09:00", "fail")):
            fetchlog.write({"source": "demo", "started_at": at, "result": result})
        got = fetchlog.latest()["demo"]
        self.assertEqual(got["last"]["result"], "fail")
        self.assertEqual(got["last_ok"]["started_at"][:10], "2026-10-01")
        self.assertEqual(len(fetchlog.history("demo")), 2)


class WrapsCommands(Base):
    def test_fetch_build_명령이_끝나면_한_줄이_생긴다(self):
        """apps.py 가 BaseCommand.execute 를 감쌌다 — 진짜 명령 하나로 본다(빈 자리라 할 일이 없다)"""
        out = io.StringIO()
        with override_settings(KIGAM50K_DIR=str(self.dir / "k")):
            call_command("sources_seed", "--check", stdout=io.StringIO(), stderr=io.StringIO())   # 기록 대상이 아니다
            with mock.patch("viewer.management.commands.fetch_kigam50k.Command.handle",
                            side_effect=lambda *a, **k: None):
                call_command("fetch_kigam50k", stdout=out)
        rows = self.rows()
        self.assertEqual([(r["command"], r["result"]) for r in rows], [("fetch_kigam50k", "ok")])
        self.assertEqual(rows[0]["source"], "fetch_kigam50k")   # 이 시험의 명세에 없는 명령 — 이름을 자료원으로

    def test_시험에서는_끈다(self):
        with override_settings(FETCH_LOG=False), \
                mock.patch("viewer.management.commands.fetch_kigam50k.Command.handle", side_effect=lambda *a, **k: None):
            call_command("fetch_kigam50k", stdout=io.StringIO())
        self.assertFalse((self.dir / "store.sqlite").exists())

    def test_감싸기는_한_번뿐이다(self):
        self.assertTrue(getattr(BaseCommand.execute, "_gsm_recorded", False))


class SpecChange(Base):
    def test_명세가_바뀌면_기록_표에도_한_줄(self):
        live = self.dir / "live.json"
        with override_settings(SOURCES_PATH=str(live)):
            live.write_text(json.dumps({"sources": []}), encoding="utf-8")
            sources._cache.update(key=None, spec=None)
            sources.load()
        self.assertEqual([r["source"] for r in self.rows()], ["_spec"])
