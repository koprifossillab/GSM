# 할 일

지금 무엇을 할 수 있는지 고르는 자리다. 왜 그렇게 했는지는 `devlog/`,
지금 어디까지 왔는지는 `HANDOFF.md`.

## 지역 — 극지 (016·017·018·019·021·022)

- [ ] **(사람)** 그린란드 50만 지질도는 GEUS 가 추린 판(`_search`)이다. 원본
      (`grl_g500_lithostr_units`)을 WMS 로 열어 주는지 GEUS 에 묻는다 —
      써 보고 빈 곳이 거슬리면 사람이 메일을 쓴다. 같은 메일에 정부 포털 시료가
      딱 2 만 점에서 잘린 것과 시료 좌표가 1 km 가량 어긋나는 것도 묻는다 (019)
- [ ] 배포 뒤 `manage.py fetch_grportal` 을 한 번 — 시료 2 만 점을 처음 켜는 사람이
      17 초를 기다리지 않게 (019). **NPI 점·지명·도폭 경계도 이제 같은 명령이 받는다** (029)
- [ ] EOX Sentinel-2 는 비상업(CC BY-NC-SA) 조건이다 — 밖에 열 때 다시 본다.
      3857 이라 북위 85° 위가 둥글게 빈다 (017)
- [ ] Esri Antarctic Imagery 는 Esri 이용 조건(Master License Agreement)이다 — EOX 처럼 밖에 열 때 다시 본다 (040)
- [ ] (검토) DiaRUGA·ForGIA 의 남극·남빙양 지점과 잇기 — CLAUDE.md 대로 DB 는 나누지 않고 `Locality.lat/lon` 을
      내보내 점묶음으로 받는다. 수심 읽기(070)가 섰다 — 올리면 수심이 붙는다 (사람, 2026-09-29, 047)
- [ ] 그린란드 포털의 `gmom_tracts`(면)·지화학 원소 하나를 골라 색으로 그리기 (019)

- [ ] **(사람)** KPDC 공개 정책을 보고 `LAB_ONLY` 에서 `kopri` 를 뺄지 정한다 (053). 본문은 2026-09-30 에 읽었다
      (영문, 제10–11조). "과학적 목적으로 자유롭게" 공개하되, **자료를 쓰려는 이는 범위·목적을 적어 신청하고**
      (14 일 안에 심사), 알린 범위 안에서만 쓰며 출처를 밝히고 결과를 알린다(11조, "추가 논의 필요" 로 적혀 있다).
      우리가 보이는 것은 자료 자체가 아니라 목록(제목·위치·키워드)과 지도 서버의 선이다 — 목록은 AMD 에 올리라고
      한 메타데이터라 공개 쪽으로 읽히지만, 암석 시료·운석 목록을 밖에 다시 내주는 것이 "이용" 인지는 정책이 말하지
      않는다. 밖에 열기 전에 kpdc@kopri.re.kr 에 묻는 것이 안전하다
- [ ] 운영에서 `manage.py fetch_kopri` 를 가끔 — 새로 올라온 KPDC 자료만 받는다(목록 여덟 장 + 새 상세). 처음 모은 것은
      2026-09-29 밤 `/srv/GSM/db/kopri/` 에 두었다 (053)
- [ ] (사람) 아라온 해양 자료 백여 건이 같은 기본 네모(북위 60–80°, 160°E–150°W)만 적어 북극해 지도에서 빠진다 —
      항적이 따로 있는지 KPDC 에 묻는다. Midtre Lovénbreen 의 경도 부호(075 §5)와 같은 메일에 (076)
- [ ] 암석 시료의 상세(암상·박편·3D 모델) — 상세 페이지가 로그인 없이는 비어 있다. 극지연구소에 묻는다 (053)
- [ ] KPDC 의 다른 묶음 — PAMC 미생물 균주(2 만 2 천)·KVH 식물 표본(3 천 8 백). 지질과 거리가 있어 미뤘다 (053)

## 지역 — 일본·동아시아 (024)

