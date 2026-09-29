# HANDOFF

이 문서는 **지금 어디까지 왔고 다음이 무엇인지** 한 곳에서 답한다.
왜 그렇게 했는지는 `devlog/`, 무엇이 언제 붙었는지는 `CHANGELOG.md`.

마지막으로 손본 날: **2026-09-29**

## 한 줄

**배포했고, 인증키로 돈다.** `http://paleolab/GSM/` 에 서 있다 (짧은 주소 `/geomap/`).
2026-09-27 에 키가 들어와 임시 스위치를 껐다. 타일·범례는 `/openapi/wms` +
키로, **속성만 GeoServer 로** 받는다 — `/openapi/wms` 가 `GetFeatureInfo` 를
막아 두었기 때문이다 (devlog 006).

키는 `/srv/GSM/db/kigam_key` 에 있다. `/srv/GSM/.env` 는 root 의 것이라 못
고쳐서 설정을 **DB 옆 파일**로도 읽게 해 두었다 —
`kigam_key`·`allowed_hosts`·`dev_direct_wms`·`secret_key`.

**v0.5.x 에서 늘어난 것** — 주제도 비교(밀어 보기·나란히, 011), 선·면 GeoJSON 과
잡은 범위를 네모 그대로 저장(모양 `Shape`, 012), 좌표계 고르기(TM·UTM-K·옛 Bessel,
013). 판마다 무엇이 붙었는지는 `CHANGELOG.md`.

