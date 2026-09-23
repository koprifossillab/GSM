"""인증키가 없을 때 타일 자리에 띄우는 안내.

키 심사를 기다리는 동안에도 레이어 패널·좌표·점묶음을 만들고 볼 수 있어야
해서 둔다. 빈 화면 대신 까닭이 적힌 타일이 뜬다.

**글자는 로마자로 적는다.** 이 저장소는 화면 문구를 한국어로 쓰지만 여기만
예외다 — 컨테이너 이미지(`python:3.12-slim`)에 폰트가 하나도 없어서 PIL 의
기본 글꼴로 한글을 그리면 **네모가 줄줄이 찍힌다.** 2026-09-23 첫 배포
화면이 그랬다.

글꼴을 이미지에 넣는 길도 있지만 한글 글꼴 하나가 웬만한 이미지 층보다
크고, **까닭은 이미 한국어로 옆에 적혀 있다** — 레이어 패널 위의 안내 띠가
그것이다(`templates/viewer/map.html` 의 `.warn`). 타일의 글자는 "여기가
자료가 아니라 안내" 임을 알리는 표지면 된다.
"""
import io

from PIL import Image, ImageDraw

_BG = (248, 246, 242, 235)
_LINE = (176, 166, 152, 255)
_TEXT = (92, 84, 74, 255)

#: 타일에 적는 말. 한글을 쓰지 않는 까닭은 이 파일 머리에 적었다.
NO_KEY = "GSM: no API key"
NO_MAP = "GSM: upstream gave no map"


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