- [ ] **GSM 을 밖에 열기 전에 geo3al(중국)을 내린다** — "내부 용도만, 가공물 포함 재배포 금지" (025).
      스위치가 생겼다 — `GSM_PUBLIC=1`(또는 `<DB 옆>/public`)이면 geo3al·한반도 지질도·암맥이 내려간다 (029)
- [ ] 중국지질조사국 1:250만 수치지질도(`10.23650/data.H.2017.NGA121474`) — 사람이 받을 수
      있는지·조건을 확인 중. 오면 geo3al 을 밀어낸다 (025)
- [ ] (사람) P04 §5 — 어디까지 자르나·어느 탭에 두나. Dropbox 묶음을 받을 때 안의 조건 글도 본다

- [ ] 일본의 찾기 칸 — 지금은 좌표로만 간다. 국토지리원의 주소 검색 API 를 살펴본다
      (붙이면 문이 하나 는다)
- [ ] GSJ 는 호출 제한 수치를 밝히지 않는다 — `upstream_stats` 의 `gsj` 를 지켜본다

## 3D (015)

- [ ] 배포 뒤 운영에서 기지 셋의 3D 극지 지형을 한 번 받아 둔다 — `manage.py prewarm --around <위도,경도> --km 5
      --zooms 11-15 --layers dem`, 다산·장보고·세종이 합쳐 30 분 남짓. 좌표는 명령의 머리글에 (wetherilli 078)
- [ ] 시료 고도를 삼각점 스물 남짓과 견준다 (P03 §7) — ±15 m 안에 드나. 봉우리는 수십 m 낮게 읽는 것을 보았다

## 달 (P05)

대돌여지도 아이콘의 숨은 차림 → 둥근 달(CesiumJS). 지역 탭이 아니다. 테마는 흑백.

- [ ] (사람) P05 §8 — 달 시대 한국어 표기를 본다(지금 `trek.AGES_KO`), 다누리 KGRS 자료가 열려 있는지,
      원소·광물 레이어군을 둘지, Trek 이용 조건
- [ ] (사람) Kaguya(JAXA) 자료의 이용 조건을 읽는다 — 밖에 열기 전에 (043)
- [ ] (사람) 창어 2 호(CE-2 CCD, CNSA/CLEP) 정사 모자이크의 이용 조건 — 극 평면의 고해상 배경이다. Trek 을 거쳐
      받지만 자료의 주인은 중국 달 탐사 계획이다. 밖에 열기 전에 (052)
- [ ] (사람) 달 Trek 판 한글 제목 초안(몸 전체를 덮는 114 판)을 읽고 고친다 — `data/moon_trek_layers.json` 의 `ko` (060)
- [ ] 화성 지역 지질도를 옛 지질도에 더한다 — SIM 2888(북부 평원)·I-2650(타우마시아)·MTM 1:50만 지역도.
      원본은 USGS `pigpen/mars/geology/` (068)

## 서버 디스크 — 어드민과 상의할 것

- [ ] `paleo-server` 디스크가 87% 차 있다 (228 GB 중 여유 31 GB, 2026-09-27).
      DiaRUGA·ForGIA·phyloserver 가 같은 디스크를 쓴다. 캐시는 계속 보태므로
      (007) 디스크를 늘리거나 `/srv/GSM/tiles` 를 다른 디스크로 옮길 수 있는지
      어드민과 상의한다. 그때까지는 여유 5 GB 밑이면 더 담지 않는다
- [ ] **가장 나아 보이는 길: 캐시를 NAS 로.** 이미 붙어 있는 NAS
      (172.16.112.125 → `/nfs/temp-share`, 여유 18 TB)에 타일을 두면 한 장 읽기가
      0.4 ms 다 (로컬 0.02 ms, 상류 200~700 ms — 2026-09-27 에 200 장으로 쟀다).
      상의할 것 셋: ① 지금 `hard` 마운트라 NAS 가 끊기면 요청이 **멈춘다** —
      캐시용은 `soft` 로 붙여 끊기면 상류로 넘어가게 ② 이름이 `temp-share` 라
      언제 비워지는지 ③ root 의 `docker-compose.yml` 에 볼륨을 걸고 uid 1000 이
      쓸 수 있게

