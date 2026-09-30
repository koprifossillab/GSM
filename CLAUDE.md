# CLAUDE.md

한국지질자원연구원 **지오빅데이터 오픈플랫폼**(data.kigam.re.kr)의 오픈API를 받아
지질주제도를 겹쳐 보고, 클릭해 속성을 읽고, 내 좌표 자료를 얹는 지도뷰어.
문서는 한국어로 쓴다 — 커밋 메시지, devlog, 주석 모두.

**DiaRUGA·ForGIA 와 자료를 나누지 않는다.** 저장소도 DB도 배포도 따로다.
다만 **말을 고르는 규칙과 devlog 규약은 그쪽에서 물려받는다** — 같은 사람이
읽을 문서이기 때문이다. 훗날 시추 지점을 지도에 올리고 싶어지면 그때
`Locality.lat/lon` 을 내보내 `PointSet` 으로 받는다. 지금은 다리를 놓지 않는다.

## 이름

**뷰어의 이름은 `GSM` 이다.** 표기는 이 하나뿐 — `Gsm`·`gsm` 으로 쓰지 않는다.
저장소·경로(`~/projects/GSM`·`~/venv/GSM`)·URL(`/GSM/`)·DB(`GSM.db`)가 전부
`GSM` 이다. **기술이 소문자를 강제하는 자리만 `gsm`** — 파이썬 패키지(`gsmweb`),
Docker Hub 이미지(`koprifossillab/gsm`), 브라우저 `localStorage` 키.
환경변수는 `GSM_*`.

약자의 풀이는 **GreatStoneMap** 이고, **한국어 자리의 이름은 `대돌여지도`** 다
(대동여지도에 돌을 끼웠다). 화면 제목·`<title>`·README 첫 줄이 그 자리다.
**길게 쓸지 짧게 쓸지는 자리가 정한다.** 자리가 넉넉하면 풀어 쓰고
(`대돌여지도` · `GREAT STONE MAP`), 좁으면 `GSM` 으로 줄인다. 따로 막는
규칙은 두지 않는다.

## 말을 고르는 규칙

**DiaRUGA 의 규칙 그대로다.** 한 낱말이 두 뜻을 겸하지 않게 한다.

| 뜻 | 쓰는 말 |
|---|---|
| 돌다 말고 멈추다 | **멈춘다** |
| 임포트·설정이 성립하다 | **돈다** |
| 경고·띠가 나타나다 | **뜬다** |
| 행·개체가 만들어지다 | **생긴다** |

이 저장소가 더하는 것 — **지도 낱말은 상류(KIGAM)의 말을 따른다.**

| 뜻 | 쓰는 말 | 쓰지 않는 말 |
|---|---|---|
| WMS 가 돌려주는 지도 한 장 | **타일** | 이미지, 그림 |
| 겹쳐 그리는 한 겹 | **레이어** | 계층, 층 |
| 레이어를 묶은 것 | **레이어군** | 그룹, 카테고리 |
| 사용자가 올린 좌표 묶음 | **점묶음**(`PointSet`) | 마커, 포인트셋 |
| 점묶음에 든 선·면 하나 | **모양**(`Shape`) | 도형, 피처 |
| 클릭해 읽은 속성 | **속성** | 정보, 피처 |
| 지도의 보이는 범위 | **범위**(bbox) | 영역, 뷰포트 |

`층`은 **자료의 층**(권역>지역>지점)에만 쓴다 — DiaRUGA 가 그렇게 쓴다.
지도에서 겹치는 것은 언제나 **레이어**다.

## 자료의 층

```
레이어군   지질도 / 지화학도 / 해저지질도 …        LayerGroup
 └ 레이어    25만 지질도 (L_250K_Geology_Map)      Layer     ← 상류가 주는 것
점묶음     내가 올린 CSV·GeoJSON 하나              PointSet  ← 내가 만드는 것
 ├ 점        위경도 하나 + 딸린 속성                Point
 └ 모양      선·면 하나 (GeoJSON 그대로)            Shape
```

점과 모양을 가른 것은 **점은 위경도 하나**라는 뜻을 지키려는 것이다. 모양은
올린 GeoJSON 의 선·면, 잡아 둔 범위, 잰 선·면에서 온다. 이름은 여전히
점묶음이다 — 올린 것 대부분이 점이다.

**둘은 섞이지 않는다.** 레이어는 상류에서 카탈로그로 받아 채우는 것이라
사람이 손으로 만들지 않고(한글 제목 손질만 한다), 점묶음은 전부 내 것이라
상류를 타지 않는다. 화면에서만 같은 레이어 패널에 나란히 선다.

## 인증키

**인증키는 브라우저에 절대 내보내지 않는다.** 이것이 이 저장소에 서버가
있는 이유다. 브라우저는 `/GSM/wms/` 를 부르고, Django 가 거기에 키를 붙여
상류 `/openapi/wms` 로 넘긴다.

