"""인증키가 없을 때 타일 자리에 띄우는 안내.

키 심사를 기다리는 동안에도 레이어 패널·좌표·점묶음을 만들고 볼 수 있어야
해서 둔다. 빈 화면 대신 까닭이 적힌 타일이 뜬다.
"""
import io

from PIL import Image, ImageDraw

_BG = (248, 246, 242, 235)
_LINE = (176, 166, 152, 255)
_TEXT = (92, 84, 74, 255)


def notice_tile(width: int, height: int, message: str) -> bytes:
    width = max(1, min(width, 4096))
    height = max(1, min(height, 4096))
    img = Image.new("RGBA", (width, height), _BG)
    draw = ImageDraw.Draw(img)

    # 빗금 — 여기가 자료가 아니라 안내임을 한눈에 알리려는 것
    step = 24
    for x in range(-height, width, step):
        draw.line([(x, height), (x + height, 0)], fill=_LINE, width=1)

    if width >= 180 and height >= 60:
        box = (8, height // 2 - 20, width - 8, height // 2 + 20)
        draw.rectangle(box, fill=(255, 255, 255, 236), outline=_LINE)
        draw.text((18, height // 2 - 8), message, fill=_TEXT)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