## 인증키 뒤에 남은 것

- [ ] 호출 제한 수치를 KIGAM 에 묻는다 — 사람이 게시판부터 본다

## 영어판 — 남은 것 (008)

`manage.py i18n_missing` 이 잡지 못하는 것이다.

- [ ] **사람이 훑어본다.** 초안은 Claude 가 적었다. 특히 레이어 제목
      (좋은물지도 14 종·해저지질도 10 종), 속성 이름(`PROP_EN`), 설정 화면의
      `Ink brown`·`Hanji`. 고칠 자리는 `viewer/i18n.py` 하나다
- [ ] 속성 이름은 레이어 61 개를 두세 곳씩 눌러 모은 46 개다. 다른 자리에서
      처음 보는 열이 나오면 한국어로 뜬다 — 보이면 `PROP_EN` 에 더한다

**옮기지 않기로 한 것** — 속성 값(지층명·암석명·도폭명·사람 이름), 판 이력,
타일 안의 글자, 레이어 설명(한국어 제목을 되풀이한 것이라 영어판에서 숨긴다),
상류 오류의 자세한 문구(영어판은 `Could not get it from the source` 한 줄).

## VWorld 로 더 할 것 — 값 대비 쓸모 차례 (004)

조사는 끝났고 **쏴 보고 확인한 것들**이다. 자세한 것은 devlog 004.

### 값이 싸고 쓸모가 분명한 것


### 품이 좀 드는 것

- [ ] 단층 `legend` 1·2 의 뜻 — VWorld 가 밝히지 않았다. 알면 `VECTOR_STYLES` 와
      `vworld.FRIENDLY` 두 자리만 고친다 (020)

## 노는 자료 — 이미 가진 API 로 더 할 수 있는 것 (2026-09-30 조사)

열쇠·문이 이미 있는데 받지 않는 자료다. 새 문 없이 되는 것만 적었다. [실측] 은 2026-09-30 에 한 번 불러 본 것,
[문서] 는 목록에 이름만 본 것이다. 차례는 값 대비 품이다.

### 극지 — PGC·그린란드 포털·NPI·KPDC

- [ ] **PGC 경사·경사향·25 m 등고선** [실측] — 음영은 이미 배경(`map.js` 의 `pgcHillshade`)으로 쓴다. 같은 ImageServer 의
      `rasterFunctionInfos` 에 Slope Degrees·Aspect Degrees·Contour 25·Hillshade Multidirectional·Elevation Tinted 가 더 있다.
      함수 이름만 바꿔 그린란드·스발바르·남극에 경사도·등고선 레이어를 두고, 누르면 경사 몇 도(`identify`, `elevation.py`).
      CC BY 4.0. 반나절–하루
- [ ] **그린란드 광물 잠재 구역 `gmom_tracts`** [실측] — 면 162, `mineralisa`·`deposit_de`·예상 광상 수(`n90`…`n01`)·
      포털 색 `rgb`·보고서 `report`. `arcpoints` 의 면 틀로 `grportal.py` 에 서비스 하나. 반나절 (019)
- [ ] **그린란드 공식 지명 찾기** [실측] — `Nunat_Aqqi_pisortatigut_aug2018` 33 006 건(같은 조직에 `Gazetteer_v20170620`·
      `Stednavne_03_08_2018_official` — 하나를 고른다). 스발바르 지명 찾기(P01 §7)의 짝, `fetch_grportal` 로 모은다. 반나절–하루
- [ ] **남극 드로닝모드랜드 지명** [실측, 건수 안 셈] — NPI `NPI_Place_Names_Dronning_Maud_Land`, CC BY 4.0. 남극 찾기 칸. 반나절
- [ ] **KPDC 지도 서버의 안 쓴 레이어** [실측] — GetCapabilities 54 개 가운데 6 개만 쓴다. 북극해 수심·등심선
      (`arctic_topography_bathymetry`·`_bathymetric_contours`, 북극해 탭의 배경감), 영구동토(`arctic_topography_permafrost_ice`),
      남극 등고선(`antarctic_topography_contours_high`·`_low`), 역사 유적(`antarctic_human_historic`). `kopri.WMS` 표와 씨앗에 줄만.
      `LAB_ONLY` 다. 반나절 (057·073)