- 키는 `GSM_KIGAM_KEY` 환경변수로만 들어온다. `.env` 는 커밋하지 않는다
- **키를 로그에 적지 않는다.** 상류 URL 을 로그로 남길 때는 `key=…` 를 지운다
  (`viewer/kigam.py` 의 `redact()` 하나가 그 일을 한다)
- 키가 없어도 뷰어는 **돈다** — 타일 자리에 "인증키가 없다" 안내 타일이 뜨고
  레이어 패널·좌표 표시·점묶음은 그대로 쓸 수 있다. 키 신청이 심사 중인
  동안 나머지를 만들려고 그렇게 했다

## 상류의 함정 — 문서를 믿지 않는다

오픈API 안내 문서(`/guide/openapi`)와 레이어 목록 페이지에 **틀린 것이 있다.**
2026-09-23 에 `GetCapabilities` 와 대조해 확인했다 (devlog 001).

- 레이어 목록 페이지가 지화학도 12 종을 전부 `L_geochemMP_V`(바나듐)로 적었다.
  실제로는 `L_geochemMP_ZN`(아연)·`_CU`(구리)·`_FE2O3`(철)·`_PB`(납)·`_CAO`(칼슘)
  처럼 다 다르다
- 변성암 동위원소는 `L_1M_isotope_plutonic` 이 아니라 `L_1M_isotope_metamorphic`,
  광상은 `L_1M_isotope_ore` 다
- 문서에 아예 없는 레이어가 15 개 있다 — 좋은물지도 14 종과 수원정보

**그래서 레이어 카탈로그를 표로 둔다.** 사람이 문서를 보고 옮겨 적지 않는다.
`GetCapabilities` 가 준 것을 씨앗으로 넣고(`data/kigam_layers.json`),
한글 제목과 레이어군만 사람이 손질한다.

## 두 개의 상류 주소 — 갈라 쓴다

| 주소 | 쓰는 자리 | 키 |
|---|---|---|
| `/openapi/wms` | **제품이 도는 길** (`GetMap`·`GetLegendGraphic`) | 필요 |
| `/mgeo/geoserver/wms` | **속성**(`GetFeatureInfo`), 씨앗 뽑기, 개발 스위치를 켰을 때 | 없어도 된다 |

아래쪽은 **문서에 없는 주소다.** 오픈API 예제 소스에 주석으로 남아 있던 것을
보고 알았다. 키를 묻지 않고 `GetMap`·`GetFeatureInfo`·`GetLegendGraphic`
·`GetCapabilities` 를 다 준다.

**뚫은 것은 아니다.** 플랫폼이 자기 지도 페이지에 쓰는 타일 소스와 같은
계열이다 — `/gives/mapService/serviceInfo.do` 가 `{"store":"GeoEnv",
"url":"../geoserver"}` 를 내려주고 그 페이지의 OpenLayers 가 키 없이 타일을
받아간다. 즉 **인증키는 자료를 감추려는 것이 아니라 프로그램 접근을 식별하고
계량하는 공식 창구다.** 이용제한("지나치게 잦은 호출") 조항이 거기 걸려 있다.

그래서 이렇게 갈랐다.

- **제자리는 `/openapi/wms` + 인증키다.** 식별되는 쪽으로 나가는 것이 옳고,
  문서에 없는 주소는 예고 없이 닫혀도 할 말이 없다. 요청의 대부분인 타일이
  이 길로 간다
- **속성만은 GeoServer 로 간다.** 2026-09-27 에 키를 받아 대조하니
  `/openapi/wms` 가 `GetFeatureInfo` 를 막아 두었다(500, devlog 006). 문서의
  "`REQUEST=GetMap` 고정" 이 그 뜻이었다. 속성을 못 읽는 뷰어는 반쪽이라
  이것만 갈랐다. 이 길에는 **키를 붙이지 않는다** — 묻지 않는 곳에 흘릴 까닭이
  없다. 갈림은 `kigam.DIRECT_REQUESTS` 한 줄이고, `/openapi/wms` 가 열어주면
  거기서 지운다
- `GSM_DEV_DIRECT_WMS=1` 은 **인증키가 없을 때의 임시 조치다.** 켜면 모든
  상류 요청이 GeoServer 로 곧장 가고 화면 맨 위에 띠가 뜬다
  (`map.html` 의 `.warn.direct`). 기본값은 꺼짐이다. 2026-09-23~27 에는
  배포본에서 켜 두었고, 키가 들어와 껐다
- 씨앗 뽑기(`seed_catalog --from-upstream`)는 사람이 직접 부를 때만 간다.
  평소의 씨앗은 저장소에 든 `data/kigam_layers.json` 이다

받아둔 타일은 길이 바뀌어도 **버리지 않아도 된다** — 캐시 열쇠에 상류 주소가
안 들어가고, 두 길이 같은 GeoServer 를 보므로 같은 그림이다 (`tilecache.py`).

