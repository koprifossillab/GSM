# GSM — 대돌여지도

한국지질자원연구원 **지오빅데이터 오픈플랫폼** 오픈API 로 지질주제도를 보는 뷰어.

공식 플랫폼과 다른 곳은 넷이다.

- **레이어를 쌓아 본다** — 한 장씩 갈아끼우지 않고, 켜기·순서·투명도를 따로 준다
- **클릭하면 속성이 뜬다** — 그 지점의 지층명·지질시대·대표암석을 바로 읽는다
- **내 좌표를 얹는다** — CSV·GeoJSON 을 올리면 점묶음이 되어 지도 위에 선다
- **좌표가 늘 보인다** — 십진도와 도분초를 오가고, 찍어서 이동하고, 눌러서 복사한다

그리고 한 번 받은 타일은 **우리 디스크에 둔다.** 같은 자리를 다시 볼 때
상류에 묻지 않으니 빠르고, 상류 부담도 그만큼 준다
(`manage.py prune_tiles` 가 나이와 크기로 줄인다).

## 세우기

```bash
python -m venv ~/venv/GSM && . ~/venv/GSM/bin/activate
pip install -r requirements.txt

cp .env.template .env      # GSM_KIGAM_KEY 를 채운다
cd web && python manage.py migrate && python manage.py seed_catalog
python manage.py runserver
```

`http://127.0.0.1:8000/GSM/`.

**인증키가 아직 없어도 돈다.** 타일 자리에 안내가 뜰 뿐, 레이어 패널·좌표
표시·점묶음 업로드는 그대로 쓸 수 있다. 키는
[오픈API 신청](https://data.kigam.re.kr/my-openapi/request/)에서 받는다.

## 자료

| | |
|---|---|
| 상류 | `https://data.kigam.re.kr/openapi/wms` (WMS 1.1.1/1.3.0) |
| 열린 레이어 | `geoOpen` 61 종 — 지질도·지화학도·해저지질도·좋은물지도·동위원소 연대지도 |
| 좌표계 | 화면은 `EPSG:3857`, 자료 입출력은 `EPSG:4326` |
| 배경지도 | OpenStreetMap |

레이어 카탈로그는 상류 `GetCapabilities` 에서 뽑아 `data/kigam_layers.json` 에
두었다. **공식 안내 문서의 레이어 목록에는 틀린 것이 있다** — 자세한 것은
[CLAUDE.md](CLAUDE.md) 의 "상류의 함정" 과 [devlog 001](devlog/20260923_001_kigam-openapi-survey.md).

## 문서

- [CLAUDE.md](CLAUDE.md) — 이름·낱말·구조의 규약
- [HANDOFF.md](HANDOFF.md) — 지금 어디까지 왔고 다음이 무엇인지
- [CHANGELOG.md](CHANGELOG.md) — 판 이력
- [devlog/](devlog/) — 왜 그렇게 했는지

## 라이선스와 자료의 출처

코드는 이 저장소의 라이선스를 따른다. **지도 자료의 저작권은 한국지질자원연구원에
있다** — 이 뷰어는 오픈API 로 받아 그릴 뿐 자료를 재배포하지 않는다.
이용 조건은 [플랫폼 이용약관](https://data.kigam.re.kr/)을 따른다.