- [ ] **스발바르 빙하 전면 변화** [실측] — NPI `Temadata/I_Glacier_Fronts_Svalbard`(연도별 전면), 같은 폴더에 빙하 면·범위.
      CC BY 4.0, `Basisdata_Intern` 이 아니다. 빙하가 물러나며 드러난 노두를 본다. 반나절
- [ ] 그린란드 불안정 사면·매스무브먼트 [실측] — `Map_of_unstable_slopes_and_registered_mass_movements_WFL1` 면 넷.
      작성 중인 자료라 캐시 주기를 짧게. 반나절
- [ ] 그린란드 다이아몬드 탐사 DB [실측] — `DED_GL_OCCURRENCES` 3 029 점(암석군·주향·경사), 같은 묶음에 시추공·지시광물 화학.
      산출지만 반나절–하루
- [ ] 그린란드 전암 화학 [실측] — `Rock_Chemical_Analysis_from_Greenland` 31 769 점, 원소가 열 하나씩. U/Th 하나만 하루,
      원소 고르개·분위수 색까지 이틀 넘게. 위 "지화학 원소 하나를 골라 색으로" 가 이것이다
- [ ] (사람) 그린란드 50만 지질도 원본 면 [실측] — 포털 `GEUS_Greenland_500k_geology_polygon` 102 859 면(2020-05).
      GEUS WMS `_search` 의 빈 곳을 메울 수 있지만 받아온 길이 다르다 — 섞을지 사람이 정한다. 한다면 파일로 받아 굽는다. 이틀 넘게

개발 머신에서 그린란드 포털(`services5.arcgis.com`)을 부르면 인증서가 막힌다(사내망이 끼워 넣는 인증서) —
`REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt` 를 주면 돈다. 운영과는 상관없다.

### 일본·동아시아 — GSJ·국토지리원

- [ ] **CCOP 동·동남아시아 200만 지질도** [실측] — `ows.gsj.jp/ows/GSJ_CCOP_Combined_Bedrock_and_Superficial_Geology_and_Age/wms`,
      레이어 `EASIA_CCOP_2M_Combined_BLT_SLT_BA`, 동경 92–156°·남위 16.6°–북위 47.6°. 베이징 둘레가 칠해져 왔다. 3857 GetMap 은
      되지만 GetFeatureInfo 는 4326 으로만(`MAJOR_CODE` 한 칸 — GML 은 안 봤다). 조건이 "개인·교육·연구·비상업" 이라
      **밖에 열 때 geo3al 을 대신할 후보**다(025). `gsj.py`. 반나절–하루
- [ ] **GSJ 지질도Navi WMTS — 판 1 849 개** [실측] — `gbank.gsj.jp/geonavi/maptile/wmts/1.0.0/WMTSCapabilities.xml`,
      타일 `tiles.gsj.jp/tiles/geomap/<ID>/{z}/{x}/{y}.png`(3857). 5만·20만 도폭 1 006, 해양지질 339, 공중자기 96, 중력 40,
      화산지질도 30, 활구조도 21 따위. 일본 탭 "원도 도폭" 레이어군 — Trek 판처럼 씨앗으로 두고 보는 자리를 덮는 것만.
      정부표준이용규약 2.0(판마다는 안 봤다), CORS 안 봤다. 이틀
- [ ] **국토지리원 주제 타일** [실측: 경사량도 `slopemap`·도시권 활단층도 `afm` / 문서: 토지조건도 `lcmfc2`·화산기본도 `vbm`] —
      `gsiLayer()` 에 한 줄씩, 브라우저가 곧장. 반나절
- [ ] 일본 찾기 칸 [실측] — `msearch.gsi.go.jp/address-search/AddressSearch?q=` 가 GeoJSON 을 준다(위 "일본의 찾기 칸").
      좌표→주소 `mreversegeocoder.gsi.go.jp` 도 산다. 새 문(`gsi.py`)이거나, CORS 가 열렸으면 브라우저가 곧장. 반나절

