"""달 지명을 Moon Trek 색인에서 받아 `data/moon_places.json` 에 적는다 (devlog 036).

IAU 행성 지명 사전을 Trek 이 옮겨 둔 것과 착륙지 북마크다. 달 화면의 찾기 칸이 이 파일을
뒤진다 — 상류를 날마다 타지 않는다. 지명은 거의 바뀌지 않으니 **사람이 가끔 부른다.**
저장소에 담는다(수백 KB, 공개 영역인 IAU 이름).
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from viewer import trek


class Command(BaseCommand):
    help = "달 지명을 Moon Trek 에서 받아 data/moon_places.json 에 적는다"

    def add_arguments(self, parser):
        parser.add_argument("--out", default=str(settings.MOON_PLACES_FILE))

    def handle(self, *args, **o):
        try:
            places = trek.fetch_places()
        except trek.TrekError as exc:
            raise CommandError(str(exc))
        if len(places) < 1000:
            raise CommandError(f"지명이 {len(places)} 개뿐이다 — 상류가 이상하다. 적지 않는다")
        out = Path(o["out"])
        out.write_text(json.dumps({
            "source": "NASA Moon Trek index (IAU Gazetteer of Planetary Nomenclature, landing sites)",
            "fetched": timezone.localdate().isoformat(),
            "columns": ["name", "kind", "lon", "lat"],
            "places": places,
        }, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
        self.stdout.write(f"지명 {len(places)} 개를 {out} 에 적었다")
