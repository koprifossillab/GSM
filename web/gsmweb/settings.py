"""GSM(대돌여지도) Django 설정.

환경변수는 전부 `GSM_*` 이고 저장소 뿌리의 `.env` 에서 온다. python-dotenv 를
쓰지 않는 것은 실수가 아니다 — 읽을 것이 여남은 개뿐이라 의존성을 하나 더
들이는 값이 없다. `_load_env()` 열 줄이 그 일을 한다.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent   # web/
REPO_DIR = BASE_DIR.parent                          # 저장소 뿌리


def _load_env(path: Path) -> None:
    """`.env` 를 환경변수로 올린다. 이미 있는 값은 덮지 않는다 —
    컨테이너가 넘겨준 것이 파일보다 세다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env(REPO_DIR / ".env")


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    return env(key, "1" if default else "0").lower() in ("1", "true", "yes", "on")


def env_int(key: str, default: int) -> int:
    try:
        return int(env(key, str(default)))
    except ValueError:
        return default


# ── 상류 ──────────────────────────────────────────────────────────────


def _data_dir() -> Path:
    """앱을 돌리는 사람이 쓸 수 있는 자리. DB 가 있는 곳이다."""
    return Path(env("GSM_DB_PATH", str(REPO_DIR / "GSM.db"))).parent


def _lines_from(path_env: str, default_name: str) -> list:
    """한 줄에 하나씩 적힌 파일을 읽는다. 없으면 빈 목록."""
    path = env(path_env) or str(_data_dir() / default_name)
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        out.extend(part.strip() for part in line.split(",") if part.strip())
    return out



def _one_line(path_env: str, default_name: str) -> str:
    """한 줄짜리 비밀을 파일에서 읽는다. 없으면 빈 문자열."""
    path = env(path_env) or str(_data_dir() / default_name)
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _key_from_file() -> str:
    """인증키를 파일에서 읽는다. 환경변수가 비었을 때만 본다.

    **왜 두 갈래인가.** 배포한 자리의 `/srv/GSM/.env` 는 root 의 것이라 앱을
    돌리는 사람이 못 고친다. 인증키는 심사가 끝나는 날 들어오는데, 그때마다
    배포한 사람을 다시 부르는 것은 일이 아니다. 그래서 **쓸 수 있는 자리**
    (DB 옆)에 놓아도 읽는다.

    자리: `GSM_KIGAM_KEY_FILE`, 없으면 `<DB 가 있는 곳>/kigam_key`.
    키 하나만 적은 파일이고 앞뒤 공백은 버린다.
    """
    path = env("GSM_KIGAM_KEY_FILE")
    if not path:
        path = str(Path(env("GSM_DB_PATH", str(REPO_DIR / "GSM.db"))).parent / "kigam_key")
    # _data_dir() 를 쓰지 않는 것은 차례 때문이다 — 이 함수가 더 위에 있다.
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


# 인증키. 비어 있어도 뷰어는 돈다 — 타일 자리에 안내가 뜰 뿐이다.
KIGAM_KEY = env("GSM_KIGAM_KEY") or _key_from_file()

