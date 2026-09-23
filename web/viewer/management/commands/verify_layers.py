"""카탈로그의 레이어가 문서화된 주소로 **실제로 그려지는지** 대조한다.

    manage.py verify_layers

씨앗은 문서에 없는 주소(`GetCapabilities`)에서 왔다. 거기 있다고 오픈API 로
열려 있다는 보장이 없어서, 키가 생긴 뒤 한 장씩 받아보고 `Layer.verified_at`
에 날짜를 남긴다. 안 그려지는 레이어는 `enabled=False` 로 내려 레이어 패널에서
치운다 — 눌러도 빈 자리만 뜨는 것을 목록에 두지 않으려는 것이다.

레이어 61 개에 요청 61 번이다. 상류의 이용제한을 생각해 한 장씩 사이를 둔다.
"""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from viewer import kigam
from viewer.models import Layer

#: 한반도 한복판의 작은 상자. 어느 레이어든 걸치도록 넓게 잡지 않는다 —
#: 큰 상자는 상류에 무거운 그림을 그리게 한다.
PROBE_BBOX = "127.0,36.0,127.4,36.4"


class Command(BaseCommand):
    help = "레이어가 /openapi/wms 로 실제로 그려지는지 대조한다"

    def add_arguments(self, parser):
        parser.add_argument("--delay", type=float, default=0.5,
                            help="한 장 사이에 쉬는 초 (기본 0.5)")
        parser.add_argument("--only", default="",
                            help="이 글자가 든 레이어명만 본다")
        parser.add_argument("--redo", action="store_true",
                            help="이미 확인한 것도 다시 본다")

    def handle(self, *args, **options):
        if not kigam.has_key():
            self.stderr.write(self.style.ERROR(
                "인증키가 없다. .env 의 GSM_KIGAM_KEY 를 채운다."))
            return

        layers = Layer.objects.all()
        if options["only"]:
            layers = layers.filter(name__icontains=options["only"])
        if not options["redo"]:
            layers = layers.filter(verified_at__isnull=True)

        total = layers.count()
        if not total:
            self.stdout.write("대조할 레이어가 없다.")
            return
        self.stdout.write(f"{total}개를 대조한다.")

        ok = failed = 0
        for index, layer in enumerate(layers, start=1):
            params = {
                "version": "1.1.1", "layers": layer.name,
                "srs": "EPSG:4326", "bbox": PROBE_BBOX,
                "width": "64", "height": "64",
                "format": "image/png", "transparent": "true",
            }
            try:
                content, _ = kigam.get_map(params)
            except kigam.UpstreamError as exc:
                failed += 1
                layer.enabled = False
                layer.verify_note = str(exc)[:200]
                layer.save(update_fields=["enabled", "verify_note"])
                self.stdout.write(self.style.WARNING(
                    f"  [{index}/{total}] {layer.name} — 안 된다: {exc}"))
            else:
                ok += 1
                layer.verified_at = timezone.now()
                layer.verify_note = f"{len(content)} bytes"
                layer.enabled = True
                layer.save(update_fields=["verified_at", "verify_note", "enabled"])
                self.stdout.write(f"  [{index}/{total}] {layer.name} — 그려진다")
            time.sleep(options["delay"])

        self.stdout.write(self.style.SUCCESS(f"그려지는 것 {ok}, 안 되는 것 {failed}"))
        if failed:
            self.stdout.write(
                "안 되는 것은 enabled=False 로 내렸다. 까닭은 Layer.verify_note 에 있다.")
