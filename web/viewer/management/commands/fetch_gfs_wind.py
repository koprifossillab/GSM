"""지금의 바람 — GFS 의 가장 새 판을 받아 `<WIND_DIR>/gfs/` 에 굽는다 (koprifossillab P02).

    manage.py fetch_gfs_wind              가장 새 판이 이미 있으면 아무것도 하지 않는다
    manage.py fetch_gfs_wind --keep 8     최근 여덟 판만 둔다 (기본)
    manage.py fetch_gfs_wind --cycle 2026100100

**호스트에서 돈다** — ecCodes·numpy 가 cron 의 전용 venv 에만 있다(`requirements-wind.txt`). cron 이 매시 :35 에
`/srv/GSM/scripts/run.sh fetch_gfs_wind` 로 부른다(`deploy/host/crontab.GSM`, koprifossillab 005). 판은 그 시각에서 네 시간 남짓 뒤에 올라오므로 가장 가까운 지난 판부터 차례로 묻고, 처음 받은 판에서 멈춘다.
한 판에 한 번 부른다. **예보는 다음 판이 이긴다** — 쌓지 않고 최근 것만 둔다.
"""
import datetime as dt

from django.core.management.base import BaseCommand, CommandError

from viewer import gfs, wind


class Command(BaseCommand):
    help = "GFS 의 가장 새 판의 바람(10 m·250 hPa)을 받아 굽는다"

    def add_arguments(self, parser):
        parser.add_argument("--cycle", help="이 판만 (YYYYMMDDHH, UTC)")
        parser.add_argument("--keep", type=int, default=8, help="남길 판 수 (기본 8 = 이틀)")

    def handle(self, *args, **opts):
        index = wind.read_index("gfs")
        have = {e["t"] for e in index["times"]}
        cycles = [opts["cycle"]] if opts["cycle"] else gfs.recent_cycles(dt.datetime.now(dt.timezone.utc), 3)
        for cycle in cycles:
            if cycle in have:
                self.stdout.write(f"{cycle} 은 이미 있다 — 할 일 없음")
                return
            try:
                grib = gfs.download(cycle)
            except gfs.GfsError as exc:
                raise CommandError(str(exc)) from exc
            if grib is None:
                self.stdout.write(f"{cycle} 은 아직 올라오지 않았다")
                continue
            try:
                entry = wind.write_time("gfs", cycle, gfs.decode(grib))
            except (gfs.GfsError, ValueError) as exc:
                raise CommandError(f"{cycle}: {exc}") from exc
            times = [e for e in index["times"] if e["t"] != cycle] + [entry]
            wind.write_index("gfs", times)
            gone = wind.prune("gfs", opts["keep"])
            self.stdout.write(f"{cycle} 을 구웠다 ({len(grib) / 1e6:.1f} MB)" + (f" · 지움 {', '.join(gone)}" if gone else ""))
            return
        self.stdout.write("받을 판이 없다")
