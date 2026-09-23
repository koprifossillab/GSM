"""받아온 타일을 디스크에 둔다. 같은 것을 두 번 받지 않으려는 것이다.

**왜 두는가.** 지질도는 잘 바뀌지 않는다 — 5만 지질도의 도폭은 1977 년에
찍힌 것도 그대로다. 그런데 브라우저가 지도를 조금만 움직여도 타일 요청이
수십 개씩 나간다. 상류에 그만큼 다시 묻는 것은 느리고, 이용제한("지나치게
잦은 호출")에도 가깝다. 한 번 받은 것은 우리가 들고 있으면 된다.

**캐시지 보관소가 아니다.** 자료의 주인은 한국지질자원연구원이고 우리는
그리려고 잠깐 들고 있을 뿐이다. 그래서 셋을 지킨다.

1. 나이 제한(`GSM_TILE_CACHE_MAX_AGE_DAYS`, 기본 30 일). 지나면 다시 받는다
2. 크기 제한(`GSM_TILE_CACHE_MAX_BYTES`, 기본 2 GB). `prune_tiles` 가 오래된
   것부터 버린다
3. 받은 그대로만 둔다. 고쳐 쓰거나 다시 내주지 않는다

**열쇠에 상류 주소를 넣지 않는다.** 개발 스위치를 켜고 받은 타일과 인증키로
받은 타일은 같은 그림이다(뒤에 선 GeoServer 가 하나다). 열쇠를 갈라 두면
키가 나온 날 받아둔 것을 전부 버리게 된다.
"""
import hashlib
import logging
import os
import time
from pathlib import Path

from django.conf import settings

log = logging.getLogger(__name__)

#: 열쇠에 넣는 변수. 여기 없는 것은 그림을 바꾸지 않는다고 본다.
#: `key`(인증키)가 빠져 있는 것이 요점이다 — 누가 받았든 같은 그림이다.
KEY_PARAMS = ("layers", "styles", "srs", "crs", "bbox", "width", "height",
              "format", "transparent", "bgcolor", "version", "layer")


def enabled() -> bool:
    return bool(settings.TILE_CACHE_DIR)


def key_for(kind: str, params: dict) -> str:
    """`kind` 는 `map` 이나 `legend`. 둘을 섞지 않으려고 둔다."""
    parts = [kind]
    for name in KEY_PARAMS:
        value = params.get(name)
        if value not in (None, ""):
            parts.append(f"{name}={str(value).strip().lower()}")
    return hashlib.sha256("&".join(parts).encode("utf-8")).hexdigest()


def _path(key: str) -> Path:
    # 두 자씩 두 번 갈라 담는다. 한 디렉토리에 수십만 개가 쌓이면
    # 디렉토리 읽기 자체가 느려진다.
    root = Path(settings.TILE_CACHE_DIR)
    return root / key[:2] / key[2:4] / f"{key}.png"


def get(key: str):
    """들고 있으면 바이트를, 없거나 늙었으면 None."""
    if not enabled():
        return None
    path = _path(key)
    try:
        stat = path.stat()
    except OSError:
        return None

    max_age = settings.TILE_CACHE_MAX_AGE_DAYS * 86400
    if max_age > 0 and (time.time() - stat.st_mtime) > max_age:
        return None                     # 늙었다. 지우지는 않는다 — prune 의 몫이다

    try:
        data = path.read_bytes()
    except OSError:
        return None
    if not data:
        return None

    # 언제 마지막으로 쓰였는지 남긴다. prune 이 이것을 보고 고른다.
    try:
        os.utime(path, (time.time(), stat.st_mtime))
    except OSError:
        pass
    return data


def put(key: str, content: bytes) -> None:
    """디스크가 꽉 차거나 권한이 없어도 **멈추지 않는다** — 캐시는 덤이다."""
    if not enabled() or not content:
        return
    path = _path(key)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # 반쯤 쓰다 만 파일을 읽는 일이 없도록 옆에 쓰고 옮긴다
        tmp = path.with_suffix(".part")
        tmp.write_bytes(content)
        tmp.replace(path)
    except OSError as exc:
        log.warning("타일을 캐시에 두지 못했다 (%s): %s", key[:12], exc)


def stats() -> dict:
    """`prune_tiles` 와 시험이 쓴다."""
    if not enabled():
        return {"enabled": False, "count": 0, "bytes": 0}
    count = total = 0
    for path in Path(settings.TILE_CACHE_DIR).rglob("*.png"):
        try:
            total += path.stat().st_size
            count += 1
        except OSError:
            continue
    return {"enabled": True, "count": count, "bytes": total}


def prune(max_bytes: int = None, max_age_days: int = None) -> dict:
    """늙은 것을 먼저 버리고, 그래도 크면 **오래 안 쓰인 것부터** 버린다.

    지운 뒤의 수와 크기를 돌려준다.
    """
    if not enabled():
        return {"removed_age": 0, "removed_size": 0, "count": 0, "bytes": 0}

    max_bytes = settings.TILE_CACHE_MAX_BYTES if max_bytes is None else max_bytes
    max_age_days = (settings.TILE_CACHE_MAX_AGE_DAYS
                    if max_age_days is None else max_age_days)

    entries, now = [], time.time()
    for path in Path(settings.TILE_CACHE_DIR).rglob("*.png"):
        try:
            stat = path.stat()
        except OSError:
            continue
        entries.append((path, stat.st_size, stat.st_atime, stat.st_mtime))

    removed_age = 0
    if max_age_days > 0:
        limit = max_age_days * 86400
        keep = []
        for entry in entries:
            if (now - entry[3]) > limit:
                _unlink(entry[0])
                removed_age += 1
            else:
                keep.append(entry)
        entries = keep

    total = sum(e[1] for e in entries)
    removed_size = 0
    if max_bytes > 0 and total > max_bytes:
        entries.sort(key=lambda e: e[2])        # 오래 안 쓰인 것이 앞
        for path, size, _, _ in entries:
            if total <= max_bytes:
                break
            _unlink(path)
            total -= size
            removed_size += 1

    after = stats()
    return {"removed_age": removed_age, "removed_size": removed_size,
            "count": after["count"], "bytes": after["bytes"]}


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except OSError:
        pass
