# devlog 색인

그때의 판단과 근거를 적는다 — 규약은 [CLAUDE.md](../CLAUDE.md) "devlog". **새 파일은 이 표에 한 줄씩 더한다.**

## 파일 이름

2026-09-30 부터 글쓴이마다 번호를 따로 센다(WegenersDream 과 같은 꼴):

- 한 작업: `devlog/YYYYMMDD_{author}_{nnn}_{title}.md`
- 계획: `devlog/YYYYMMDD_{author}_P{nn}_{title}.md`
- `author` 는 GitHub 계정 이름(소문자). 이 서버의 Linux 계정마다 GitHub 계정이 하나다(`whoami` 로 본다):

  | Linux 계정 | GitHub 계정(`author`) |
  |---|---|
  | paleoadmin | `koprifossillab` |
  | jikhanjung | `jikhanjung` |
  | sclee | `wetherilli` |
  | jschoi | `tupandactyl` |

- `title` 은 영어 snake_case
- 번호는 **그 글쓴이의 다음 번호**다(저장소의 다음 번호가 아니다). 옛 꼴 001~077·P01~P05 는 sclee 계정이 적었으므로
  `wetherilli` 는 **078**·**P06** 부터, 다른 사람은 001·P01 부터
- **옛 꼴(`YYYYMMDD_NNN_slug.md`)은 이름을 바꾸지 않는다.** 가리킬 때는 번호만("devlog 017", "(017)")
- 새 꼴은 링크나 "jikhanjung 001" 로 가리킨다. 커밋 메시지 끝도 `(jikhanjung 001)`
- 머리줄 아래에 `날짜 · \`브랜치\` · 글쓴이` 를 적는다

## 목록