GeoServer 로 갈 때는 레이어명에 워크스페이스 접두사(`geoOpen:`)가 붙는다 —
GeoServer 는 그것을 요구하고 `/openapi/wms` 는 접두사 없는 이름을 받는다.
그 갈림은 `kigam._endpoint()` 와 `kigam._qualify()` 둘이 맡는다.

문서화된 `/openapi/wms` 는 `GetCapabilities` 를 막아놨다(400). 그래서 카탈로그를
제품 스스로 새로 고칠 길이 지금은 없다. 대신 `manage.py verify_layers` 가
레이어를 한 장씩 받아보고 `Layer.verified_at` 에 남긴다 — 2026-09-27 에 61 개
전부 그려졌다.

**상류 방화벽은 curl 의 User-Agent 를 막는다**(400 `Request Blocked`). 손으로
찔러볼 때는 `curl -A 'GSM/0.1'` 을 붙인다. 코드는 늘 `GSM/0.1` 을 보낸다.

## 받아온 것의 순위 — 새 것이 이긴다

타일은 세 곳에서 올 수 있다. 부딪히면 **위가 이긴다.**

1. **방금 상류에서 받은 것** (`/openapi/wms` + 인증키)
2. **우리 캐시에 있던 것** (`viewer/tilecache.py`)
3. 옆 저장소에서 옮겨온 것 — **지금은 없다.** 앞으로도 1·2 를 덮지 않는다

까닭 둘.

- **새 것이 더 나중이다.** 상류가 판을 올리면 우리 것은 따라가지만, 옮겨온
  것은 옮겨온 그날에 멈춰 있다
- **받아온 길이 다르다.** 우리는 제품이 도는 길을 `/openapi/wms` + 인증키
  하나로 묶어 두었다. 다른 길로 받은 것을 섞으면 "이 타일이 어느 길로 왔나" 를
  나중에 답할 수 없다

2026-09-23 에 phyloserver 의 지질도 캐시(789 MB)를 가져올지 견주고
**안 가져오기로 했다** — 지질 폴리곤은 같은데 주향·경사·단층·지명이 빠진
2015 년 판이었다. 자세한 것은 devlog 002. (002 가 "5만 원도 스캔" 이라 적은
`uploads/geolmap` 은 원도가 아니라 한반도 지질도 한 장이었다 — 026)

**받아온 것은 계속 보탠다** (2026-09-27, devlog 007). 타일·범례·속성을
모두 캐시에 담고 스스로 지우지 않는다 — 다음에 같은 자리를 볼 때 상류를
타지 않게 하려는 것이다. 그래도 위의 순위는 지킨다. 3 년이 지난 것은
**상류에 다시 묻고 새 것으로 덮으며**, 상류가 못 줄 때만 옛것을 낸다.
디스크 여유가 5 GB 밑이면 더 담지 않는다.

**미리 데우기(`manage.py prewarm`)는 천천히 간다** — 1 초에 한 번, 차단
조짐이면 멈춘다. **호출 제한을 재려고 두드리지 않는다.** 재다 걸리면 서버
IP 가 막혀 모든 것이 멈춘다 (devlog 010). 얼마나 묻는지는
`manage.py upstream_stats` 로 지켜본다. 받는 타일은 브라우저가 부르는 것과
**한 글자까지 같아야** 캐시가 맞는다 — 상류마다 꼴이 달라(3857 WMS·극지 투영
WMS·z/x/y·우리가 굽는 것) 계획을 따로 둔다 (029).

캐시는 여전히 **덤이지 자료가 아니다.** 통째로 지워도 뷰어는 그대로 돌고,
줄이고 싶으면 사람이 `manage.py prune_tiles` 를 부른다. 자료의 주인은
한국지질자원연구원이다 — 우리는 받은 것을 다시 내주지 않는다.

## 지역 — 한국·일본·중국·그린란드·스발바르·얀마옌·남극, 그리고 동아시아·북극

화면 위 지역 탭으로 가른다 (devlog 016). **한국이 기본**이고 다른 지역은
"+ 추가 지역" 에서 더한다. 지역마다 레이어 목록·켠 레이어·보던 자리·배경·색이
따로다 — 한국은 먹갈색·금, 일본은 벚꽃, 중국은 청화백자, 그린란드는 빙하빛, 스발바르는 노르웨이
국기의 남색·빨강, 얀마옌은 현무암 숯빛·용암 주황, 남극은 오로라 청록, 동아시아는 청자.

- **달은 지역이 아니다** — 대돌여지도 아이콘의 숨은 차림에서 들어가는 따로 화면(`/GSM/moon/`)이다.
  CesiumJS 의 둥근 달(극까지 온전하다)에 USGS 달 통합 지질도와 LOLA 지형을 얹고, 테마는 늘 흑백이다
  (036, P05). 지질도·표고·속성·범례는 `trek.py` 를 거치고, 영상 배경(LRO WAC·Kaguya TC·LOLA 음영)만 브라우저가
  Trek 을 곧장 부른다. 좌표는 달 경위도다 — 지구의 `toLL`·좌표계를 타지 않는다. 평면은 위도 65° 너머면
  달 극 평사도법(`IAU_2015:30130`·`30135`)이고 Trek 의 극지 판을 받는다 (052). 달 지명은
  `data/moon_places.json`(`manage.py fetch_moon_places`). 원도 6 장(1971–1979)은 우리가 굽는다 — 아래 "파일을 받아"