**v0.7.0 — 극지** (017–022). 지역이 한국·그린란드·스발바르·얀마옌·남극에 북극
묶음 탭까지 여섯이다. 극지는 극 평사도법(3413·3031)으로 본다. 남극 GeoMAP 과 얀마옌은
**파일을 받아 우리가 그린다** — 파일은 `/srv/GSM/db/geomap/`·`/srv/GSM/db/npolar/`
에 있고 원본은 NAS `N:\GSM\sources\`. 상류(문)가 다섯으로 늘었다 — KIGAM·VWorld·
GEUS·그린란드 정부 포털·NPI.

**v0.8.0 — 일본·동아시아** (024). 일본 지질조사종합센터(GSJ)의 심리스 지질도 V2 를
z/x/y 타일로 중계하고, 한국·일본을 한 화면에 모은 동아시아 묶음 탭을 더했다. 문이
여섯이 되었다(+ GSJ). GSJ 는 열쇠가 없고 파일도 없다.

**v0.9.0 — 중국, 그리고 연구실의 암맥** (025·026). 중국은 USGS geo3al(1:500만)을 **파일로 받아
우리가 그린다** — `/srv/GSM/db/usgs/geo3al/` 에 `geo3al.{shp,dbf,prj}` 를 두면 읽힌다
(원본 NAS `N:\GSM\sources\china\geo3al.zip`). **연구실 내부용이다** — 이용 조건이
가공물까지 재배포를 막아, 파일은 저장소·이미지에 없고 밖에 열 때는 이 레이어를 먼저 내린다.
한국에는 **커스텀 지질도** — phyloserver 암맥 기록(줌 11 아래 도폭별 로즈)과 한반도 지질도
스캔(026). 문이 일곱이 되었다(+ phyloserver, 읽기만 한다). 운영 설정은 없다.

**v0.9.1 — 한반도 지질도 음영판** (027). 좌표가 박힌 QGIS PDF 를 5179 타일로 잘라 두고
화면이 옮겨 그린다 — `db/peninsula/`. PDF 의 좌표는 해안선에 대 고쳐 쓴다. 문이 아니다.

**v0.10.0 — 그림 내려받기, 3D 점묶음, 스발바르 도폭** (028·029). 도구 막대의 "그림" 이 지금
보는 지도를 PNG 한 장으로 내려준다(레이어·축척·출처를 밑에 적는다). 3D(실험)에 점묶음이
얹히고, 켜고 끈 것은 2D 와 함께 기억한다. 스발바르에 1:10만 도폭 스캔과 도폭 경계가 섰다.
절(Age) 이름은 국제지질연대층서표 한글판을 따른다. `prewarm` 이 NPI·GSJ·GeoMAP 을 안다.
밖에 열 때는 `GSM_PUBLIC=1` 하나로 연구실 내부용 레이어가 내려간다. 한반도 지질도 민판(028).

**v0.10.1 — 3D 에 커스텀 지질도** (030). 한반도 지질도 셋(5179·5181 격자)을 서버가 3857 로
다시 펴고(`warp.py`, `/GSM/warp/`), 암맥은 그대로 얹는다. 3D 점묶음에 이름표(글꼴 조각을 담았다).

**v0.11.0 — 시료 고도, 3D 의 일본 지형** (031). 표고로 나가는 문 `elevation.py` — AWS 표고 타일·
국토지리원 표고 타일·PGC. 문이 여덟이다. `Point` 에 표고 칸 셋(이주 0011).

**v0.11.1 — 북극의 3D** (032·033). 위도 60° 너머의 3D 지형을 PGC ArcticDEM 으로(`dem/`).
VWorld 배경은 곧장 닿지 못하면 서버를 거친다(033).

**v0.11.2 — 3D 에도 그림으로 내려받기.** 3D 화면을 PNG 한 장으로, 밑에 자리·출처 띠를 붙인다.

**v0.11.3 — 극지 3D 속도·테마** (034). gunicorn 워커마다 스레드 8, PGC 는 4×4 네모째 받는다.

**v0.11.4 — 남극 3D** (035). REMA 지형에 드로닝모드랜드 지질. GeoMAP 은 아직 3D 에 없다.

**v0.12.0 — 달** (036, P05). 아이콘의 숨은 차림 → `/GSM/moon/`. CesiumJS(`vendor/cesium/`, 14 MB)의 둥근 달에
USGS 달 통합 지질도·LOLA 지형. 문이 아홉이 되었다(+ `trek.py`, NASA Moon Trek). 운영 설정은 없다.

**v0.13.0 — 달 점묶음** (037). `PointSet.body`(이주 0012). 지구 화면은 `earth`, 달 화면은 `moon` 만 읽는다.
달 점묶음의 ⛰ 는 LOLA `getSamples`(GET, 100 점씩 — POST 는 Trek 이 403).

**v0.14.0 — 달을 2D 의 틀로** (038). `moon.html` 이 `map.css` 를 그대로 싣고 `data-region="moon"` 흑백.
구(Cesium)와 평면(OpenLayers, IAU_2015:30110)을 한 화면에 두고 250 km·400 km 문턱으로 오간다. 지질은 오버레이 카드.

**v0.15.0 — 세 세션을 모은 판** (039–043). 달 원도 6 장(`moonmap.py`, 우리가 굽는다 — 운영 `db/moon/moon_originals.sqlite`,
원본 NAS `sources/moon/`), 가구야 고해상 배경, 영상 보정(평면 배경은 WebGLTile), 도구·자세 손잡이, 남극 Esri 위성·3D GeoMAP.
**판은 한 세션이 모아 붙인다** — 다른 세션은 커밋만 하고 커밋 번호·요지를 넘긴다.

**v0.16.0 — 달 기울여 보기, 시대별 범례** (044·045). 이주·운영 파일 없음.

**v0.17.0 — 달 착륙지, 남극 IBCSO** (046·047). 운영 파일 — `/srv/GSM/db/ibcso/tiles-{bed,ice}/`(56 MB, `manage.py build_ibcso`
가 자른 것. 원본 TIFF 는 NAS `sources/ibcso/`). 달 EVA 동선은 저장소의 씨앗 `data/moon_apollo_eva.json`.

**v0.17.1 — 달 그림 내려받기, 남극 기지 단추** (048·049). 이주·운영 파일 없음.

**v0.18.0 — 화성, 3D 상시, 극지연구소 자료, 3D 남극 IBCSO, 달 극 평면** (050–059). 세 세션을 모았다. 이주 0013
(`PointSet.body` 에 `mars`). 화성은 `/GSM/mars/`(`mars.js`·`mars.html` — `moon.*` 을 옮긴 것, 문은 `trek.py` 의 `mars_*`).
새 문 `kopri.py`(연구실 내부용) — 운영 `db/kopri/` 를 `manage.py fetch_kopri` 가 채운다. 3D 남극은 운영
`db/ibcso/{dem,wide}-{bed,ice}/`(460 MB, 판 전에 옮겨 두었다).

**영어판이 있다** (v0.4.0). 설정의 "언어 · Language" 로 고른다. 화면의 글을
고치면 `viewer/i18n.py` 에 영어도 적는다 — CLAUDE.md "영어판", devlog 008.

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
| 시험 | 492 개 다 돈다 (`manage.py test viewer`, 2026-09-29) |
| 오픈API | 키로 61 개 전부 그려진다. 범례도 된다. **속성은 막혀 있다** (006) |
| 배포 | `http://paleolab/GSM/` 200. 짧은 주소 `/geomap/` 301 |
| 배경지도 | VWorld `Base`·`Satellite`·`Hybrid` 200. 자리 차례는 `z/y/x` (003) |

## 무엇이 아직 아닌가

- **속성이 문서에 없는 주소에 기대고 있다.** `/mgeo/geoserver/wms` 가 닫히면
  클릭 속성이 멈춘다 (타일은 그대로 돈다). 그때는 `kigam.DIRECT_REQUESTS` 를
  보고, `/openapi/wms` 가 열렸는지 다시 찔러본다
- 호출 제한의 실제 수치를 모른다. 문서는 "지나치게 잦은 호출" 이라고만 적었다.
  타일 캐시를 둔 것이 이 때문이다 (브라우저 쪽 하루, 디스크 쪽은 지우지 않고 3 년마다 다시 묻는다)