| devlog | 날짜 | 제목 |
|---|---|---|
| 001 | 2026-09-23 | [상류 오픈API 를 훑는다](20260923_001_kigam-openapi-survey.md) |
| 002 | 2026-09-23 | [옆 저장소의 지질도 캐시를 가져올까](20260923_002_phyloserver-tile-cache.md) |
| 003 | 2026-09-23 | [배경지도를 무엇으로 깔까](20260923_003_basemap.md) |
| 004 | 2026-09-23 | [VWorld 로 더 할 수 있는 것](20260923_004_vworld-api.md) |
| 005 | 2026-09-23 | [손질이 안 뜬 까닭, 그리고 로고](20260923_005_cache-and-brand.md) |
| 006 | 2026-09-27 | [인증키가 왔다. 타일은 열려 있고 속성은 닫혀 있었다](20260927_006_openapi-key.md) |
| 007 | 2026-09-27 | [받은 것은 계속 보탠다](20260927_007_keep-everything.md) |
| 008 | 2026-09-27 | [영어판](20260927_008_english.md) |
| 009 | 2026-09-27 | [주소·장소로 찾기](20260927_009_address-search.md) |
| 010 | 2026-09-27 | [호출 제한은 재지 않는다, 미리 데우기는 천천히 크게](20260927_010_rate-and-prewarm.md) |
| 011 | 2026-09-27 | [주제도 비교](20260927_011_compare.md) |
| 012 | 2026-09-27 | [선·면도 받는다](20260927_012_shapes.md) |
| 013 | 2026-09-27 | [좌표계를 고른다](20260927_013_crs.md) |
| 014 | 2026-09-27 | [지운 점묶음을 적어 두고 되살린다](20260927_014_deletion-log.md) |
| 015 | 2026-09-27 | [3D 실험: VWorld 가 아니라 MapLibre 로](20260927_015_3d-experiment.md) |
| 016 | 2026-09-27 | [지역을 나눈다: 한국·그린란드·남극](20260927_016_regions.md) |
| 017 | 2026-09-27 | [극지는 극에서 본다: 3413·3031 화면과 극지 배경](20260927_017_polar-projections.md) |
| 018 | 2026-09-27 | [남극 지질도: GeoMAP 을 우리가 그린다](20260927_018_geomap.md) |
| 019 | 2026-09-27 | [그린란드 정부 포털의 점을 레이어로: 시료·연대·광물 산출지](20260927_019_greenland-portal.md) |
| 020 | 2026-09-27 | ["지질 참고": VWorld WMS 와 단층 벡터](20260927_020_vworld-reference.md) |
| 021 | 2026-09-27 | [스발바르와 북극: 노르웨이 극지연구소 지도 서버를 3413 으로 중계한다](20260927_021_svalbard.md) |
| 022 | 2026-09-27 | [얀마옌: NPI 지질도를 모양째 받아 우리가 그린다](20260927_022_jan-mayen.md) |
| P01 | 2026-09-27 | [스발바르 — 노르웨이 극지연구소(NPI) 자료로 지역 하나를 더한다 (계획)](20260927_P01_svalbard.md) |
| P02 | 2026-09-27 | [3D 에 점묶음을 얹는다 (계획)](20260927_P02_3d-pointsets.md) |
| P03 | 2026-09-27 | [시료 고도 붙이기 — 표고 타일에서 점마다 고도를 읽는다 (계획)](20260927_P03_sample-elevation.md) |
| 023 | 2026-09-28 | [v0.7.0 을 합치고 올리며 정한 것](20260928_023_v0.7-merge-and-deploy.md) |
| 024 | 2026-09-28 | [일본, 그리고 동아시아: GSJ 심리스 지질도를 타일째 중계한다](20260928_024_japan.md) |
| 025 | 2026-09-28 | [중국: USGS geo3al 을 모양째 얹는다 (연구실 내부용)](20260928_025_china-geo3al.md) |
| 026 | 2026-09-28 | [연구실의 암맥 기록과 한반도 지질도를 싣는다](20260928_026_phyloserver-dikes.md) |
| 027 | 2026-09-28 | [한반도 지질도 음영판: 좌표가 박힌 PDF, 그리고 그 좌표를 고쳐 쓴 까닭](20260928_027_peninsula-shaded.md) |
| 028 | 2026-09-28 | [한반도 지질도 민판: 월드파일이 붙어 왔는데 또 고쳐 쓴 까닭](20260928_028_peninsula-plain.md) |
| 029 | 2026-09-28 | [v0.10 묶음: 품 S 일곱, 미리 데우기 넓히기, 절 이름, 3D 점묶음, 그림 내려받기, 스발바르 도폭](20260928_029_v0.10-batch.md) |
| P04 | 2026-09-28 | [GLiM — 전 지구 암상도를 얹는다 (계획)](20260928_P04_glim.md) |
| 030 | 2026-09-29 | [3D 에 커스텀 지질도: 5179·5181 격자를 서버가 3857 로 다시 편다](20260929_030_3d-custom-layers.md) |
| 031 | 2026-09-29 | [시료 고도(P03)와 3D 의 일본 지형: 표고 상류 셋, 그리고 극지가 쉬워진 까닭](20260929_031_elevation.md) |
| 032 | 2026-09-29 | [북극의 3D: PGC ArcticDEM 을 3857 로 옮겨, 스발바르·그린란드를 3D 로 본다](20260929_032_polar-3d.md) |
| 033 | 2026-09-29 | [VWorld 배경지도를 곧장 받지 못하면 서버를 거친다: 사내 VPN 이 끊는다](20260929_033_vworld-relay.md) |
| 034 | 2026-09-29 | [스발바르 3D: 디코드 오류, 느린 로딩, 한국 테마](20260929_034_polar-3d-speed.md) |
| 035 | 2026-09-29 | [남극도 3D 를 연다, GLiM 벡터의 이용 조건](20260929_035_antarctic-3d-glim-terms.md) |
| 036 | 2026-09-29 | [달 — 둥근 달에 지질도를 얹는다](20260929_036_moon.md) |
| 037 | 2026-09-29 | [달 점묶음 — 몸을 가른다](20260929_037_moon-pointsets.md) |
| 038 | 2026-09-29 | [달 — 2D 의 틀로, 가까이 가면 평면으로](20260929_038_moon-flat.md) |
| 039 | 2026-09-29 | [달 지질도 원도 6 장을 얹는다](20260929_039_moon-originals.md) |
| 040 | 2026-09-29 | [남극 고해상 위성 배경, 남극 3D 에 GeoMAP](20260929_040_antarctic-imagery-geomap-3d.md) |
| 041 | 2026-09-29 | [달 — 도구와 자세, 누른 자리의 표, 자전축](20260929_041_moon-tools.md) |
| 042 | 2026-09-29 | [달 — 배경 영상 보정](20260929_042_moon-image-tune.md) |
| 043 | 2026-09-29 | [달 고해상 배경 — WAC 위에 Kaguya 지형 카메라](20260929_043_moon-kaguya-imagery.md) |
| 044 | 2026-09-29 | [달 — 범례를 지질시대별 상자로](20260929_044_moon-legend-ages.md) |
| 045 | 2026-09-29 | [달 — 기울여 보기: 가운데 점·거리·방위·기울기, 그리고 자전축을 한 막대로](20260929_045_moon-pose.md) |
| 046 | 2026-09-29 | [달 — 착륙지 레이어군](20260929_046_moon-landing-sites.md) |
| 047 | 2026-09-29 | [남극 배경에 IBCSO v2 — 해저·빙저 지형](20260929_047_ibcso.md) |
| 048 | 2026-09-29 | [달 — 그림으로 내려받기](20260929_048_moon-export.md) |
| 049 | 2026-09-29 | [남극 탭 — 장보고·세종 기지로 바로 가는 "자세" 묶음](20260929_049_antarctic-stations.md) |
| 050 | 2026-09-29 | [3D — 극지에서 넓게 열고, 레이어 목록은 지역을 따른다](20260929_050_3d-polar-range-and-regions.md) |
| 051 | 2026-09-29 | [3D 남극 — IBCSO 를 배경과 지형으로](20260929_051_3d-ibcso.md) |
| 052 | 2026-09-29 | [달 — 극 평사도법 평면](20260929_052_moon-polar-flat.md) |
| 053 | 2026-09-29 | [극지연구소 암석 시료 — 새 문 `kopri.py`](20260929_053_kopri-rock-samples.md) |
| 054 | 2026-09-29 | [남극 기지 — KPDC 지도 서버의 COMNAP 시설](20260929_054_antarctic-stations.md) |
| 055 | 2026-09-29 | [KPDC 자료의 위치 — 주제마다 한 레이어](20260929_055_kpdc-datasets.md) |
| 056 | 2026-09-29 | [운석 발견 지점 — KPDC 의 KoreaMet](20260929_056_meteorites.md) |
| 057 | 2026-09-29 | [KPDC 지도 서버의 WMS — 해안선 변화·호수·하천·빙퇴석](20260929_057_kpdc-wms.md) |
| 058 | 2026-09-29 | [화성 — 달 화면을 옮겨 짓고, 달·화성에 제 아이콘과 대기 화면](20260929_058_mars.md) |
| 059 | 2026-09-29 | [3D — 실험을 벗는다](20260929_059_3d-graduates.md) |
| P05 | 2026-09-29 | [달 — 둥근 달로 들어가 평면에서 일한다 (계획)](20260929_P05_moon.md) |
| 060 | 2026-09-30 | [NASA Trek 판 목록 — 달·화성이 함께 쓰는 틀](20260930_060_trek-catalog.md) |
| 065 | 2026-09-30 | [화성 — 극 평사도법 평면](20260930_065_mars-polar-flat.md) |
| 066 | 2026-09-30 | [화성 — 주룽(祝融) 착륙 지점과 주행 경로](20260930_066_zhurong.md) |
| 067 | 2026-09-30 | [화성 — 크레이터 38 만 개 (Robbins & Hynek 2012)](20260930_067_mars-craters.md) |
| 068 | 2026-09-30 | [화성 — 옛 지질도 (USGS I-1802-A·B·C, 1986–87)](20260930_068_mars-originals.md) |
| 070 | 2026-09-30 | [누른 자리의 수심·표고 — IBCSO 수치 격자에서 읽는다](20260930_070_ibcso-depth.md) |
| 071 | 2026-09-30 | [IBCSO 자료 출처(TID) 레이어 — 잰 곳과 메운 곳](20260930_071_ibcso-tid.md) |
| 072 | 2026-09-30 | [GeoMAP 암층 — 무늬 채우기를 옮겼다](20260930_072_geomap-lithostrat.md) |
| 073 | 2026-09-30 | [KPDC 지도 서버 속성의 이름](20260930_073_kpdc-wms-props.md) |
| 074 | 2026-09-30 | [시료 지점에 VWorld 둘레를 붙인다](20260930_074_pointset-vworld-places.md) |
| 075 | 2026-09-30 | [KPDC 자료의 북극 — 스발바르·그린란드 탭에](20260930_075_kpdc-arctic.md) |
| 076 | 2026-09-30 | [북극해 탭 — KPDC 북극 자료의 나머지](20260930_076_arctic-ocean-tab.md) |
| 077 | 2026-09-30 | [VWorld 벡터의 칸을 레이어마다 — 지하수 등수심선](20260930_077_vworld-vector-cells.md) |
| jikhanjung 001 | 2026-09-30 | [화면 투영의 EPSG 번호를 축척 막대 옆에](20260930_jikhanjung_001_epsg_badge.md) |
| jikhanjung 002 | 2026-09-30 | [제목 옆에 판 번호](20260930_jikhanjung_002_title_version.md) |
| jikhanjung P01 | 2026-09-30 | [KIGAM 5만 지질도의 층리·엽리·절리를 레이어로 (계획)](20260930_jikhanjung_P01_kigam_50k_structures.md) |
| jikhanjung 003 | 2026-09-30 | [층리·엽리 뺀 5만 지질도 — 그림만 낱레이어를 엮어 GeoServer 에서](20260930_jikhanjung_003_kigam_50k_no_attitude.md) |
| jikhanjung 004 | 2026-09-30 | [5만 지질도의 자세 기호에 커서를 — 올리면 손가락, 누르면 값](20260930_jikhanjung_004_attitude_hover.md) |
| jikhanjung 005 | 2026-09-30 | [자세 기호를 늘 그리는 스위치, 그리고 "(층리 등 제외)"](20260930_jikhanjung_005_attitude_symbols.md) |
| jikhanjung 006 | 2026-09-30 | [줌 표시, 그리고 자세 기호를 멀리서 작게](20260930_jikhanjung_006_zoom_badge.md) |
| wetherilli 078 | 2026-09-30 | [3D 극지 지형을 미리 받는다](20260930_wetherilli_078_polar_dem_prewarm.md) |
| wetherilli 079 | 2026-09-30 | [화성 — USGS 지역 지질도를 옛 지질도에 얹는다](20260930_wetherilli_079_mars_regional_geology.md) |
| wetherilli 080 | 2026-09-30 | [화성 — NASA Trek 판 목록을 화성 화면에](20260930_wetherilli_080_mars_trek_catalog.md) |
| wetherilli 081 | 2026-09-30 | [달 — Trek 의 지질도 그림 둘에 속성과 범례를 붙인다](20260930_wetherilli_081_moon_geologic_rasters.md) |
| wetherilli 082 | 2026-09-30 | [운영 — 타일 캐시를 /data 하드로 옮긴다](20260930_wetherilli_082_tile_cache_to_data_disk.md) |
| wetherilli 083 | 2026-09-30 | [달 — 지형을 LOLA 256 ppd 로 올린다](20260930_wetherilli_083_moon_dem_256ppd.md) |
| wetherilli 084 | 2026-09-30 | [VWorld — 보호구역·토양·공역·유역 26 개를 더한다](20260930_wetherilli_084_vworld_more_layers.md) |
| wetherilli 085 | 2026-09-30 | [달 — 극 평면에서 Trek 판의 극지 짝을 받는다](20260930_wetherilli_085_moon_polar_trek_twins.md) |
| wetherilli P06 | 2026-09-30 | [온 지구 화면 — 달·화성처럼 둥근 지구를, 그리고 그때 그 자리 (계획)](20260930_wetherilli_P06_whole_earth.md) |
| wetherilli 086 | 2026-09-30 | [온 지구 — 달·화성처럼 둥근 지구에 Macrostrat 지질도를](20260930_wetherilli_086_whole_earth_globe.md) |
| wetherilli 087 | 2026-09-30 | [온 지구 — 그때의 자리, PALEOMAP 2016 판 회전으로](20260930_wetherilli_087_paleo_position.md) |
| wetherilli 088 | 2026-09-30 | [온 지구 — 그때의 자리를 EarthThruTime3D 에서 본다](20260930_wetherilli_088_ett_link.md) |
| wetherilli 089 | 2026-09-30 | [그린란드 포털 — 면과 갈래 색을 받는 틀, 그리고 레이어 넷](20260930_wetherilli_089_greenland_portal_areas.md) |
| wetherilli 090 | 2026-09-30 | [Trek 판 목록 — 타일 한 장을 받아 보고 적는다](20260930_wetherilli_090_trek_probe_tile.md) |
| wetherilli P07 | 2026-09-30 | [온 지구 — 시간 축, 그리고 그 위에 얹을 일곱 (계획)](20260930_wetherilli_P07_earth_time_axis.md) |
| wetherilli 091 | 2026-09-30 | [온 지구 — 시간 축, 그리고 판을 돌린 그때의 지구](20260930_wetherilli_091_earth_time_axis.md) |
| wetherilli 092 | 2026-09-30 | [극지 배경 — PGC 음영의 다른 그리는 법 둘](20260930_wetherilli_092_pgc_hillshade_variants.md) |
| wetherilli 093 | 2026-09-30 | [남극 — 세종·장보고 기지 위성영상 (VWorld 테마)](20260930_wetherilli_093_vworld_antarctic_stations.md) |
| wetherilli 094 | 2026-09-30 | [스발바르 — 빙하 전면 변화 1936–2025 (NPI)](20260930_wetherilli_094_svalbard_glacier_fronts.md) |
| wetherilli 095 | 2026-09-30 | [극지연구소 — KPDC 기본도 다섯 (노출암·등고선·역사 유적·북극 등심선·빙상 등고선)](20260930_wetherilli_095_kpdc_base_map_layers.md) |
| wetherilli 096 | 2026-09-30 | [지명 찾기 — 스발바르 하나에서 그린란드·드로닝모드랜드·북극 묶음으로](20260930_wetherilli_096_place_search_regions.md) |
| wetherilli 097 | 2026-09-30 | [온 지구 — 옛 해안선, 화석이 가리키는 가장 깊은 바다](20260930_wetherilli_097_paleocoastlines.md) |
| wetherilli 098 | 2026-09-30 | [온 지구 — 화석 산지, PBDB 27 만 곳을 연대마다 그 자리에](20260930_wetherilli_098_pbdb_fossil_collections.md) |
| wetherilli 099 | 2026-09-30 | [극지 — PGC 경사·등고선을 지질도 위에 겹치는 레이어로](20260930_wetherilli_099_pgc_slope_contour_layers.md) |
| wetherilli 100 | 2026-09-30 | [달 — 잰 선을 따라 높이 그래프](20260930_wetherilli_100_moon_elevation_profile.md) |
| wetherilli 101 | 2026-09-30 | [온 지구 — 지각 두께, CRUST 2.0](20260930_wetherilli_101_crust_thickness.md) |
| wetherilli 102 | 2026-09-30 | [온 지구 — 지명 찾기, 산맥·바다 이름, 강·호수, 빙하](20260930_wetherilli_102_natural_earth_places.md) |
| wetherilli 103 | 2026-09-30 | [달 — 누른 자리의 광물·원소·지각 두께 값](20260930_wetherilli_103_moon_point_values.md) |
| wetherilli 104 | 2026-09-30 | [온 지구 — 최근 빙기의 빙상 가장자리, 25–1 ka](20260930_wetherilli_104_ice_margins.md) |
| wetherilli 105 | 2026-09-30 | [온 지구 — 지질도가 가까이 갈수록 깨지던 것, 색마다 매끄럽게 늘린다](20260930_wetherilli_105_geology_upscale.md) |
| wetherilli 106 | 2026-09-30 | [온 지구 — 지구 속, OPT1 의 섭입한 판과 하부 더미](20260930_wetherilli_106_mantle_slabs.md) |
| wetherilli 107 | 2026-09-30 | [달 — 극지 5 m·NAC DTM 으로 가까이서 고운 지형](20260930_wetherilli_107_moon_fine_terrain.md) |
