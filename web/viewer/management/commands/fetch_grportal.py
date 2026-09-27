"""그린란드 정부 포털의 점 레이어를 미리 받아 둔다.

    manage.py fetch_grportal              없는 것만 받는다
    manage.py fetch_grportal --refresh    있어도 다시 받아 덮는다

화면에서 처음 켜는 사람이 기다리지 않게 하려는 것이다 — 시료 2 만 점은
열 장, 20 초 남짓 걸린다. 받는 길은 화면이 부르는 것과 같다
(`views.vector_features`). 레이어 사이에 1 초 쉰다 (devlog 010 의 빠르기).
"""
import time

from django.core.management.base import BaseCommand

from viewer import grportal, views


class Command(BaseCommand):
    help = "그린란드 정부 포털의 점 레이어를 캐시에 받아 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--refresh", action="store_true", help="있어도 다시 받는다")

    def handle(self, *args, **options):
        for index, name in enumerate(grportal.LAYERS):
            if index:
                time.sleep(1)
            try:
                data = views.vector_features(name, refresh=options["refresh"])
            except grportal.PortalError as exc:
                self.stdout.write(self.style.ERROR(f"{name}: {exc}"))
                continue
            count = data.count(b'"Feature"')
            self.stdout.write(f"{name}: {count}점, {len(data) // 1024} KB")