#: 배경지도(VWorld) 열쇠. 비어 있으면 배경 고르개에 VWorld 가 안 뜬다.
#:
#: **이 키는 브라우저로 나간다.** 상류 인증키와 다른 점이다 — VWorld 의
#: WMTS 는 브라우저가 직접 부르는 것을 전제로 하고, 키에 도메인 제한을
#: 걸어 지킨다. 그래서 서버가 중계하지 않는다. 중계하면 도메인 제한이
#: 뜻을 잃고 우리 서버가 모든 타일을 짊어진다.
#:
#: `<DB 옆>/vworld_key` 에 적어도 된다 — 배포한 자리의 .env 를 못 고치기 때문.
VWORLD_KEY = env("GSM_VWORLD_KEY") or _one_line("GSM_VWORLD_KEY_FILE", "vworld_key")
#: GEUS(그린란드) 지도 서비스. 이름 없이 부르면 바쁜 시간에 거절될 수 있어,
#: 부르는 이를 `whoami` 로 밝힌다 — GEUS 가 그렇게 해 달라고 적어 두었다.
#: 이메일은 저장소에 적지 않는다(공개된다). 환경변수나 `<DB 옆>/geus_whoami`.
GEUS_WMS_URL = env("GSM_GEUS_WMS_URL", "https://data.geus.dk/geusmap/ows/3857.jsp")
GEUS_MAPNAME = env("GSM_GEUS_MAPNAME", "greenland_portal")
GEUS_WHOAMI = env("GSM_GEUS_WHOAMI") or _one_line("GSM_GEUS_WHOAMI_FILE", "geus_whoami") or "GSM"
#: 그린란드 정부 광물자원 포털의 ArcGIS 서비스들 (`viewer/grportal.py`). 열쇠가 없다.
GRPORTAL_URL = env("GSM_GRPORTAL_URL",
                   "https://services5.arcgis.com/wbN76kmEQ2ue8VQm/arcgis/rest/services")
#: 노르웨이 극지연구소(NPI)의 ArcGIS 서비스들 (`viewer/npolar.py`, devlog 021). 열쇠가 없다.
#: 지도 서버(MapServer — 지질도 타일·속성·범례)와, NPI 가 ArcGIS Online 에 올린
#: 점(FeatureServer — 시료·지명) 둘이다.
NPOLAR_URL = env("GSM_NPOLAR_URL", "https://geodata.npolar.no/arcgis/rest/services")
# 극지연구소 — 암석 시료 DB, KPDC 자료 목록, KPDC 지도 서버(GeoServer). 문은 `kopri.py` 하나다
KOPRI_ROCK_URL = env("GSM_KOPRI_ROCK_URL", "https://rock.kopri.re.kr/rock")
KOPRI_KPDC_URL = env("GSM_KOPRI_KPDC_URL", "https://kpdc.kopri.re.kr")
KOPRI_GEO_URL = env("GSM_KOPRI_GEO_URL", "https://kpdcgeo.kopri.re.kr/geoserver/kpdc")
NPOLAR_FEATURES_URL = env("GSM_NPOLAR_FEATURES_URL",
                          "https://services3.arcgis.com/CflNQ7lugha7SFIt/arcgis/rest/services")
