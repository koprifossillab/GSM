"""한반도 지질도 음영판을 5179 타일로 잘라 둔다 (devlog 027).

    manage.py build_peninsula                   <GSM_PENINSULA_DIR>/*.pdf 를 자른다
    manage.py build_peninsula --pdf 다른.pdf    이 PDF 를 자른다

잘라 둔 것은 `<GSM_PENINSULA_DIR>/tiles/{z}/{x}/{y}.webp` 다. 새로 자른 것을
옆 자리(`tiles.new`)에 다 쓰고 나서 바꿔 끼운다 — 자르는 동안에도 뷰어는 옛것을 낸다.

원본을 통째로 풀어서 **메모리를 3.5 GB 쓴다** (2026-09-28 에 쟀다, 24 초). 서버가 빠듯하면 다른 곳에서
잘라 `tiles/` 만 옮겨도 된다. 한 번 자르면 다시 부를 일은 판이 바뀔 때뿐이다.
"""
import io
import shutil
import time

from django.core.management.base import BaseCommand, CommandError

from viewer import peninsula


class Command(BaseCommand):
    help = "한반도 지질도 음영판(PDF)을 타일로 잘라 둔다"

    def add_arguments(self, parser):
        parser.add_argument("--pdf", help="잘라 낼 PDF (기본: GSM_PENINSULA_DIR 의 PDF)")

    def handle(self, *args, **options):
        from PIL import Image
        Image.MAX_IMAGE_PIXELS = None           # 1 억 7 천만 화소 — 폭탄이 아니라 지도다

        path = options["pdf"] or peninsula.source_file()
        if not path:
            raise CommandError(f"PDF 가 없다 — {peninsula.root()} 에 둔다 (원본은 NAS N:\\GSM\\sources\\)")
        started = time.monotonic()
        try:
            with open(path, "rb") as fh:
                jpeg, epsg, corners = peninsula.read_pdf(fh.read())
            peninsula.check_corners(epsg, corners)
        except (OSError, peninsula.PeninsulaError) as exc:
            raise CommandError(str(exc)) from exc

        image = Image.open(io.BytesIO(jpeg))
        if image.size != (peninsula.WIDTH, peninsula.HEIGHT):
            raise CommandError(f"그림이 {image.size} 다 — {peninsula.WIDTH}×{peninsula.HEIGHT} 를 기다렸다")
        self.stdout.write(f"{path} — {image.size[0]}×{image.size[1]}, EPSG:{epsg}")
        # 흰 바탕을 투명하게 하고, 줄일 때 가장자리가 희게 번지지 않게 미리 곱해 둔다
        full = peninsula.transparent_white(image).convert("RGBa")
        del image

        out = peninsula.tiles_dir()
        fresh = out.with_name(out.name + ".new")
        shutil.rmtree(fresh, ignore_errors=True)
        written = size = 0
        for z in range(peninsula.MAX_ZOOM, -1, -1):
            factor = 2 ** (peninsula.MAX_ZOOM - z)
            level = full if factor == 1 else full.reduce(factor)
            cols, rows = peninsula.grid_size(z)
            for x in range(cols):
                for y in range(rows):
                    tile = peninsula.cut(level, factor, z, x, y)
                    if tile is None:
                        continue                    # 다 투명하다 — 서버가 빈 타일을 낸다
                    data = peninsula.encode(tile)
                    target = fresh / str(z) / str(x) / f"{y}.{peninsula.FORMAT}"
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(data)
                    written += 1
                    size += len(data)
            self.stdout.write(f"  z{z} — {cols}×{rows} 칸")

        old = out.with_name(out.name + ".old")
        shutil.rmtree(old, ignore_errors=True)
        if out.exists():
            out.rename(old)
        fresh.rename(out)
        shutil.rmtree(old, ignore_errors=True)
        self.stdout.write(self.style.SUCCESS(
            f"타일 {written} 장, {size / 1024 / 1024:.1f} MB — {out} ({time.monotonic() - started:.0f} 초)"))
