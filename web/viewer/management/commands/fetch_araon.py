"""아라온호의 마지막 자리를 받아 `KOPRI_DIR/araon.jsonl` 에 한 줄 보탠다.

    manage.py fetch_araon

호스트 cron 이 매시간 `/srv/GSM/scripts/run.sh fetch_araon` 으로 부른다(`deploy/host/crontab.GSM`, koprifossillab 005). 한 번에 한 쪽만 받는다. 배가 아직 새 자리를 안
보냈으면(시각이 마지막 줄과 같으면) 보태지 않는다 — 극지에서는 위성 보고가 몇 시간씩 밀리기도 한다.
극지연구소 쪽은 지난 자리를 지워 버리므로, 이 파일이 아라온호 항적의 우리 쪽 기록이다.
"""
from django.core.management.base import BaseCommand, CommandError

from viewer import kopri


class Command(BaseCommand):
    help = "아라온호의 마지막 자리를 받아 쌓는다"

    def handle(self, *args, **options):
        try:
            row = kopri.fetch_araon()
        except kopri.KopriError as exc:
            raise CommandError(str(exc)) from exc
        if kopri.append_araon(row):
            self.stdout.write(f"아라온호 {row['time']} {row['lat']}, {row['lon']}")
        else:
            self.stdout.write(f"아라온호 새 자리 없음 (마지막 {row['time']})")