GSJ 는 2024-05-10 에 WMS·WMTS 를 `ows.gsj.jp` 로 옮겼다. 심리스 V2 타일만 `gbank.gsj.jp` 에 남았다 — 위를 지으면
CLAUDE.md 의 GSJ 줄에 호스트를 적는다.

### 달 — Trek

- [ ] **광물·원소·지각 두께를 눌러 값으로** [실측] — Trek ImageServer 161 개 가운데 Kaguya MI 광물(FeO wt%·감람석·휘석·
      사장석 %, 50°N–S), Lunar Prospector Th, GRAIL 지각 두께, 극지 광물·얼음 깊이. `lola_values` 와 같은 `getSamples` 라
      `trek.py` 에 붙는다. 팝업에 "FeO 14.2 wt% · 사장석 71 % · 지각 38 km", 달 점묶음에 열로. Kaguya 는 JAXA 조건(043). 하루.
      화성 ImageServer 17 개는 DEM·모자이크뿐이다
- [ ] 달 고해상 DEM [실측] — 지금 `LOLA_DEM_Global_128ppd_v04`. 같은 서버에 `256ppd_v06`, 극지 5 m, NAC DTM 40여 곳(1.5–2 m).
      3D 지형·⛰ 가 고와진다. 하루

### 어디나 — 표고

- [ ] **표고 단면** [코드] — 잰 선을 따라 높이 그래프. 지구 `elevation.elevations`·달 `trek.lola_values`·화성 `trek.mars_values`
      가 이미 있다. 같은 점의 지질 단위를 긁어 밑에 띠를 깔면 모의 지질 단면. 새 상류 없음, 그래프 UI 가 품. 화성은 옆 세션의
      `mars.js` 와 맞춘다. 이틀
- [ ] AWS `normal` 타일 [실측] — `elevation-tiles-prod/normal/` 이 온다. 음영 배경이 빈약한 중국·동아시아에 방향 고르는 음영,
      경사도. 브라우저가 곧장. 반나절–하루

phyloserver 는 이 저장소만으로 더 할 것이 없다 — 도폭(`MapSheet`) JSON API 를 그쪽에 먼저 더해야 한다(아래 "더 나중에").

### 한국 — VWorld·KIGAM

- [ ] **"채취·출입 제한" 레이어군과 시료 지점의 "보호구역 안"** [실측] — VWorld 데이터 API `LT_C_UO301`(국가유산 지정·
      보호구역, `alias`·`uname`·`remark`)이 온다. WMS 짝은 [문서]: 국립·도립·군립공원(`lt_c_wgisnpgug`·`npdo`·`npgun`),
      백두대간(`lt_c_uf901`), 산림보호구역(`lt_c_uf151`), 자연환경보전지역(`lt_c_uq114`), 습지(`lt_c_wgisarwet`·`lt_c_um901`),
      해양보호구역(`lt_c_tfismpa`). 천연기념물 화석산지처럼 허가가 드는 자리를 채취 전에 안다. 020 이 "지질 참고가 아니다" 로
      뺀 것을 다른 레이어군으로 세운다. `point_facts`(074)에 한 칸. 반나절–하루
- [ ] **KIGAM 표본(시료·분석) 점 레이어** [실측] — `/openapi/data` 목록 3 450 건, 첫 100 건 가운데 48 건이 시료·분석.
      상세에 `POINT`·시료 분류·지질연대·지질단위·채취지·보관처·DOI. 함정: `page` 는 0 부터, `collection=` 거르기가 안 먹고,
      목록엔 좌표가 없어 한 건씩 상세를 불러야 한다 → `fetch_kopri` 처럼 모아 둔다(2 초 간격 두 시간, 다음부터 `lastModified`).
      CC BY-NC, DOI 로 출처. 이틀 (아래 "더 나중에" 의 데이터셋 검색 API 가 이것이다)
