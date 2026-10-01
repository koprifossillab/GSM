"""바람 — 구워 둔 u·v 텍스처의 자리와 목록, 그리고 굽기 (koprifossillab P02).

문이 아니다. 받는 것은 `gfs.py`(지금의 바람)·`era5.py`(지난 바람)가 하고, 여기는 받은 격자를 PNG 로 굽고 목록을 적는다.

- **굽기(`encode`)는 호스트에서만 돈다** — numpy 를 쓴다. 운영 이미지에는 numpy 가 없으므로 numpy 는 그 함수 안에서만 부른다.
  컨테이너가 이 모듈에서 쓰는 것은 자리와 목록을 읽는 것뿐이다
- 한 장 = 한 시각·한 높이. 1440×721, **경도 −180→180**, 위도 90→−90(0.25°). 상류(GFS·ERA5)는 둘 다 경도 0 부터라 여기서 돌린다 —
  화면이 다시 돌리지 않게
- R=u, G=v 를 그 장의 최솟값·최댓값으로 0–255 에 담는다. 되돌릴 값은 출처의 `index.json` 에 적는다. B 는 비운다
- 자리 — `<WIND_DIR>/<출처>/<시각>/<높이>.png`, 출처마다 `index.json`. 시각은 GFS 가 `YYYYMMDDHH`, ERA5 가 `YYYYMMDD`(00 UTC)
- GFS 의 시각은 **유효 시각**이다 — 목록 한 줄에 판(`run`)과 예보 시간(`fh`, 0 이 분석)을 함께 적는다. 같은 유효 시각을 여러
  판이 내면 새 판이 이긴다. 그래서 같은 주소의 그림이 바뀔 수 있어 화면은 `?run=` 을 붙여 부른다 (koprifossillab 008)
"""
import io
import json
import os
import re
import shutil
from pathlib import Path

from django.conf import settings

SOURCES = ("gfs", "era5")
LEVELS = ("10m", "250hPa")
WIDTH, HEIGHT = 1440, 721
STAMP = {"gfs": re.compile(r"^\d{10}$"), "era5": re.compile(r"^\d{8}$")}
CREDIT = {
    "gfs": "NOAA/NCEP GFS 0.25° (public domain)",
    "era5": "Contains modified Copernicus Climate Change Service information — ERA5 (Hersbach et al. 2020), CC BY 4.0",
}


def root() -> Path:
    return Path(settings.WIND_DIR)


def png_path(source: str, stamp: str, level: str) -> Path:
    return root() / source / stamp / f"{level}.png"


def valid(source: str, stamp: str, level: str) -> bool:
    return source in SOURCES and level in LEVELS and bool(STAMP[source].match(stamp))


def read_index(source: str) -> dict:
    """출처의 목록. 없거나 깨졌으면 빈 목록."""
    try:
        data = json.loads((root() / source / "index.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data.setdefault("times", [])
    data["source"] = source
    data["credit"] = CREDIT[source]
    return data


def write_index(source: str, times: list) -> None:
    """`times` — `[{"t": 시각, "10m": {"u": [최소, 최대], "v": [...]}, "250hPa": {...}}]`. 시각 차례로 적는다."""
    path = root() / source / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {"source": source, "levels": list(LEVELS), "width": WIDTH, "height": HEIGHT,
            "times": sorted(times, key=lambda e: e["t"])}
    tmp = path.with_suffix(".json.part")
    tmp.write_text(json.dumps(body, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    os.replace(tmp, path)


def encode(u, v) -> tuple:
    """u·v 격자(721×1440, 경도 0 부터) -> (PNG 바이트, {"u": [최소, 최대], "v": [...]}). **호스트에서만** — numpy 를 쓴다."""
    import numpy as np
    from PIL import Image

    u = np.asarray(u, dtype=np.float32).reshape(HEIGHT, WIDTH)
    v = np.asarray(v, dtype=np.float32).reshape(HEIGHT, WIDTH)
    if not (np.isfinite(u).all() and np.isfinite(v).all()):
        raise ValueError("빈 값(NaN)이 섞였다")
    # 경도 0→360 을 −180→180 으로 — 열 720 이 경도 −180 이다
    u = np.roll(u, WIDTH // 2, axis=1)
    v = np.roll(v, WIDTH // 2, axis=1)
    scale = {}
    rgb = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    for i, (name, grid) in enumerate((("u", u), ("v", v))):
        lo, hi = float(grid.min()), float(grid.max())
        span = hi - lo or 1.0
        rgb[..., i] = np.rint((grid - lo) / span * 255).astype(np.uint8)
        scale[name] = [round(lo, 3), round(hi, 3)]
    out = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(out, "PNG", optimize=True)
    return out.getvalue(), scale


def write_time(source: str, stamp: str, fields: dict) -> dict:
    """한 시각의 높이들(`{높이: (u, v)}`)을 굽고, 그 시각의 목록 한 줄을 낸다. 옆 자리에 다 쓴 뒤 바꿔 끼운다."""
    final = root() / source / stamp
    tmp = root() / source / f"{stamp}.part"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    entry = {"t": stamp}
    for level, (u, v) in fields.items():
        png, scale = encode(u, v)
        (tmp / f"{level}.png").write_bytes(png)
        entry[level] = scale
    shutil.rmtree(final, ignore_errors=True)
    os.replace(tmp, final)
    return entry


def prune(source: str, keep: int) -> list:
    """가장 새 `keep` 시각만 남기고 지운다. 지운 시각들."""
    index = read_index(source)
    times = sorted(index["times"], key=lambda e: e["t"])
    gone = [e["t"] for e in times[:-keep]] if keep and len(times) > keep else []
    if gone:
        write_index(source, times[-keep:])
        for stamp in gone:
            shutil.rmtree(root() / source / stamp, ignore_errors=True)
    return gone


def prune_before(source: str, stamp: str) -> list:
    """시각이 `stamp` 보다 앞선 것을 지운다. 지운 시각들."""
    index = read_index(source)
    times = sorted(index["times"], key=lambda e: e["t"])
    gone = [e["t"] for e in times if e["t"] < stamp]
    if gone:
        write_index(source, [e for e in times if e["t"] >= stamp])
        for old in gone:
            shutil.rmtree(root() / source / old, ignore_errors=True)
    return gone