#: 일본 산업기술종합연구소 지질조사종합센터(GSJ)의 심리스 지질도 V2 Web API
#: (`viewer/gsj.py`, devlog 024). 열쇠가 없다. 판이 오르면 주소의 `1.3` 이 바뀐다.
GSJ_URL = env("GSM_GSJ_URL", "https://gbank.gsj.jp/seamless/v2/api/1.3")
#: NASA Moon Trek 의 달 서비스들 (`viewer/trek.py`, devlog 036·P05). 열쇠가 없다.
#: 지질도(ArcGIS MapServer)·표고(ImageServer)·색인(TrekServices)이 이 밑에 있다.
TREK_URL = env("GSM_TREK_URL", "https://trek.nasa.gov/moon")
#: 달 지명 — `manage.py fetch_moon_places` 가 적는다. 저장소의 씨앗 자리(`data/`)에 둔다
MOON_PLACES_FILE = BASE_DIR.parent / "data" / "moon_places.json"
#: NASA Mars Trek — 화성 (`viewer/trek.py` 의 "화성" 마디, devlog 058). 같은 Trek 의 다른 몸이다
TREK_MARS_URL = env("GSM_TREK_MARS_URL", "https://trek.nasa.gov/mars")
#: Macrostrat — 온 지구 화면의 지질도 (`viewer/macrostrat.py`, wetherilli P06). 열쇠가 없다. CC BY 4.0.
#: 타일(carto)과 API 가 주소가 다르다
MACROSTRAT_TILES_URL = env("GSM_MACROSTRAT_TILES_URL", "https://tiles.macrostrat.org")
MACROSTRAT_API_URL = env("GSM_MACROSTRAT_API_URL", "https://macrostrat.org/api/v2")
#: 화성 지명 — `manage.py fetch_moon_places --body mars` 가 적는다
MARS_PLACES_FILE = BASE_DIR.parent / "data" / "mars_places.json"
#: 주룽 로버의 착륙 지점·주행 경로 (066, `manage.py build_zhurong`)
MARS_ZHURONG_FILE = BASE_DIR.parent / "data" / "mars_zhurong.json"
#: PALEOMAP 2016 판 회전과 대륙 다각형 — 온 지구의 옛 위치 (`viewer/paleo.py`, wetherilli 087,
#: `manage.py build_paleomap <zip>`). CC BY 4.0 이라 저장소에 둔다
PALEOMAP_FILE = BASE_DIR.parent / "data" / "paleomap2016.json"
#: 지각 두께 CRUST 2.0 — 1° 격자 (`viewer/crust.py`, wetherilli 101, `manage.py build_crust <zip>`). CC BY 4.0 이라 저장소에 둔다
CRUST_FILE = BASE_DIR.parent / "data" / "crust2_thickness.json"
#: 온 지구의 지명·강·호수·빙하 — Natural Earth 10 m (`viewer/naturalearth.py`, wetherilli 102, `manage.py build_natural_earth`).
#: 퍼블릭 도메인이라 저장소에 둔다
EARTH_PLACES_FILE = BASE_DIR.parent / "data" / "earth_places.json"
EARTH_WATER_FILE = BASE_DIR.parent / "data" / "earth_water.json"
EARTH_ICE_FILE = BASE_DIR.parent / "data" / "earth_ice.json"
#: 최근 빙기의 빙상 가장자리 NADI-1·DATED-1 (`viewer/icemargins.py`, wetherilli 104, `manage.py build_ice_margins`). 저장소에 둔다
ICE_MARGINS_FILE = BASE_DIR.parent / "data" / "ice_margins.json"
#: 달 지질도 원도 6 장을 구운 sqlite(`moon_originals.sqlite`)가 있는 곳 (`viewer/moonmap.py`, devlog 039).
#: 상류가 아니라 **우리 디스크의 파일**이다. 없으면 원도 레이어 자리에 안내가 뜬다. 운영은 /srv/GSM/db/moon
MOON_DIR = env("GSM_MOON_DIR") or str(_data_dir() / "moon")
#: 화성 크레이터 목록(Robbins & Hynek 2012)을 구운 sqlite(`mars_craters.sqlite`)와 옛 지질도(`mars_originals.sqlite`,
#: 068)가 있는 곳 (`viewer/marscraters.py`·`marsmap.py`, devlog 067). 우리 디스크의 파일이다. 없으면 크레이터 레이어 자리에 안내가 뜬다. 운영은 /srv/GSM/db/mars
MARS_DIR = env("GSM_MARS_DIR") or str(_data_dir() / "mars")
#: 온 지구의 큰 자료 — 옛 해안선(`paleocoastlines_v7.json`, wetherilli 097, `manage.py build_paleocoastlines <zip>`) 따위.
#: 우리 디스크의 파일이다. 없으면 그 레이어가 비고 나머지는 돈다. 운영은 /srv/GSM/db/earth (P07 §5)
EARTH_DIR = env("GSM_EARTH_DIR") or str(_data_dir() / "earth")
#: 화성 옛 지질도(068)의 단위 색·구조선 모양 — 저장소에 담는다
MARS_ORIGINAL_STYLES_FILE = BASE_DIR.parent / "data" / "mars_original_styles.json"
#: 연구실의 phyloserver — 암맥 기록 (`viewer/phyloserver.py`, devlog 026). 열쇠가 없다.
#: 같은 서버라 컨테이너에서 호스트의 nginx 를 부른다. `paleolab` 은 컨테이너 안에서
#: 풀리지 않을 수 있어 주소로 둔다. 비우면 암맥 레이어에 "주소가 없다" 가 뜬다.
PHYLOSERVER_URL = env("GSM_PHYLOSERVER_URL", "http://172.16.116.98")
#: 남극 지질도(SCAR GeoMAP) 파일이 있는 곳. 상류가 아니라 **우리 디스크의 파일**이다
#: (devlog 018). 비어 있거나 파일이 없으면 남극 레이어 자리에 "자료가 없다" 안내가
#: 뜰 뿐 뷰어는 돈다. 기본은 `<DB 옆>/geomap/` 이다 — 운영은 /srv/GSM/geomap.
GEOMAP_DIR = env("GSM_GEOMAP_DIR") or str(_data_dir() / "geomap")
#: 노르웨이 극지연구소(NPI)에서 받아 둔 파일이 있는 곳. 지금은 얀마옌 지질도
#: (`<여기>/NP_J250_Geologi/NP_J250_Geologi_{f,l,p}.geojson`) 하나다 (devlog 022).
#: GeoMAP 과 같다 — 저장소에 두지 않고, 없으면 그 레이어에 "자료가 없다" 가 뜰
#: 뿐 뷰어는 돈다. 기본은 `<DB 옆>/npolar/` 이다 — 운영은 /srv/GSM/npolar.
NPOLAR_DIR = env("GSM_NPOLAR_DIR") or str(_data_dir() / "npolar")
#: USGS 에서 받아 둔 파일이 있는 곳. 지금은 동아시아 지질도 geo3al 하나다
#: (`<여기>/geo3al/geo3al.{shp,dbf,prj}`, devlog 025). **연구실 내부용**이다 — 이용 조건이
#: 재배포를 막는다. 저장소·이미지에 두지 않고, 없으면 "자료가 없다" 가 뜰 뿐 뷰어는 돈다.
#: 기본은 `<DB 옆>/usgs/` 이다 — 운영은 /srv/GSM/db/usgs (023 §3).
USGS_DIR = env("GSM_USGS_DIR") or str(_data_dir() / "usgs")
#: 한반도 지질도 음영판 — 좌표가 박힌 QGIS PDF 한 장과 그것을 잘라 둔 타일 (devlog 027).
#: `<여기>/*.pdf` 를 `manage.py build_peninsula` 가 `<여기>/tiles/` 로 자른다. 출처를 몰라
#: 저장소·이미지에 두지 않는다. 없으면 안내 타일이 뜰 뿐 뷰어는 돈다. 기본은 `<DB 옆>/peninsula/`.
PENINSULA_DIR = env("GSM_PENINSULA_DIR") or str(_data_dir() / "peninsula")
#: 남극 해저·빙저 지형 IBCSO v2 — PANGAEA 의 칠한 GeoTIFF 둘과 그것을 잘라 둔 타일 (devlog 047).
#: `<여기>/IBCSO_v2_{bed,ice-surface}_RGB.tif` 를 `manage.py build_ibcso` 가 `<여기>/tiles-{bed,ice}/`
#: 로 자른다. 340 MB 라 저장소·이미지에 두지 않는다. 없으면 안내 타일이 뜰 뿐 뷰어는 돈다.
IBCSO_DIR = env("GSM_IBCSO_DIR") or str(_data_dir() / "ibcso")
#: 극지연구소(KOPRI)에서 모아 둔 것 — 암석 시료 목록(`rock.json`)과 KPDC 자료 목록·상세(`kpdc.json`).
#: `manage.py fetch_kopri` 가 천천히 모아 여기 쓴다(두 시간 남짓, 다음부터는 새 것만). 저장소·이미지에
#: 두지 않는다. 없으면 그 레이어에 "자료가 없다" 가 뜰 뿐 뷰어는 돈다 (devlog 053·055). 기본은 `<DB 옆>/kopri/`.
KOPRI_DIR = env("GSM_KOPRI_DIR") or str(_data_dir() / "kopri")