- [ ] **이 자리를 덮는 KIGAM 자료 — 도폭의 저자·발간일·DOI** [실측] — 같은 API 상세에 도폭 외곽 `POLYGON`·저자·발간일·DOI.
      누른 자리의 5만 도폭 원전을 인용 꼴로. 위와 모으기를 같이 쓰면 하루 더. 파일 내려받기(`/openapi/file`)는 확인 못 했다
- [ ] **주소만 적힌 CSV 를 점묶음으로** [004·009] — VWorld `getCoord` 로 좌표를 붙인다. 옛 야장. 0.2 초 간격. 반나절
- [ ] **토양·산림입지** [실측] — 데이터 API `LT_C_ASITSOILDEP`(유효토심)·`LT_C_FSDIFRSTS`(산림토양형) 가 온다. WMS 짝 [문서]
      `lt_c_asitsoildep`·`asitsurston`·`asitdeepsoil`·`asitsoildra`·`fsdifrsts`. 옛 토양도(`gimsscs`)가 비어 있던 자리를 메운다. 반나절
- [ ] 급경사재해예방지역·재해위험지구 [문서] — `lt_c_up401`·`lt_c_up201`. 야외 안전. 반나절
- [ ] 드론 비행 제한 공역 [문서] — `lt_c_aisprhc`·`aisresc`·`aisctrc`·`aisuac`·`aisdronezone`. 데이터 API 이름은 달라
      `NOT_FOUND` 였다 — WMS 로 다시 본다. 노두 드론 촬영 계획. 반나절
- [ ] 수질·지하수 측정망과 유역 [문서] — `lt_p_weissite*`·`lt_p_sgisgwchg`·`lt_c_wkmbbsn`·`wkmmbsn`·`wkmsbsn`.
      지하수 등수위선·등수심선(029·077)의 짝. 반나절
- [ ] 연속지적·토지 소유 [004·문서] — `lp_pa_cbnd_bubun`(WFS 로만)·`dt_d160`. 출입 허가를 받을 상대. 개인정보를 먼저 본다. 하루
- [ ] VWorld 남극 기지 위성영상 [004] — WMTS 테마 `AntarcticaSejong`·`AntarcticaJangbogo`. 남극 탭 기지 둘레 배경감.
      `z/x/y` 차례가 배경지도와 반대, 도는지 확인 안 함. 반나절
- [ ] **(사람) KIGAM GeoServer 에만 있는 레이어 338 개** [실측] — 5만 지질도의 층리·엽리·절리·선구조·화석·시료·광산
      (`Geology_map:l_50k_geology_*_latest`), 노두(`outcrop_korea`), 응력도(`korea_stress_map_2020`), 방사능(`radioactive_*`),
      Li·U 지화학, **5만 원도 스캔 50 장**(`Geology_origin_raster_50k:*_rectified`), 탄전 지질도 126, 드론 음영기복도.
      `/openapi/wms` 는 `geoOpen` 에 묶여 `LayerNotDefined` 다 — 제품 길 규칙(CLAUDE.md "두 개의 상류 주소") 아래서는 못 쓴다.
      KIGAM 에 `geoOpen` 으로 열어 달라 묻거나, 속성처럼 예외로 둘지 사람이 정한다. 값은 가장 크다

## 캐시·미리 받기 (007·010)

2026-09-30 에 타일이 어디서 어떻게 캐시되는지 훑었다. 캐시를 더 적극적으로 쓰기로 했다(사람). 차례는 위에서 아래로.

- [ ] 브라우저에 주는 유효기간이 모든 타일에 하루(`TILE_CACHE_SECONDS`)이고 ETag 가 없다 — 하루 지나면 다 다시 받는다.
      우리가 굽는 것(GeoMAP·IBCSO·달 원도·음영판)은 주소에 판을 넣고 길게, 상류 것은 ETag·304 로
- [ ] 서버를 거치는데 디스크에 담지 않는 길 — phyloserver 스캔 타일, 3D 의 `warp/` 결과. 속성·범례 JSON 에는
      Cache-Control 이 없다. 범례의 옛것 길·`dem/` 의 302 도 헤더가 없다
