"""보고 싶은 자리의 타일을 **천천히** 미리 받아 둔다.

    manage.py prewarm --bbox 127.25,36.33,127.5,36.5 --zooms 10-15 --dry-run
    manage.py prewarm --around 36.378,127.362 --km 5 --zooms 12-16
    manage.py prewarm --bbox ... --layers L_50K_Geology_Map,L_250K_Geology_Map

**한계를 재지 않고, 누가 봐도 무리가 없는 빠르기로 간다** (devlog 010).

- 기본 **1 초에 한 장.** 사람이 지도를 볼 때 나가는 것보다 느리다
- 한 번에 **최대 2 000 장**(`--max`). 남은 것은 다음에 이어 받는다 — 이미
  받아 둔 타일은 건너뛰므로 같은 명령을 다시 부르면 이어진다
- **차단 조짐이 한 번이라도 보이면 곧장 멈춘다.** 실패가 연달아 3 번이어도
  멈춘다
- 받는 타일은 브라우저가 부르는 것과 **한 글자까지 같다** (`tilegrid.py`).
  그래야 캐시가 맞는다
- **큰 그림 한 장을 받아 잘라 담는다** (`--meta 4` 면 2048 px 한 장 = 타일
  16 장). 호출이 16 분의 1 로 준다. 지질 경계·색·무늬는 따로 받은 타일과
  똑같고, 지명·기호 **글자 자리만** 다르다 — GeoServer 가 그림 한 장 안에서
  글자가 겹치지 않게 놓기 때문이다. 2026-09-27 에 견줘 보니 다른 픽셀이
  1.3~1.6% 였고 모두 글자였다. `--meta 1` 이면 한 장씩 받는다

밤에 돌리려면 cron 에 건다. 이 명령 자체는 시간을 가리지 않는다.
"""
import io
import math
import time

from PIL import Image

from django.core.management.base import BaseCommand, CommandError

from viewer import kigam, tilecache, tilegrid, usage
from viewer.models import Layer

DEFAULT_LAYERS = ["L_50K_Geology_Map"]
#: 큰 그림 한 장을 그려 받는 데 드는 초. 2026-09-27 에 5만 지질도로 쟀다
#: (512 px 0.2 초, 2048 px 1.1 초, 4096 px 2.4 초).
SECONDS_PER_CALL = {1: 0.2, 2: 0.5, 4: 1.1, 8: 2.4}


def parse_zooms(text):
    lo, _, hi = text.partition("-")
    lo, hi = int(lo), int(hi or lo)
    if not (0 <= lo <= hi <= 19):
        raise CommandError("--zooms 는 0~19 사이, 예: 10-15")
    return range(lo, hi + 1)


