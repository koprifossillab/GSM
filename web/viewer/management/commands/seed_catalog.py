"""레이어 카탈로그를 씨앗에서 채운다.

    manage.py seed_catalog                  저장소에 든 씨앗으로 (평소)
    manage.py seed_catalog --from-upstream  상류에서 다시 뽑아 씨앗도 갱신

**사람이 손질한 것을 덮지 않는다.** 이미 있는 레이어는 제목·레이어군·차례를
건드리지 않고 범위(bbox)와 설명만 새로 받는다. 상류가 준 제목이 마음에
안 들어 고쳐 둔 것을 다시 뽑을 때마다 되돌리면 손질할 마음이 안 난다.
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from viewer import catalog, kigam
from viewer.models import Layer, LayerGroup


class Command(BaseCommand):
    help = "레이어 카탈로그를 씨앗에서 채운다"

    def add_arguments(self, parser):
        parser.add_argument(
            "--from-upstream", action="store_true",
            help="상류 GetCapabilities 에서 다시 뽑는다 (문서에 없는 주소를 탄다)")
        parser.add_argument(
            "--reset-titles", action="store_true",
            help="사람이 손질한 제목까지 상류 것으로 되돌린다")

    def handle(self, *args, **options):
        if options["from_upstream"]:
            seed = self._from_upstream()
        else:
            seed = self._from_file()

        order = seed.get("레이어군순서") or catalog.GROUP_ORDER
        layers = seed.get("레이어") or []
        if not layers:
            raise CommandError("씨앗에 레이어가 없다")

        made, touched = self._apply(layers, order, options["reset_titles"])

        self.stdout.write(self.style.SUCCESS(
            f"카탈로그 {len(layers)}개 — 새로 생긴 것 {made}, 손본 것 {touched}"))
        unverified = Layer.objects.filter(verified_at__isnull=True).count()
        if unverified:
            self.stdout.write(
                f"아직 /openapi/wms 로 확인하지 않은 레이어 {unverified}개. "
                "인증키가 생기면 `verify_layers` 로 대조한다.")

    def _from_file(self) -> dict:
        path = settings.CATALOG_SEED
        if not path.exists():
            raise CommandError(
                f"씨앗이 없다: {path}\n"
                "상류에서 뽑으려면 --from-upstream 을 준다.")
        return json.loads(path.read_text(encoding="utf-8"))

    def _from_upstream(self) -> dict:
        self.stdout.write(self.style.WARNING(
            "문서에 없는 주소로 씨앗을 뽑는다 — CLAUDE.md '두 개의 상류 주소'"))
        try:
            xml = kigam.fetch_capabilities()
        except kigam.UpstreamError as exc:
            raise CommandError(str(exc)) from exc

        seed = catalog.parse(xml)
        path = settings.CATALOG_SEED
        path.parent.mkdir(parents=True, exist_ok=True)
        keep = {}
        if path.exists():
            old = json.loads(path.read_text(encoding="utf-8"))
            keep = {k: v for k, v in old.items() if k.startswith("_")}
        keep["_뽑은날"] = _today()
        keep["_출처"] = settings.CAPABILITIES_URL
        path.write_text(json.dumps({**keep, **seed}, ensure_ascii=False, indent=1),
                        encoding="utf-8")
        self.stdout.write(f"씨앗을 새로 적었다: {path}")
        return seed

    @transaction.atomic
    def _apply(self, layers, order, reset_titles):
        groups = {}
        for index, name in enumerate(order):
            group, _ = LayerGroup.objects.get_or_create(
                name=name, defaults={"order": index})
            if group.order != index:
                group.order = index
                group.save(update_fields=["order"])
            groups[name] = group

        made = touched = 0
        for index, row in enumerate(layers):
            group = groups.get(row["group"]) or LayerGroup.objects.get_or_create(
                name=row["group"], defaults={"order": len(groups)})[0]
            groups.setdefault(row["group"], group)

            bbox = row.get("bbox") or [None] * 4
            fields = {
                "abstract": row.get("abstract") or "",
                "bbox_west": bbox[0], "bbox_south": bbox[1],
                "bbox_east": bbox[2], "bbox_north": bbox[3],
            }
            layer = Layer.objects.filter(name=row["name"]).first()
            if layer is None:
                Layer.objects.create(
                    name=row["name"],
                    title=row.get("title") or row["name"],
                    group=group, order=index, **fields)
                made += 1
                continue

            # 사람이 손질한 자리는 그대로 둔다
            if reset_titles and row.get("title"):
                fields["title"] = row["title"]
            for key, value in fields.items():
                setattr(layer, key, value)
            layer.save()
            touched += 1
        return made, touched


def _today() -> str:
    from django.utils import timezone
    return timezone.localdate().isoformat()