# 문서화된 주소. 제품이 타는 곳은 여기뿐이다.
WMS_URL = env("GSM_WMS_URL", "https://data.kigam.re.kr/openapi/wms")
# 씨앗 뽑기 전용. 문서에 없는 주소이고 seed_catalog --from-upstream 만 부른다.
CAPABILITIES_URL = env("GSM_CAPABILITIES_URL",
                       "https://data.kigam.re.kr/mgeo/geoserver/wms")
#: 브라우저에게 "이만큼 들고 있어라" 고 말하는 시간 (HTTP Cache-Control).
TILE_CACHE_SECONDS = env_int("GSM_TILE_CACHE_SECONDS", 86400)
UPSTREAM_TIMEOUT = env_int("GSM_UPSTREAM_TIMEOUT", 20)

#: 받아온 타일을 우리 디스크에 두는 자리. 비우면 캐시를 끈다.
#: 위의 TILE_CACHE_SECONDS 와 **다른 것이다** — 저쪽은 브라우저,
#: 이쪽은 서버다. 까닭은 `viewer/tilecache.py`.
TILE_CACHE_DIR = env("GSM_TILE_CACHE_DIR", str(REPO_DIR / "web" / ".tilecache"))
#: 이 나이가 지나면 상류에 다시 묻는다. 지우지는 않는다. 기본 3 년.
TILE_CACHE_MAX_AGE_DAYS = env_int("GSM_TILE_CACHE_MAX_AGE_DAYS", 3 * 365)
#: `prune_tiles` 를 사람이 부를 때만 쓴다. 저절로 줄지 않는다.
TILE_CACHE_MAX_BYTES = env_int("GSM_TILE_CACHE_MAX_BYTES", 2 * 1024 * 1024 * 1024)
#: 디스크 여유가 이만큼 밑이면 캐시에 더 담지 않는다. 0 이면 보지 않는다.
TILE_CACHE_MIN_FREE_BYTES = env_int("GSM_TILE_CACHE_MIN_FREE_BYTES",
                                    5 * 1024 * 1024 * 1024)


