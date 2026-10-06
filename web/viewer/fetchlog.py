"""받은 차례의 기록 — `<DB 옆>/store.sqlite` 의 `fetch_log` (jikhanjung P02 2 단계).

**문이 아니다.** 받아 두는 자료원(`sources.json`, P02 1 단계)마다 **받은 차례 하나가 한 줄**이다 — 언제·결과·걸린 초·마지막 말·
상류가 센 수 대 받은 수·원본 자리와 sha·구운 판. 사람이 정하는 것(조건·주기)은 명세에, 돌아가며 바뀌는 것은 여기에 둔다.
`store.sqlite` 는 뒤의 적재(②)가 자료원마다 표를 더할 그 파일이다 — Django 의 `GSM.db` 에는 넣지 않는다(백업이 부푼다).

누가 쓰나
- **컨테이너의 `fetch_*`·`build_*`** — `apps.py` 가 명령의 `execute` 를 감싸 끝날 때 한 줄을 적는다. 명령은 아는 것을 `note()` 로
  보탠다(`rows`·`expected`·`raw_path` …). 명령 마흔다섯을 하나하나 고치지 않으려고 한 자리에서 감쌌다
- **호스트**(`run.sh` 가 `GSM_RUN_PLACE=host`)는 sqlite 에 쓰지 않는다 — 컨테이너와 한 파일에 쓰지 않게(검토의 "잠금").
  매시 일은 지금처럼 `hourly_status.json` 이 남기고, 사람이 호스트에서 부른 일(ERA5·ECCO2)은 `fetch_log_host.jsonl` 에 한 줄을 덧붙인다.
  컨테이너가 화면·healthz 를 그릴 때 둘을 옮겨 적는다(`sync()`)
"""
import contextlib
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from django.conf import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS fetch_log (
    id               INTEGER PRIMARY KEY,
    source           TEXT NOT NULL,
    command          TEXT NOT NULL DEFAULT '',
    started_at       TEXT NOT NULL,
    seconds          REAL,
    result           TEXT NOT NULL,          -- ok · fail · skip
    note             TEXT NOT NULL DEFAULT '',
    upstream_version TEXT NOT NULL DEFAULT '',
    expected         INTEGER,                -- 상류가 센 수
    rows             INTEGER,                -- 받은(적재한) 수
    changed          INTEGER,
    raw_path         TEXT NOT NULL DEFAULT '',
    raw_sha256       TEXT NOT NULL DEFAULT '',
    built_at         TEXT NOT NULL DEFAULT '',
    built_by         TEXT NOT NULL DEFAULT '',
    estimated        INTEGER NOT NULL DEFAULT 0,  -- 1 이면 지난 것을 파일 stat 으로 어림한 줄
    origin           TEXT NOT NULL DEFAULT 'container',  -- container · hourly · host · backfill · spec
    UNIQUE (source, started_at, origin)
);
CREATE INDEX IF NOT EXISTS fetch_log_source ON fetch_log (source, started_at);
"""

#: 명령이 `note()` 로 보탤 수 있는 칸
FIELDS = ("upstream_version", "expected", "rows", "changed", "raw_path", "raw_sha256", "built_at", "built_by")

_local = threading.local()
_schema_done = set()


def store_path() -> Path:
    return Path(settings.STORE_PATH)


def host_log_path() -> Path:
    return store_path().parent / "fetch_log_host.jsonl"


def hourly_status_path() -> Path:
    return store_path().parent / "hourly_status.json"


def on_host() -> bool:
    return os.environ.get("GSM_RUN_PLACE") == "host"


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


@contextlib.contextmanager
def connect():
    p = store_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(p, timeout=10)
    try:
        if str(p) not in _schema_done:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript(SCHEMA)
            _schema_done.add(str(p))
            try:
                os.chmod(p, 0o664)
            except OSError:
                pass
        yield db
        db.commit()
    finally:
        db.close()


def write(row: dict):
    """한 줄을 적는다. 같은 (자료원·시작한 때·어디서)는 한 번만."""
    cols = ["source", "command", "started_at", "seconds", "result", "note", "estimated", "origin", *FIELDS]
    values = [row.get(c) for c in cols]
    defaults = {"command": "", "note": "", "estimated": 0, "origin": "container", "upstream_version": "",
                "raw_path": "", "raw_sha256": "", "built_at": "", "built_by": ""}
    values = [defaults.get(c) if v is None and c in defaults else v for c, v in zip(cols, values)]
    with connect() as db:
        db.execute(f"INSERT OR IGNORE INTO fetch_log ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", values)


# ── 명령이 끝날 때 ─────────────────────────────────────────────────

def note(**fields):
    """도는 명령이 아는 것을 보탠다 — `fetchlog.note(rows=…, expected=…)`. 기록 중이 아니면 아무 일도 없다."""
    current = getattr(_local, "current", None)
    if current is not None:
        current.update({k: v for k, v in fields.items() if k in FIELDS})


@contextlib.contextmanager
def record(source: str, command: str, schedule: str = "manual"):
    """명령 하나를 감싼다. 끝나면 결과·초·마지막 말을 적는다. 예외는 `fail` 로 적고 다시 던진다.

    기록이 실패해도 명령의 결과를 바꾸지 않는다 — 장부가 일을 막으면 안 된다.
    """
    started, t0 = _now(), time.monotonic()
    extra = {}
    previous = getattr(_local, "current", None)
    _local.current = extra
    tail = _Tail()
    _local.tail = tail
    result, last = "ok", ""
    try:
        yield tail
    except SystemExit as exc:
        result = "ok" if not exc.code else "fail"
        raise
    except BaseException as exc:
        result, last = "fail", f"{type(exc).__name__}: {exc}"[:300]
        raise
    finally:
        _local.current = previous
        row = {"source": source, "command": command, "started_at": started,
               "seconds": round(time.monotonic() - t0, 1), "result": result,
               "note": last or tail.last, **extra}
        try:
            if on_host():
                if schedule != "hourly":          # 매시 일은 hourly_status.json 이 남긴다
                    _append_host(row)
            else:
                write(row)
        except Exception:                         # noqa: BLE001 — 장부가 일을 막으면 안 된다
            pass


class _Tail:
    """명령의 출력을 그대로 넘기며 마지막 빈 줄 아닌 것을 기억한다."""

    def __init__(self, out=None):
        self.out = out
        self.last = ""

    def write(self, text):
        for line in str(text).splitlines():
            if line.strip():
                self.last = line.strip()[:300]
        if self.out is not None:
            return self.out.write(text)
        return len(text)

    def flush(self):
        if self.out is not None and hasattr(self.out, "flush"):
            self.out.flush()

    def isatty(self):
        return bool(self.out is not None and hasattr(self.out, "isatty") and self.out.isatty())


def _append_host(row: dict):
    p = host_log_path()
    line = json.dumps(row, ensure_ascii=False) + "\n"
    with open(p, "a", encoding="utf-8") as fh:            # 한 줄 덧붙이기는 쪼개지지 않는다
        fh.write(line)


# ── 옮겨 적기 ───────────────────────────────────────────────────────

def sync(spec_rows=None) -> int:
    """호스트가 남긴 것(`hourly_status.json`·`fetch_log_host.jsonl`)을 `fetch_log` 로. 옮긴 줄 수."""
    if on_host():
        return 0
    if spec_rows is None:
        from . import sources
        spec_rows = sources.load().rows
    by_command = {c: r for r in spec_rows for c in r.get("commands", [])}
    rows = []
    try:
        jobs = json.loads(hourly_status_path().read_text(encoding="utf-8")).get("jobs") or {}
    except (OSError, ValueError, AttributeError):
        jobs = {}
    for command, job in jobs.items():
        source = by_command.get(command)
        if not source or not isinstance(job, dict) or not job.get("at"):
            continue
        result = {"ok": "ok", "skip": "skip"}.get(job.get("result"), "fail")
        rows.append({"source": source["id"], "command": command, "started_at": job["at"],
                     "seconds": job.get("seconds"), "result": result, "note": str(job.get("note") or "")[:300],
                     "origin": "hourly"})
    try:
        with open(host_log_path(), encoding="utf-8") as fh:
            for line in fh:
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict) and row.get("source") and row.get("started_at"):
                    rows.append({**row, "origin": "host"})
    except OSError:
        pass
    if not rows:
        return 0
    before = _count()
    for row in rows:
        try:
            write(row)
        except sqlite3.Error:
            return 0
    return _count() - before


def _count() -> int:
    try:
        with connect() as db:
            return db.execute("SELECT count(*) FROM fetch_log").fetchone()[0]
    except sqlite3.Error:
        return 0


# ── 읽기 ────────────────────────────────────────────────────────────

def latest() -> dict:
    """자료원마다 마지막 줄과 마지막으로 된(ok) 줄 — {id: {"last": row, "last_ok": row}}."""
    out = {}
    try:
        with connect() as db:
            db.row_factory = sqlite3.Row
            for row in db.execute("SELECT * FROM fetch_log ORDER BY started_at, id"):
                d = dict(row)
                entry = out.setdefault(d["source"], {"last": None, "last_ok": None})
                entry["last"] = d
                if d["result"] in ("ok", "skip"):
                    entry["last_ok"] = d
    except sqlite3.Error:
        return {}
    return out


def history(source: str, limit: int = 20) -> list:
    try:
        with connect() as db:
            db.row_factory = sqlite3.Row
            return [dict(r) for r in db.execute(
                "SELECT * FROM fetch_log WHERE source = ? ORDER BY started_at DESC, id DESC LIMIT ?", (source, limit))]
    except sqlite3.Error:
        return []