- **화성도 지역이 아니다** — 달 화면을 옮긴 따로 화면(`/GSM/mars/`, `mars.js`·`mars.html`, 058)이다. 틀은 달과 같고
  자료만 다르다 — USGS 화성 지질도(SIM 3292)·MOLA–HRSC 지형, 영상 배경은 Viking·THEMIS·MOLA. 문은 같은 `trek.py`
  (`mars_*`, 주소 `TREK_MARS_URL`)다 — 같은 NASA Trek 의 다른 몸이라 문을 새로 내지 않았다. 테마는 녹슨 주황이다.
  평면은 달처럼 위도 65° 너머면 극 평사도법인데, Trek 의 화성 극지 판이 **극 반지름(3 376.2 km)의 구**라
  이름이 `IAU2000:49918`·`49920` 이다 (065). **달 화면을 고치면 화성에도 옮길지 본다** — 두 파일은 일부러 나란히 두었다. 화성 지명은
  `data/mars_places.json`(`manage.py fetch_moon_places --body mars`). 달·화성은 아이콘(`emblem-moon.png`·
  `emblem-mars.png`)과 대기 화면(`splash-*.gif`)이 따로다 — 원본은 `docs/brand/`
- **온 지구도 지역이 아니다** — 화성 화면을 옮긴 따로 화면(`/GSM/earth/`, `earth.js`·`earth.html`, wetherilli P06·082)이다.
  지역 탭이 "그 나라의 지도를 그 나라의 투영으로" 보는 자리라면, 여기는 둥근 지구 하나에 온 지구의 자료를 얹는다.
  지질도는 Macrostrat(`macrostrat.py`, CC BY 4.0)이고, 배경(NASA GIBS Blue Marble)·표고(AWS Terrarium)는 브라우저가
  곧장 부른다. 평면은 경위도(4326) 그대로이고 위도 65° 너머는 지역 탭과 같은 3413·3031 이다. **carto 는 한 대역
  아래만 채워**(세계 지질도뿐인 한반도는 줌 6 부터 빈다) 서버가 더 거친 대역의 타일을 늘려 밑에 깐다
  (`macrostrat.fill`). 까는 법을 고치면 `views.MACROSTRAT_FILL_VERSION` 을 올린다. 점묶음은 지역 탭의 것(`earth`)을 같이 읽는다
- **점묶음은 몸을 갖는다**(`PointSet.body` — `earth`·`moon`·`mars`, 037·058). 지구 화면은 `earth` 만, 달 화면은
  `moon` 만, 화성 화면은 `mars` 만 읽는다. 몸을 적지 않은 요청은 지구다. 달 점묶음의 표고는 LOLA(`trek.lola_values`),
  화성은 MOLA–HRSC(`trek.mars_values`, 화성 기준면)
- **지역마다 화면 투영이 다르다** — 한국·일본·중국·동아시아 3857, 그린란드·스발바르·얀마옌·북극
  3413, 남극 3031 이고 남극점이 가운데다 (017). 좌표를 옮길 때는 `toLL`/`fromLL`
  (화면 투영)을 쓰고 `ol.proj.toLonLat` 을 투영 없이 부르지 않는다. 지금의 투영은 축척 막대 옆에
  EPSG 번호로 늘 떠 있다 (jikhanjung 001)
- **북극은 지역이 아니라 묶음이다** — `REGIONS.arctic.includes` 가 그린란드·스발바르·
  얀마옌의 레이어군을 한 화면에 모은다. DB 의 `REGIONS` 에는 없다 (021).
  **동아시아도 묶음이다** — `REGIONS.eastasia.includes` 가 한국·일본·중국을 모은다. 묶음
  탭(3857)에서는 레이어가 제 범위(`bbox` + 0.5°) 밖 타일을 묻지 않는다 (024)
- 레이어군은 지역을 갖고(`LayerGroup.region`), 레이어는 상류를 갖는다
  (`Layer.upstream` — kigam·geus·vworld·grportal·npolar·gsj·phyloserver·geomap·janmayen·geo3al·kopri). 서버는 레이어의
  상류를 보고 문을 고른다
- 레이어는 그리는 법도 갖는다 — 타일(WMS)이 거의 전부이고, `kind: vector` 는 단층
  선을 1° 칸으로 받아 우리가 그리고(020), `kind: points` 는 점·모양을 한 덩이로
  받아 우리가 그린다(019·022·025). 면이 만 개를 넘는 중국은 `render: image`
  (`ol.layer.VectorImage`)로 한 장씩 굽는다