def _default_ca_bundle() -> str:
    """상류를 검증할 CA 꾸러미.

    KOPRI 망은 TLS 를 가로챈다 — `data.kigam.re.kr` 의 인증서 체인 끝이
    `CN=KOPRI SSL` 이다. 그 루트는 시스템 꾸러미에 깔려 있고
    (`/usr/local/share/ca-certificates/kopri_ssl_root.crt`),
    `requests` 가 기본으로 보는 certifi 꾸러미에는 없다. 그래서 그냥 두면
    상류 요청이 전부 `CERTIFICATE_VERIFY_FAILED` 로 **멈춘다.**

    `verify=False` 로 끄지 않는다 — 검증을 끄면 가로채는 쪽을 못 가린다.
    시스템 꾸러미를 가리켜 제대로 검증한다. 컨테이너는 이미지를 만들 때
    KOPRI 인증서를 넣고(`deploy/Dockerfile.web`) 같은 자리를 본다.
    """
    system = "/etc/ssl/certs/ca-certificates.crt"
    configured = env("GSM_CA_BUNDLE")
    if configured:
        return configured
    return system if Path(system).exists() else ""


CA_BUNDLE = _default_ca_bundle()

def _dev_direct_wms() -> bool:
    """켜면 상류 요청이 문서화된 `/openapi/wms` 가 아니라 GeoServer 로 곧장 간다.

    **인증키를 기다리는 동안의 임시 조치다.** 키 없이도 타일·속성·범례가
    다 나와서 그 사이에도 일을 할 수 있다. 상류 플랫폼이 자기 지도 페이지에
    쓰는 것과 같은 주소이지만 오픈API 제품은 아니고, 예고 없이 닫혀도
    할 말이 없다.

    환경변수(`GSM_DEV_DIRECT_WMS`)와 파일(`<DB 옆>/dev_direct_wms`) 둘 다
    본다. 파일을 보는 까닭은 인증키와 같다 — 배포한 자리의 `.env` 는 root 의
    것이라 앱을 돌리는 사람이 못 고친다.

    **켜져 있으면 화면에 띠가 뜬다**(`map.html` 의 `.warn.direct`). 이것이
    이 스위치를 파일로도 열어 둔 값이다 — 끄는 것을 잊어도 보는 사람이
    안다. 키가 들어오면 파일을 지우고 다시 띄운다.
    """
    if env_bool("GSM_DEV_DIRECT_WMS", False):
        return True
    flag = _lines_from("GSM_DEV_DIRECT_WMS_FILE", "dev_direct_wms")
    return bool(flag) and flag[0].lower() in ("1", "true", "yes", "on")


