"""IBCSO v2 의 칠한 판(해저면·얼음 위)을 3031 타일로 잘라 둔다 (devlog 047).

    manage.py build_ibcso                   원본이 있는 판을 다 자른다
    manage.py build_ibcso --layer bed       이 판만 자른다

원본은 `<GSM_IBCSO_DIR>/` 에 둔다 — `IBCSO_v2_bed_RGB.tif`·`IBCSO_v2_ice-surface_RGB.tif`
(PANGAEA 937574, 원본은 NAS N:\\GSM\\sources\\ibcso\\). 잘라 둔 것은 `tiles-bed/`·`tiles-ice/` 의
`{z}/{x}/{y}.webp` 다. 새로 자른 것을 옆 자리(`.new`)에 다 쓰고 나서 바꿔 끼운다 — 자르는 동안에도
뷰어는 옛것을 낸다.

원본을 통째로 풀어서 메모리를 몇 GB 쓴다. 다시 부를 일은 판이 바뀔 때뿐이다.
"""
import math
import shutil
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import ibcso


class Command(BaseCommand):
    help = "IBCSO v2 의 칠한 판(해저면·얼음 위)을 남극 3031 타일로 잘라 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--layer", choices=[n.split(":", 1)[1] for n in ibcso.SHEETS],
                            help="이 판만 자른다 (기본: 원본이 있는 판 모두)")

    def handle(self, *args, **options):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None           # 3 억 7 천만 화소 — 폭탄이 아니라 지도다

        sheets = ([ibcso.SHEETS[f"ibcso:{options['layer']}"]] if options["layer"]
                  else list(ibcso.SHEETS.values()))
        jobs = [(s, s.source_file()) for s in sheets]
        missing = [s.source for s, path in jobs if path is None]
        if options["layer"] and missing or not any(path for _, path in jobs):
            raise CommandError(f"원본이 없다 — {', '.join(missing)} 를 {ibcso.root()} 에 둔다 "
                               "(원본은 NAS N:\\GSM\\sources\\ibcso\\, PANGAEA 937574)")
        for sheet, path in jobs:
            if path:
                self._build(sheet, path)

    def _build(self, sheet, path):
        started = time.monotonic()
        try:
            full = ibcso.open_source(path)
        except (OSError, ibcso.IbcsoError) as exc:
            raise CommandError(f"{path} — {exc}") from exc
        self.stdout.write(f"{sheet.name} ← {path}")

        out = sheet.tiles_dir()
        fresh = out.with_name(out.name + ".new")
        shutil.rmtree(fresh, ignore_errors=True)
        written = size = 0
        for z in range(ibcso.MAX_ZOOM, -1, -1):
            # 줌 z 의 한 화소보다 거칠지 않게 원본을 줄여 둔다 — 줄인 것에서 자르면 빠르다
            res = ibcso.geomap.resolution(z) / ibcso.SCALE          # 9354 미터
            factor = max(1, 2 ** int(math.log2(res / ibcso.SOURCE_RES))) if res > ibcso.SOURCE_RES else 1
            level = full if factor == 1 else full.reduce(factor)
            n = 2 ** z
            for x in range(n):
                for y in range(n):
                    tile = ibcso.cut(level, factor, z, x, y)
                    if tile is None:
                        continue                    # 자료 밖 — 서버가 빈 타일을 낸다
                    data = ibcso.encode(tile)
                    target = fresh / str(z) / str(x) / f"{y}.{ibcso.FORMAT}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    written += 1
                    size += len(data)
            self.stdout.write(f"  z{z} — {n}×{n} 칸, 원본 1/{factor}")
            del level

        old = out.with_name(out.name + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if out.exists():
            out.rename(old)
        fresh.rename(out)
        shutil.rmtree(old, ignore_errors=True)
        self.stdout.write(self.style.SUCCESS(
            f"타일 {written} 장, {size / 1024 / 1024:.1f} MB — {out} ({time.monotonic() - started:.0f} 초)"))