- **WMS 는 대개 3857 로 받고 OpenLayers 가 옮겨 그린다** — 캐시 열쇠가 앞 판과
  같다. **NPI 만은 지역의 투영으로 곧장 받는다** — 3857 로 물으면 축척이 부풀어
  1:25만 대신 1:75만을 준다 (021). **일본(GSJ)은 WMS 가 아니라 z/x/y 타일**이다 —
  GSJ 의 WMS 는 옛 판(V1)이라 타일 API(V2)를 `gsj/<레이어>/{z}/{x}/{y}.png` 로 중계하고,
  속성은 `point=위도,경도`(`gsj/info/`), 범례는 보는 범위의 것만 JSON 으로(`gsj/legend/`) 받는다 (024)
- 카탈로그 씨앗은 상류마다 `data/*_layers.json` 이다. KIGAM 씨앗처럼 사람이
  제목·레이어군만 손질하고, `seed_catalog` 가 컨테이너가 뜰 때 다 넣는다
- VWorld 배경·주소 찾기·한국 좌표계·KIGAM 인증키 띠는 한국과, 한국을 품은 동아시아에서만 보인다
- 극지 배경(EOX·NASA GIBS·PGC·NPI 타일·Esri 남극 위성)과 일본 배경(국토지리원 지리원 타일)은 VWorld 처럼
  브라우저가 곧장 부른다.
  EOX Sentinel-2 는 **비상업(CC BY-NC-SA)** 조건이고 Esri 남극 위성은 **Esri 이용 조건**이다 — 밖에 열 때 다시 본다 (040)
- **중국 geo3al 은 연구실 내부용이다** — USGS 메타데이터의 이용 조건이 "내부 용도만,
  가공물 포함 제3자 재배포 금지" 다(UNESCO·CGMW·ESRI 지적재산). 화면에 보이는 것 자체가
  재배포라 **밖에 열 때는 이 레이어를 먼저 내린다.** 파일은 `.gitignore`·`.dockerignore` 가 막는다 (025).
  내리는 스위치는 `GSM_PUBLIC=1`(또는 `<DB 옆>/public`)이다 — geo3al·phyloserver·peninsula 를
  목록에서 빼고 그 길도 닫는다(`views.LAB_ONLY`). 연구실 내부용 상류가 새로 오면 거기 더한다 (029).
  극지연구소(`kopri`)도 KPDC 공개 정책을 사람이 읽기 전까지 거기 있다 (053)
- GEUS 는 부르는 이를 `whoami` 로 밝혀 달라고 한다. 이메일이라 **저장소에
  적지 않는다** — `GSM_GEUS_WHOAMI` 나 `<DB 옆>/geus_whoami`