DEV_DIRECT_WMS = _dev_direct_wms()


def _public() -> bool:
    """켜면 **밖에 연 뷰어**로 돈다 — 연구실 안에서만 볼 레이어를 내린다.

    내리는 것은 `views.LAB_ONLY` 의 상류다. 중국 geo3al 은 이용 조건이 "내부
    용도만, 가공물 포함 재배포 금지"(025), 한반도 지질도 스캔·음영판은 출처를
    몰라서(026·027), phyloserver 암맥은 연구실의 기록이라서다. 목록에서 빠지고
    그 길(타일·점)도 404 가 된다. 기본은 꺼짐 — 지금은 연구실 망 안에서만 연다.

    환경변수(`GSM_PUBLIC`)와 파일(`<DB 옆>/public`) 둘 다 본다. 까닭은
    `dev_direct_wms` 와 같다.
    """
    if env_bool("GSM_PUBLIC", False):
        return True
    flag = _lines_from("GSM_PUBLIC_FILE", "public")
    return bool(flag) and flag[0].lower() in ("1", "true", "yes", "on")


PUBLIC = _public()

CATALOG_SEED = REPO_DIR / "data" / "kigam_layers.json"
#: 그린란드(GEUS) 카탈로그 씨앗. seed_catalog 가 KIGAM 씨앗과 함께 넣는다
GEUS_CATALOG_SEED = REPO_DIR / "data" / "geus_layers.json"
#: 한국의 "지질 참고" 레이어군(VWorld WMS·WFS) 씨앗. 이것도 함께 넣는다 (devlog 020)
VWORLD_CATALOG_SEED = REPO_DIR / "data" / "vworld_layers.json"
#: 그린란드 정부 포털의 점 레이어 씨앗. 역시 seed_catalog 가 함께 넣는다
GRPORTAL_CATALOG_SEED = REPO_DIR / "data" / "grportal_layers.json"
#: 남극(GeoMAP) 카탈로그 씨앗과, .qml 에서 뽑아 둔 색 (manage.py geomap_styles)
GEOMAP_CATALOG_SEED = REPO_DIR / "data" / "geomap_layers.json"
JANMAYEN_CATALOG_SEED = REPO_DIR / "data" / "janmayen_layers.json"
#: 노르웨이 극지연구소 — 스발바르와 남극 드로닝모드랜드 (devlog 021). 지역이 둘이라 씨앗도 둘
NPOLAR_CATALOG_SEED = REPO_DIR / "data" / "npolar_layers.json"
NPOLAR_DML_CATALOG_SEED = REPO_DIR / "data" / "npolar_dml_layers.json"
#: 일본 — GSJ 심리스 지질도 (devlog 024)
GSJ_CATALOG_SEED = REPO_DIR / "data" / "gsj_layers.json"
#: 중국 — USGS geo3al (devlog 025)
GEO3AL_CATALOG_SEED = REPO_DIR / "data" / "geo3al_layers.json"
#: 연구실의 암맥 기록 — phyloserver (devlog 026)
PHYLOSERVER_CATALOG_SEED = REPO_DIR / "data" / "phyloserver_layers.json"
#: 한반도 지질도 음영판 — 우리 디스크의 PDF (devlog 027)
PENINSULA_CATALOG_SEED = REPO_DIR / "data" / "peninsula_layers.json"
#: 남극 IBCSO 자료 출처(TID) — 우리가 잘라 둔 3031 타일 (071)
IBCSO_CATALOG_SEED = REPO_DIR / "data" / "ibcso_layers.json"
#: PGC 경사·등고선 — 지질도 위에 겹치는 극지 레이어 (wetherilli 099). 지역이 셋이라 씨앗도 셋이다
PGC_CATALOG_SEEDS = tuple(REPO_DIR / "data" / f"pgc_{r}_layers.json" for r in ("greenland", "svalbard", "antarctica"))
#: 극지연구소(KOPRI) — 지역마다 한 장: 남극(시료·KPDC 자료·기지·해안선), 스발바르·그린란드(암석 시료·KPDC 자료),
#: 북극해(KPDC 자료) (053–057·075·076)
KOPRI_CATALOG_SEEDS = [REPO_DIR / "data" / f"kopri_{region}_layers.json"
                       for region in ("antarctica", "svalbard", "greenland", "arctic_ocean")]