- [ ] 브라우저가 곧장 받는 배경 가운데 조건이 허락하는 것을 서버에 담는다 — PGC 음영(요청마다 1–2 초)·NPI 타일·
      NASA GIBS·Trek 영상. EOX(비상업)·Esri 는 조건을 먼저 본다. VWorld 는 그대로 곧장 (003·033)
- [ ] `prewarm` 이 모르는 것 — KOPRI WMS, Trek(지질·표고), 표고 타일(`dem/`)
- [ ] **무엇을 미리 받을지 정한다.** 남한 전체 줌 12 까지는 싸다(5만 지질도
      7 천 장, 0.4 GB, 호출 450 번 남짓). 줌 13~14 는 10 만 장·5 GB 라 디스크
      상의(맨 위)와 함께 본다. 줌 15 위는 전국으로는 받지 않고 현장 권역만

## 더 나중에

- [ ] 데이터셋 검색 API(`/openapi/data`) 붙이기 — 시료 자료를 지도에서 바로 찾기.
      이번 판은 WMS 만 쓴다
- [ ] (사람) 한반도 지질도의 출처·판·이용 조건을 **김선호 님께** 묻는다 — 밖에 열기 전에.
      단서: NAS `KimSunho/3차원에 섞을 것.cdr` 이 같은 지도의 CorelDRAW 벡터다(2023-05-31,
      `kopri`). 어느 출판 지도를 따라 그렸는지를 묻는다. 스캔이 아니면 레이어 이름의 "(스캔)" 을 고친다 (026)
- [ ] (사람) QGIS 프로젝트의 원본(GeoTIFF·벡터)을 받을 수 있는지 김선호 님께 묻는다 — 음영판의 좌표는
      해안선에 대 고쳐 쓰고 있다(027). 원본이 오면 고친 값을 버리고 그것을 믿는다. 제주가 빠진 것도 함께
- [ ] (phyloserver 저장소) dikesync DRF 가 쓰기(POST·DELETE)까지 권한 없이 열려 있다 — 그쪽에서 막는다
- [ ] (사람) 김선호 님께 민판의 월드파일 기준점과 제주가 든 판이 있는지 묻는다 (028)
- [ ] 민판의 색↔지층 표를 CorelDRAW 원본(026 §4)에서 뽑아 클릭으로 속성을 읽는다 (028)
- [ ] 도폭 경계를 phyloserver `MapSheet` 로 — JSON API 가 생기면 (지금은 KIGAM 도곽으로 충분)

## 하지 않기로 한 것

적어 두지 않으면 나중에 또 꺼내게 된다.

- **공간 연산 (GDAL·shapely·geopandas)** — 이 뷰어는 겹쳐 보고 클릭해 읽을 뿐이다.
  넣는 순간 web 이미지가 200 MB 대를 벗어난다. 필요해지면 그때 devlog 를 쓰고 더한다
- **DiaRUGA·ForGIA 와 DB 를 나누기** — 저장소도 배포도 따로다. 시추 지점을
  지도에 올리고 싶어지면 `Locality.lat/lon` 을 내보내 `PointSet` 으로 받는다
- **제품이 `/mgeo/geoserver` 를 타기** — 문서에 없는 주소다. 타일·범례는
  인증키로 `/openapi/wms` 를 탄다. **속성만은 예외로 탄다** — `/openapi/wms`
  가 막아 두었기 때문이다 (CLAUDE.md "두 개의 상류 주소", devlog 006)
- **네이버·카카오 지도를 배경으로 쓰기** — 둘 다 자기 렌더러를 들고 오는
  JS SDK 라, 쓰려면 OpenLayers 를 버리고 레이어 쌓기·투명도·속성 읽기
  ·점묶음을 그쪽 API 로 다시 짜야 한다. 배경지도 하나에 뷰어의 심장을 바꿀
  일이 아니다 (003)
- **OpenStreetMap 을 서버로 중계하기** — 화면은 살지만 그것이야말로 OSM 이
  막는 행동이다. 이번엔 서버 IP 가 막힌다 (003)