- NPI 의 `Basisdata_Intern/*` 은 "Svalbardkartet 안에서만" 이라 부르지 않는다 (P01)
- **파일을 받아 우리가 그리는 것 여덟** — 달 지질도 원도 6 장(`GSM_MOON_DIR`, 기본 `<DB 옆>/moon`, 039 —
  `manage.py build_moon_originals <zip>` 이 sqlite 한 장으로 굽는다. 같은 자리에 남극–에이트켄 분지 지질도 원본
  `spa_geomap_iqbal2026.tif` — 그리지는 않고 누른 자리만 읽는다, wetherilli 081), 남극 GeoMAP(`GSM_GEOMAP_DIR`, 기본 `<DB 옆>/geomap`,
  018), 얀마옌 지질도(`GSM_NPOLAR_DIR`, 기본 `<DB 옆>/npolar`, 022), 중국 USGS geo3al
  (`GSM_USGS_DIR`, 기본 `<DB 옆>/usgs`, 025), 한반도 지질도 음영판·민판(`GSM_PENINSULA_DIR`,
  기본 `<DB 옆>/peninsula`, 027·028 — PDF·PNG 를 `manage.py build_peninsula` 로 잘라 둔다), 남극 해저·빙저 지형
  IBCSO v2(`GSM_IBCSO_DIR`, 기본 `<DB 옆>/ibcso`, 047 — 칠한 GeoTIFF 둘을 `manage.py build_ibcso` 로 3031 에 잘라 둔다), 화성 크레이터
  목록 Robbins 2012(`GSM_MARS_DIR`, 기본 `<DB 옆>/mars`, 067 — `manage.py build_mars_craters <zip>` 이 sqlite 한 장으로 굽고 타일은 그때그때 그린다), 화성 옛 지질도·지역도 — I-1802·SIM 2888·I-2650·MTM(같은 자리, 068·wetherilli 079 —
  `manage.py build_mars_originals <zip…>`, 달 원도의 틀을 빌렸다). 운영은
  `/srv/GSM/db/` 아래다 — 배포한 자리의 compose 를 못 고쳐도 `db/` 는 붙어 있다. **저장소에 두지 않는다.** 원본은 NAS 의 `N:\GSM\sources\` 에 있다.
  파일이 없어도 뷰어는 돌고 그 자리에 안내가 뜬다. GeoMAP 의 그리는 법을 고치면
  `geomap.RENDERER` 를 올린다 — 안 올리면 캐시가 옛 그림을 낸다
- **극지연구소(053–057)는 모아 두고 그린다** — 암석 시료 목록과 KPDC 자료·운석의 상세(3 500 쪽)를
  `manage.py fetch_kopri` 가 2 초 간격으로 받아 `GSM_KOPRI_DIR`(기본 `<DB 옆>/kopri`)에 적는다. 처음 세 시간 남짓,
  다음부터는 새 것만. 화면이 부를 때 상류를 타지 않는다. 기지(WFS)와 해안선 변화 따위(3031 WMS)는 다른 상류처럼
  그때그때 받아 캐시에 보탠다. 저장소에 두지 않는다
- **phyloserver(026)는 같은 서버의 연구실 자료다** — 캐시는 하루만 믿는다(`FRESH_SECONDS`).
  한반도 지질도는 카카오 격자(EPSG:5181)를 다시 굽지 않고 화면이 옮겨 그린다. 캐시에 담지 않는다
- **한반도 지질도 음영판(027)·민판(028)은 원본의 좌표를 고쳐 쓴다** — 음영판 PDF 는 해안선보다
  355 m 북쪽·가로 0.134%, 민판 월드파일은 가로 0.267%·세로 0.137% 늘어나 있어 판마다
  `Sheet.extent` 로 고쳤다. 원본이 적은 좌표는 믿지 않고 OSM 해안선에 댄다. 스캔판처럼 출처를 몰라 밖에 열지 않는다

## 영어판

**화면의 글을 새로 적거나 고치면 영어도 같은 커밋에서 적는다.** 판을 붙일
때 영어판이 한국어판을 따라가지 못한 채 나가지 않게 하려는 것이다.

- 원문은 한국어다. JS 는 `T("…")`, 템플릿은 `{% t "…" %}`, 파이썬 메시지는
  `msg("…")` 로 감싸고, 영어는 `viewer/i18n.py` 의 표에 적는다 — 화면 문장은
  `EN`, 팝업 속성 이름은 `PROP_EN`, 레이어는 `LAYER_EN`·`GROUP_EN`
- 숫자·이름이 끼면 `{n}`·`{name}` 자리표로 적는다. 조각을 `+` 로 잇지 않는다
- **시험이 지킨다.** `test_i18n` 이 코드를 긁어 표에 없는 문장이 있으면 깨진다.
  카탈로그처럼 자료에서 오는 것은 `manage.py i18n_missing` 으로 본다 — 레이어가
  새로 들어오면 돌려 보고 `LAYER_EN` 을 채운다
- 영어판의 화면 제목은 `Great Stone Map`, 그 밑 작은 줄에 `대돌여지도` 다 —
  한국어판의 짝을 뒤집었다
- 지질시대는 **ICS 국제층서표**(https://stratigraphy.org/chart)의 명칭을 따른다.
  영어 → 한국어는 ICS 가 싣는 **한글판**(대한지질학회 옮김, v2024/12)의 표기다 — 절(Age)
  이름도 이것으로 옮긴다(`i18n.AGE_STAGES`, 029)
- **옮기지 않는 것** — 속성 값(지층명·암석명·도폭명·사람 이름), 판 이력
  (`CHANGELOG.md`), 타일 안에 그려진 글자(상류·VWorld 가 그린다). 지질시대
  값만은 낱말을 조합한 것이라 옮긴다

영어 낱말도 한 뜻에 하나만 쓴다.

| 한국어 | 영어 |
|---|---|
| 타일 | tile |
| 레이어 | layer |
| 레이어군 | layer group |
| 점묶음 | point set |
| 속성 | attributes |
| 범위 | extent |
| 배경(지도) | basemap |

## 구조

```
web/gsmweb/       Django 설정
web/viewer/       뷰어 앱 하나뿐이다. 앱을 더 가르지 않는다
  kigam.py        KIGAM 으로 나가는 문 (지질도 타일·속성·범례)
  vworld.py       VWorld 로 나가는 문 (주소·장소 검색, 좌표→주소, 지질 참고 WMS·WFS)
  geus.py         GEUS 로 나가는 문 (그린란드 지질도)
  grportal.py     그린란드 정부 포털(ArcGIS)로 나가는 문 (시료·연대 점을 통째로)
  npolar.py       노르웨이 극지연구소(NPI)로 나가는 문 (스발바르·드로닝모드랜드)
  gsj.py          일본 지질조사종합센터(GSJ)로 나가는 문 (심리스 지질도 V2 타일·속성·범례)
  kopri.py        극지연구소로 나가는 문 (암석 시료 DB·KPDC 자료 목록·KPDC 지도 서버). 목록은 모아 둔다(`fetch_kopri`)
  trek.py         NASA Trek 으로 나가는 문 (달·화성의 지질도·표고·지명·착륙지). 달·화성 화면(Cesium)만 쓴다
  macrostrat.py   Macrostrat 으로 나가는 문 (온 지구의 지질도 타일·누른 자리의 단위·범례). 온 지구 화면만 쓴다
  phyloserver.py  연구실 phyloserver 로 나가는 문 (암맥 기록 한 덩이, 한반도 지질도 카카오 격자 타일). 읽기만 한다
  zhurong.py      주룽 로버 경로 파일(data/mars_zhurong.json) -> 착륙지·경로. Trek 에 없는 것을 덧붙인다. 문이 아니다
  elevation.py    표고로 나가는 문 — AWS 표고 타일·국토지리원 표고 타일·PGC(ArcticDEM·REMA). 시료 고도, 3D 의 일본 지형
  arcpoints.py    ArcGIS 점을 받아 담는 틀. grportal·npolar 가 함께 쓴다. requests 없음
  geomap.py       남극 GeoMAP 파일을 sqlite3·struct·Pillow 로 그린다. 3031 타일 격자
  janmayen.py     얀마옌 지질도 파일(NPI) -> 위경도 GeoJSON
  geo3al.py       중국 USGS geo3al 셰이프파일(람베르트) -> 위경도 GeoJSON. 연구실 내부용
  moonmap.py      달 지질도 원도 6 장 셰이프파일 -> sqlite(R*Tree) -> 달 경위도 타일. 문이 아니다
  peninsula.py    한반도 지질도 음영판·민판 — 좌표가 붙은 QGIS PDF·PNG -> EPSG:5179 타일(미리 잘라 둔다)
  ibcso.py        남극 해저·빙저 지형 IBCSO v2 — 칠한 GeoTIFF(9354) -> 3031 타일(미리 잘라 둔다). 문이 아니다
  marscraters.py  화성 크레이터 38 만 개(Robbins 2012) -> sqlite(3 차원 R*Tree) -> 화성 경위도·극 타일. 문이 아니다
  marsmap.py      화성 옛 지질도·지역도(USGS I-1802·SIM 2888·I-2650·MTM) 셰이프파일 -> sqlite -> 화성 경위도·극 타일. moonmap 의 짝. 문이 아니다
  spamap.py       남극–에이트켄 분지 지질도 원본(팔레트 GeoTIFF) -> 누른 자리의 단위. 타일은 Trek 의 것. 문이 아니다
  warp.py         평면 격자(5179·5181·3031) 타일 -> 3857 타일. 3D 가 한반도 지질도·GeoMAP 을 얹는 길. 문이 아니다
  catalog.py      GetCapabilities XML -> 카탈로그
  coords.py       십진도 <-> 도분초. import 가 없다
  crs.py          평면 좌표계(TM·UTM-K·옛 Bessel·람베르트) <-> 위경도. pyproj 없이
  i18n.py         한국어 원문 -> 영어 번역표. 지질시대 옮기기
  tilecache.py    받아온 타일을 디스크에 둔다. 같은 것을 두 번 받지 않는다
  models.py       Layer·LayerGroup·PointSet·Point·Shape·PointSetDeletion·UpstreamDay
  views.py        화면 하나 + 프록시 둘 + 업로드