- 운영 DB 의 대조는 2026-09-27 에 끝났다 (61/61). 다시 돌릴 때는
  `docker exec -w /app/web gsm-web-1 python manage.py verify_layers --redo`

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
| `public` | `1` 이면 밖에 연 뷰어 — 연구실 내부용 레이어를 내린다 (029). 지금은 없다 |

환경변수가 있으면 그쪽이 이긴다. 파일은 없어도 된다.

**파일은 `640` 으로 둔다** (`chmod 640`). 컨테이너는 uid 1000 으로 돌고 파일
주인은 1006 이라, 무리(gid 1000)에게 읽기를 열어야 한다. 2026-09-27 에
`kigam_key` 를 `600` 으로 만들었더니 컨테이너가 못 읽어 "인증키가 없다" 띠가
떴다. 설정은 기동할 때 읽으므로 고친 뒤에는 `docker restart gsm-web-1`.

### v0.7.0 을 올릴 때 (2026-09-28)

- 파일 둘은 이미 `db/` 아래 두었다 — compose 를 고칠 일이 없다
  (`db/geomap/ATA_SCAR_GeoMAP_Geology_v2022_08.gpkg` 490 MB,
  `db/npolar/NP_J250_Geologi/*.geojson`)
- 기동할 때 이주 0006–0008 과 씨앗(VWorld 11·포털 4·GeoMAP 5·NPI 5+6·얀마옌 3)이 들어간다
- 올린 뒤 한 번 — `docker exec -w /app/web gsm-web-1 python manage.py fetch_grportal`
  (시료 2 만 점을 미리 받아 둔다. 상류를 천천히 탄다)

### v0.8.0 을 올릴 때 (2026-09-28)

- 새 파일·열쇠가 없다. 기동할 때 이주 0009 와 GSJ 씨앗 5 개가 들어간다
- 운영 장비에서 `gbank.gsj.jp`·`cyberjapandata.gsi.go.jp`(브라우저) 로 나갈 수 있어야 한다

### v0.9.0 을 올릴 때 (2026-09-28)

- 중국 파일은 먼저 두었다 — `db/usgs/geo3al/geo3al.{shp,dbf,prj}` (640). 첫 요청이 3 초 남짓 걸린다
- 기동할 때 이주 0010 과 씨앗(중국 2·커스텀 지질도 2)이 들어간다
- phyloserver 는 IP(`172.16.116.98`)로 부른다 — 컨테이너 안에서 닿는 것을 확인했다(026)

### v0.9.1 을 올릴 때 (2026-09-28)

- 음영판 파일은 먼저 두었다 — `db/peninsula/geomap.pdf` 와 잘라 둔 `db/peninsula/tiles/`
  (2 343 장, 75 MB 가운데 타일 29 MB). 판이 바뀌면 컨테이너 안에서 `manage.py build_peninsula`
- 기동할 때 씨앗(음영판 1)이 들어간다. 이주는 없다

### v0.10.0 을 올릴 때

- 민판 파일을 먼저 둔다 (028) — `db/peninsula/` 에 `geomap_new_5179.{png,pgw}` 와 잘라 둔
  `tiles-plain/`(1 015 장, 6.3 MB). 컨테이너 안에서 `manage.py build_peninsula --layer plain` 을
  돌려도 같다(메모리 2.2 GB·13 초)
- 기동할 때 씨앗(지질 참고 +2 지하수 등치선, 스발바르 +2 도폭 스캔·경계, 민판 +1)이 들어간다. 이주는 없다
- 올린 뒤 한 번 — `docker exec -w /app/web gsm-web-1 python manage.py fetch_grportal`
  (이제 NPI 점·지명·도폭 경계까지 받는다)
- 올린 뒤 한 번 — `docker exec -w /app/web gsm-web-1 python manage.py verify_layers --probe-info`
  (`/openapi/wms` 가 속성을 열었는지. 이 서버에는 키가 없어 못 보았다)
- 올렸다(2026-09-29). VWorld 배경을 깐 "그림" 도 된다. `/openapi/wms` 의 속성은 아직 500 이다

### v0.11.0 을 올릴 때

- 기동할 때 이주 0011(점의 표고 칸 셋)이 들어간다. 씨앗·파일은 없다
- 운영 장비에서 `s3.amazonaws.com`·`cyberjapandata.gsi.go.jp`·`di-pgc.img.arcgis.com` 으로 나갈 수
  있어야 한다 — 이제 서버도 부른다(전에는 브라우저만)

## VWorld 로 더 할 수 있는 것

열쇠 하나로 배경지도 말고도 꽤 된다 — WMS 187 종(단층·지질구조선·수문지질
단위·등산로), 점 하나로 묻는 데이터 API(읍면동·가까운 단층·토박이 지명),
주소↔좌표. **3D 는 권하지 않는다** — Cesium 포크라 딴 화면이어야 하고,
표고를 점 단위로 얻는 창구가 막혀 있다.

쏴 보고 확인한 것과 막힌 것을 devlog 004 에 적었고, 할 일은 TODOs 맨 위에 있다.

## 걸린 것 — 없음

지금 막힌 것은 없다.