class Command(BaseCommand):
    help = "보고 싶은 자리의 타일을 천천히 미리 받아 둔다"

    def add_arguments(self, parser):
        area = parser.add_mutually_exclusive_group(required=True)
        area.add_argument("--bbox", help="서,남,동,북 (위경도)")
        area.add_argument("--around", help="위도,경도 — --km 와 함께")
        parser.add_argument("--km", type=float, default=5.0, help="--around 의 반지름")
        parser.add_argument("--zooms", default="10-15")
        parser.add_argument("--layers", default=",".join(DEFAULT_LAYERS))
        parser.add_argument("--meta", type=int, default=4,
                            help="큰 그림 한 변에 타일 몇 장 (1·2·4·8). 4 면 2048 px 에 16 장")
        parser.add_argument("--rate", type=float, default=1.0, help="1 초에 몇 번 묻나 (최대 2)")
        parser.add_argument("--max", type=int, default=2000, help="한 번에 최대 몇 번 묻나")
        parser.add_argument("--dry-run", action="store_true", help="받지 않고 셈만 한다")

    def handle(self, *args, **o):
        bbox = self._bbox(o)
        zooms = parse_zooms(o["zooms"])
        layers = [n.strip() for n in o["layers"].split(",") if n.strip()]
        known = set(Layer.objects.filter(name__in=layers, enabled=True).values_list("name", flat=True))
        unknown = [n for n in layers if n not in known]
        if unknown:
            raise CommandError(f"카탈로그에 없거나 꺼진 레이어: {', '.join(unknown)}")
        rate = min(max(o["rate"], 0.1), 2.0)          # 2 번/초 위로는 올리지 않는다
        meta = o["meta"]
        if meta not in (1, 2, 4, 8):
            raise CommandError("--meta 는 1·2·4·8 가운데 하나")

        # 타일을 meta×meta 블록으로 묶는다. 빠진 타일이 하나라도 있는 블록만 묻는다
        blocks, have, missing = {}, 0, 0
        for layer in layers:
            for z in zooms:
                for _, x, y in tilegrid.tiles_for(bbox, z):
                    key = tilecache.key_for("map", kigam.clean_params(tilegrid.wms_params(layer, z, x, y)))
                    if tilecache.get(key) is None:
                        missing += 1
                        blocks.setdefault((layer, z, x // meta, y // meta), True)
                    else:
                        have += 1
        todo = list(blocks)
        batch = todo[:o["max"]]
        self.stdout.write(
            f"타일 {have + missing:,}장 — 이미 있는 것 {have:,}, 받을 것 {missing:,}. "
            f"큰 그림({512 * meta}px) {len(todo):,}번에 나눠 묻는다. 이번에 {len(batch):,}번, "
            f"약 {math.ceil(len(batch) * max(1 / rate, SECONDS_PER_CALL[meta]) / 60)}분 "
            f"(큰 그림 한 장에 {SECONDS_PER_CALL[meta]:g}초 남짓 걸린다).")
        if o["dry_run"] or not batch:
            return
        if not kigam.has_key():
            raise CommandError("인증키가 없다")

        got = fails = in_a_row = 0
        gap = 1.0 / rate
        for i, (layer, z, bx, by) in enumerate(batch, start=1):
            started = time.monotonic()
            try:
                got += self._fetch_block(layer, z, bx, by, meta)
            except kigam.UpstreamError as exc:
                fails += 1
                in_a_row += 1
                if usage.paused() or "차단" in str(exc):
                    self.stderr.write(self.style.ERROR(f"차단 조짐 — 멈춘다: {exc}"))
                    break
                if in_a_row >= 3:
                    self.stderr.write(self.style.ERROR(f"연달아 3 번 실패 — 멈춘다: {exc}"))
                    break
            else:
                in_a_row = 0
            if i % 50 == 0:
                self.stdout.write(f"  {i:,}/{len(batch):,}번 — 타일 {got:,}장, 실패 {fails}")
            time.sleep(max(0.0, gap - (time.monotonic() - started)))
        self.stdout.write(self.style.SUCCESS(
            f"물은 것 {i:,}번, 담은 타일 {got:,}장, 실패 {fails}번. 남은 블록 {len(todo) - i + fails:,}."))

    def _fetch_block(self, layer, z, bx, by, meta):
        """블록 하나를 큰 그림으로 받아 잘라 담는다. 담은 타일 수를 돌려준다."""
        last = 2 ** z - 1
        x0, y0 = bx * meta, by * meta
        x1, y1 = min(x0 + meta - 1, last), min(y0 + meta - 1, last)
        nx, ny = x1 - x0 + 1, y1 - y0 + 1
        if nx == 1 and ny == 1:
            params = tilegrid.wms_params(layer, z, x0, y0)
        else:
            sw, ne = tilegrid.tile_extent(z, x0, y1), tilegrid.tile_extent(z, x1, y0)
            params = dict(tilegrid.wms_params(layer, z, x0, y0),
                          width=str(512 * nx), height=str(512 * ny),
                          bbox=",".join(tilegrid.js_number(v) for v in (sw[0], sw[1], ne[2], ne[3])))
        content, _ = kigam.get_map(params)
        if nx == 1 and ny == 1:
            pieces = {(x0, y0): content}
        else:
            image = Image.open(io.BytesIO(content))
            pieces = {}
            for dx in range(nx):
                for dy in range(ny):
                    buf = io.BytesIO()
                    image.crop((dx * 512, dy * 512, dx * 512 + 512, dy * 512 + 512)).save(
                        buf, format="PNG", optimize=True)
                    pieces[(x0 + dx, y0 + dy)] = buf.getvalue()
        for (x, y), data in pieces.items():
            key = tilecache.key_for("map", kigam.clean_params(tilegrid.wms_params(layer, z, x, y)))
            tilecache.put(key, data)
        return len(pieces)

    def _bbox(self, o):
        try:
            if o["bbox"]:
                w, s, e, n = (float(v) for v in o["bbox"].split(","))
            else:
                lat, lon = (float(v) for v in o["around"].split(","))
                dlat = o["km"] / 111.0
                dlon = o["km"] / (111.0 * math.cos(math.radians(lat)))
                w, s, e, n = lon - dlon, lat - dlat, lon + dlon, lat + dlat
        except ValueError as exc:
            raise CommandError("범위를 읽지 못했다 — --bbox 서,남,동,북 / --around 위도,경도") from exc
        if not (w < e and s < n):
            raise CommandError("범위가 뒤집혀 있다")
        return w, s, e, n