deploy/           Docker·nginx·배포 스크립트
data/             카탈로그 씨앗
web/.tilecache/   받아둔 타일. 커밋하지 않는다 (운영은 /srv/GSM/tiles)
devlog/           왜 그렇게 했는지 — 색인은 devlog/README.md
```

**상류마다 문이 하나다 — `kigam.py`·`vworld.py`·`geus.py`·`grportal.py`·`npolar.py`·`gsj.py`·`phyloserver.py`·`elevation.py`·`trek.py`·`kopri.py`·`macrostrat.py`.**
이 열하나 말고는 어디서도 `requests` 를 쓰지 않는다. 뷰가 직접 부르지 않는다. 상류가 바뀌거나 주소가
닫힐 때 고칠 자리를 하나로 묶어두려는 것이다. `geomap.py`·`janmayen.py`·`geo3al.py`·`peninsula.py`·`moonmap.py`·`ibcso.py`·`zhurong.py`·`marscraters.py`·`marsmap.py`·`spamap.py` 는
상류가 아니라 우리 디스크의 파일을 읽으므로 문이 아니다. `warp.py` 도 문이 아니다 — 원본은 부르는 쪽이 넘긴다. 문은 서로를 타지 않는다 —
주소 검색은 KIGAM 을 거치지 않고, KIGAM 인증키도 쓰지 않는다.

VWorld 배경지도(WMTS)만은 문을 거치지 않고 브라우저가 곧장 부른다 — 타일이
너무 많고, VWorld 가 그렇게 쓰라고 열쇠에 도메인 제한을 건다 (003).
**곧장 닿지 못할 때만 문을 거친다** — 사내 VPN 이 `api.vworld.kr` 연결을 끊는다.
브라우저가 한 장을 받아 보고 끊기면 `vworld/…` 로 돌린다. 캐시에 담지 않는다 (033).
**VWorld 의 WMS·WFS 는 문을 거친다** — 속성·WFS 가 CORS 로 막히고, 도메인 없이도
돌아 열쇠가 나가면 안 된다 (020).

## 커밋과 PR

WegenersDream 의 규약을 따른다(2026-09-30 부터).

**각자 자기 Linux 계정에서, 자기 GitHub 계정으로 작업한다**(대응표는 [devlog/README.md](devlog/README.md)).
저장소에 git 이름을 따로 두지 않는다.

**코드 작업은 기능마다 `feature/<기능 이름>` 브랜치에서 한다** — 기능 이름은 영어 kebab-case
(`feature/tile-cache`). 고침은 `fix/<이름>`. **코드에 손대기 직전에** `main` 에서 만들고
(`git switch -c feature/<이름> main`), **커밋·push·확인을 전부 그 브랜치에서** 한다. **작업이 끝나면 PR 을
만든다**(`gh pr create --base main`) — CI(`시험`)를 통과해야 하고, **`main` 병합은 사람이 정한다.**
판을 올리는 것은 그 PR 안에서 한다(`CHANGELOG.md`·`web/gsmweb/version.py`·HANDOFF). 병합하고 판이 올랐으면
CHANGELOG 의 그 절로 GitHub 릴리스(`v<판>`)를 만든다 — 태그마다 CI 가 Docker Hub(`koprifossillab/gsm:<태그>`)에
이미지를 올린다. 2026-09-30 전에는 `main` 에 곧장 커밋하고 한 세션이 판을 모아 붙였다.

**문서·기록만 고치는 커밋은 `main` 에 바로 올린다**(HANDOFF·TODOs·CLAUDE.md·devlog 색인 같은 것).
브랜치는 부딪힐 수 있는 것을 격리하려고 있는 것이다. 애매하면 묻는다.

**한 단계가 끝날 때마다 커밋하고 push 한다** — 기능 여럿을 한 커밋에 몰지 않는다. 단계마다 devlog 하나.

메시지는 **한국어로 무엇을 했는지**를 쓰고 끝에 devlog 를 붙인다 — 옛 꼴은 번호만(`(047)`), 새 꼴은
글쓴이와 번호(`(jikhanjung 001)`):

```
남극 — IBCSO v2 해저·빙저 지형을 배경으로 (047)
배경 타일도 서버 캐시에 담는다 (jikhanjung 001)
```

**`git add` 는 내가 고친 파일만 지정한다** — `git add -A`·`git add .`·`git commit -a` 는 쓰지 않는다.
`git commit -F <메시지 파일> -- <파일…>`. 커밋 전에 `git status --short` 를 보고, 내가 손대지 않은 파일은
그대로 둔다. 작업 전에 `git pull --rebase` — 여러 계정이 같은 저장소에서 일한다.

## devlog

**그때의 판단과 근거를 남기는 곳이다.** 실제로 한 작업은 `devlog/YYYYMMDD_{author}_{nnn}_{title}.md`, 계획은
`YYYYMMDD_{author}_P{nn}_{title}.md` 로 **단계마다 끊어** 적는다. 머리줄 아래에 `날짜 · \`브랜치\` · 글쓴이` 를
적는다. **무엇을 했는지가 아니라 왜 그렇게 했고 무엇을 버렸는지를 적는다.** 무엇을 했는지는 `git log` 가 안다.

