# HANDOFF

이 문서는 **지금 어디까지 왔고 다음이 무엇인지** 한 곳에서 답한다.
왜 그렇게 했는지는 `devlog/`, 무엇이 언제 붙었는지는 `CHANGELOG.md`.

마지막으로 손본 날: **2026-09-27**

## 한 줄

**배포했고, 인증키로 돈다.** `http://paleolab/GSM/` 에 서 있다 (짧은 주소 `/geomap/`).
2026-09-27 에 키가 들어와 임시 스위치를 껐다. 타일·범례는 `/openapi/wms` +
키로, **속성만 GeoServer 로** 받는다 — `/openapi/wms` 가 `GetFeatureInfo` 를
막아 두었기 때문이다 (devlog 006).

키는 `/srv/GSM/db/kigam_key` 에 있다. `/srv/GSM/.env` 는 root 의 것이라 못
고쳐서 설정을 **DB 옆 파일**로도 읽게 해 두었다 —
`kigam_key`·`allowed_hosts`·`dev_direct_wms`·`secret_key`.

## 돌려보는 법

```bash
python -m venv ~/venv/GSM && . ~/venv/GSM/bin/activate
pip install -r requirements.txt
cp .env.template .env            # 아래 "지금의 .env" 를 본다
cd web && python manage.py migrate && python manage.py seed_catalog
python manage.py runserver
```

`http://127.0.0.1:8000/GSM/`.

### 지금의 .env

로컬에서도 키를 채우고 스위치를 끈다. 키가 없으면 `GSM_DEV_DIRECT_WMS=1` 로
돌려볼 수 있다 (화면 맨 위에 띠가 뜬다).

```
GSM_KIGAM_KEY=<받은 키>
GSM_DEV_DIRECT_WMS=0
```

둘의 갈래는 CLAUDE.md 의 "두 개의 상류 주소".

## 무엇이 확인됐나

2026-09-23 에 임시 스위치로, 2026-09-27 에 인증키로 직접 받아본 것들이다.

| | |
|---|---|
| 타일 | 25만 지질도 400×300 PNG 122 KB — 그려진다 |
| 클릭 속성 | 지질시대·도폭·지층명·지질기호·대표암석 — **상류가 한국어 이름으로 준다** |
| 범례 | 223×5218 PNG 48 KB |
| 카탈로그 | `geoOpen` 61 개, 레이어군 8 갈래 |
| 점묶음 | UTF-8 CSV·CP949 CSV·GeoJSON 올라간다. 위경도 열 없으면 까닭을 말한다 |
| 좌표 | 십진도·도분초 오가고, 찍어서 이동하고, 눌러서 복사한다 |
| 시험 | 117 개 다 돈다 (`manage.py test viewer`) |
| 오픈API | 키로 61 개 전부 그려진다. 범례도 된다. **속성은 막혀 있다** (006) |
| 배포 | `http://paleolab/GSM/` 200. 짧은 주소 `/geomap/` 301 |
| 배경지도 | VWorld `Base`·`Satellite`·`Hybrid` 200. 자리 차례는 `z/y/x` (003) |

## 무엇이 아직 아닌가

- **속성이 문서에 없는 주소에 기대고 있다.** `/mgeo/geoserver/wms` 가 닫히면
  클릭 속성이 멈춘다 (타일은 그대로 돈다). 그때는 `kigam.DIRECT_REQUESTS` 를
  보고, `/openapi/wms` 가 열렸는지 다시 찔러본다
- 호출 제한의 실제 수치를 모른다. 문서는 "지나치게 잦은 호출" 이라고만 적었다.
  타일 캐시를 둔 것이 이 때문이다 (브라우저 쪽 하루, 디스크 쪽 30 일·2 GB)
- 운영 DB 의 `Layer.verified_at` 은 아직 비어 있다. 대조는 로컬 DB 에 대고
  했다 — 운영에서 돌리려면 컨테이너 안에서 `python manage.py verify_layers`

## 알아두면 좋은 것

### 상류 문서를 믿지 않는다

안내 페이지의 레이어 목록에 틀린 것이 있다 — 지화학도 12 종이 전부 바나듐으로,
변성암·광상 동위원소가 심성암과 같은 이름으로 적혀 있고, 좋은물지도 15 종은
아예 빠져 있다. 그래서 카탈로그를 표로 두고 `GetCapabilities` 에서 채운다.
자세한 것은 devlog 001.

### KOPRI 망이 TLS 를 가로챈다

`data.kigam.re.kr` 의 인증서 체인 끝이 `CN=KOPRI SSL` 이다. 그 루트는 시스템
꾸러미에만 있고 `requests` 가 보는 certifi 에는 없어서, 그냥 두면 **상류 요청이
전부 `CERTIFICATE_VERIFY_FAILED` 로 멈춘다.** `settings._default_ca_bundle()` 이
시스템 꾸러미를 찾아 쓰고, 컨테이너는 `deploy/ca/` 를 이미지에 넣는다.
ForGIA `deploy/ca/README.md` 가 같은 것을 먼저 겪었다.

**망 밖에서 쓰려면** `deploy/ca/` 를 비우면 된다.

### OpenLayers 를 저장소에 담았다

`web/viewer/static/viewer/vendor/`. CDN 에서 부르지 않는 까닭은 위의 TLS
가로채기와, 형제 저장소(DiaRUGA·ForGIA)에 바깥 링크가 하나도 없다는 집 규칙
둘이다. 판을 올릴 때는 `vendor/README.md` 를 함께 고친다.

### 브라우저는 인증키를 모른다

타일은 `./wms/`, 속성은 `./featureinfo/`, 범례는 `./legend/` 로 부르고, 키는
Django 가 붙인다. `kigam.clean_params()` 가 브라우저가 보낸 `key` 를 **버린다** —
시험(`test_kigam.py`)이 그것을 지킨다.

## 배포한 자리에서 알아둘 것

`/srv/GSM` 은 배포한 사람(root)의 것이라 **`.env` 도 `docker-compose.yml` 도
못 고친다.** 쓸 수 있는 것은 `db/` 와 `tiles/` 뿐이다. 2026-09-23 에 이것이
세 번 걸렸다 — 빈 `SECRET_KEY` 로 기동 실패, `ALLOWED_HOSTS` 에 `paleolab` 이
없어 400, 그리고 임시 스위치.

그래서 설정을 **DB 옆 파일**로도 읽는다.

| 파일 | 하는 일 |
|---|---|
| `secret_key` | 없으면 entrypoint 가 만든다 |
| `allowed_hosts` | 들어와도 되는 이름. 한 줄에 하나 |
| `kigam_key` | 상류 인증키 |
| `dev_direct_wms` | `1` 이면 임시 경로로 간다 |
| `vworld_key` | 배경지도 열쇠. 있으면 고르개에 VWorld 가 오른다 (넣어 두었다) |

환경변수가 있으면 그쪽이 이긴다. 파일은 없어도 된다.

## VWorld 로 더 할 수 있는 것

열쇠 하나로 배경지도 말고도 꽤 된다 — WMS 187 종(단층·지질구조선·수문지질
단위·등산로), 점 하나로 묻는 데이터 API(읍면동·가까운 단층·토박이 지명),
주소↔좌표. **3D 는 권하지 않는다** — Cesium 포크라 딴 화면이어야 하고,
표고를 점 단위로 얻는 창구가 막혀 있다.

쏴 보고 확인한 것과 막힌 것을 devlog 004 에 적었고, 할 일은 TODOs 맨 위에 있다.

## 걸린 것 — 없음

지금 막힌 것은 없다.