GEOMAP_STYLES = REPO_DIR / "data" / "geomap_styles.json"

# ── Django ────────────────────────────────────────────────────────────
SECRET_KEY = env("GSM_SECRET_KEY", "개발용-바꿔야-한다")
DEBUG = env_bool("GSM_DEBUG", True)


def _allowed_hosts() -> list:
    """들어와도 되는 호스트 이름.

    **파일에서도 더 받는다.** 까닭은 인증키와 같다 — 배포한 자리의
    `/srv/GSM/.env` 는 root 의 것이라 앱을 돌리는 사람이 못 고친다. 그런데
    이 장비는 `paleolab`·`paleo-server`·IP 로 두루 불리고, 목록에 없는
    이름으로 들어오면 Django 가 **400 을 낸다** — 2026-09-23 배포 직후
    `http://paleolab/GSM/` 이 그랬다.

    `*` 로 열지 않는다. 열어 두면 될 일이지만, 어떤 이름으로 불리는지를
    적어 두는 편이 나중에 읽힌다.

    자리: `GSM_ALLOWED_HOSTS_FILE`, 없으면 `<DB 가 있는 곳>/allowed_hosts`.
    """
    hosts = [h.strip() for h in env("GSM_ALLOWED_HOSTS").split(",") if h.strip()]
    hosts += _lines_from("GSM_ALLOWED_HOSTS_FILE", "allowed_hosts")
    if not hosts:
        hosts = ["127.0.0.1", "localhost"]
    seen, out = set(), []
    for host in hosts:
        if host not in seen:
            seen.add(host)
            out.append(host)
    return out


ALLOWED_HOSTS = _allowed_hosts()
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("GSM_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# nginx 서브패스로 걸 때 `GSM/`. 뿌리에 걸려면 빈 값.
URL_PREFIX = env("GSM_URL_PREFIX", "GSM/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "viewer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # 정적 파일을 gunicorn 이 직접 내준다. DEBUG=0 이면 Django 가 안 내주고,
    # nginx 에게 맡기려면 이미지 안의 파일을 호스트로 꺼내야 해서 번거롭다.
    # 까닭은 requirements-web.txt 의 주석.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "gsmweb.urls"
WSGI_APPLICATION = "gsmweb.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("GSM_DB_PATH", str(REPO_DIR / "GSM.db")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{n}"} for n in (
        "UserAttributeSimilarityValidator", "MinimumLengthValidator",
        "CommonPasswordValidator", "NumericPasswordValidator")
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = f"/{URL_PREFIX}static/" if URL_PREFIX else "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# 눌러서 보낸다. 해시 이름(Manifest)은 쓰지 않는다 — 파일 하나가 빠지면
# 화면 전체가 멈춘다. 캐시 무효화는 템플릿이 주소 끝에 붙이는 내용 표
# (`views.asset_stamp`, `?v=`)가 맡는다. 판 번호만으로는 모자랐다 (005).
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = f"/{URL_PREFIX}media/" if URL_PREFIX else "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 업로드 한 묶음의 크기 한계. 점묶음은 좌표 목록이라 이보다 클 일이 드물다.
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("GSM_MAX_UPLOAD_BYTES", 16 * 1024 * 1024)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("GSM_LOG_LEVEL", "INFO")},
}