**파일 이름은 글쓴이마다 번호를 센다**(2026-09-30 부터). `author` 는 **작업하는 Linux 계정의 GitHub 계정 이름**
소문자, `title` 은 영어 snake_case, 번호는 **그 글쓴이의** 다음 번호다. **옛 꼴(`YYYYMMDD_NNN_slug.md`,
001~077·P01~P05)은 이름을 그대로 두고** 번호만으로 가리킨다("devlog 017"). 새 꼴은 "jikhanjung 001" 로 가리킨다.
자세한 것과 계정 대응표는 [devlog/README.md](devlog/README.md) — **새 파일은 그 색인에 한 줄 더한다.**

DiaRUGA·ForGIA·WegenersDream 의 devlog 를 가리킬 때는 `DiaRUGA 063` 처럼 저장소 이름을 붙인다 —
맨 번호와 "글쓴이 번호" 는 언제나 이 저장소의 것이다.

**계획이 아닌 검토는 `docs/`** 에 둔다 — "이렇게 하겠다" 가 정해진 것은 devlog 의 P 문서이고, "할까 말까·
언제 하나" 를 따진 것은 `docs/` 다. 검토가 계획으로 정해지면 그때 P 문서를 쓴다.

**HANDOFF.md 는 지금만 말한다** — 지난 일은 devlog 의 몫이고, HANDOFF 는 근거가 필요한 자리마다
devlog 번호를 건다. **TODOs.md 에는 끝난 일을 쌓지 않는다.**
