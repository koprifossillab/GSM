"""말 — 한국어와 영어.

**원문은 한국어다.** 화면·JS·서버 메시지를 한국어로 적고, 영어는 이 파일의
표에서 찾는다. 열쇠가 한국어 원문 그대로라 코드를 읽는 사람이 무엇을
옮긴 것인지 곧바로 안다. 표에 없는 것은 한국어로 남는다 — 영어판이 한
글자 빠졌다고 화면이 깨지지는 않는다.

**문장을 새로 적거나 고치면 여기도 적는다** (CLAUDE.md "영어판").
`test_i18n` 이 JS 의 `T("…")`, 템플릿의 `{% t "…" %}`, 파이썬의 `msg("…")`
를 모두 긁어 이 표에 없는 것을 잡는다. 레이어 제목처럼 자료에서 오는 것은
시험이 아니라 `manage.py i18n_missing` 이 보여준다.

숫자·이름이 끼는 문장은 `{n}`·`{name}` 자리표로 둔다. 영어는 말 차례가
달라 조각을 이어 붙이면 어색하다.

**속성 값은 옮기지 않는다** — 지층명·암석명은 상류가 한국어로 주는 자료이고
수천 가지다. 지질시대만은 낱말을 조합한 것이라 옮긴다. 영문 명칭은 ICS
국제층서표(https://stratigraphy.org/chart)를 따른다.
"""
import re

LANGS = ("ko", "en")
COOKIE = "gsm_lang"


def lang_of(request) -> str:
    """쿠키가 먼저다. 없으면 브라우저가 한국어를 받지 않을 때만 영어로 연다."""
    chosen = request.COOKIES.get(COOKIE, "")
    if chosen in LANGS:
        return chosen
    accept = request.META.get("HTTP_ACCEPT_LANGUAGE", "").lower()
    if accept and "ko" not in accept and "en" in accept:
        return "en"
    return "ko"


class Msg(str):
    """한국어로 채워진 문자열이면서 원문 틀과 값을 따로 들고 있다.

    업로드 알림처럼 뷰 밖(`pointsets.py`)에서 만들어져 뷰가 사람에게 보일 때
    영어로 바꿔야 하는 문장에 쓴다. 그냥 쓰면 한국어 문자열이라 기존 코드와
    시험은 그대로 돈다.
    """

    def __new__(cls, template, **params):
        self = super().__new__(cls, template.format(**params))
        self.template = template
        self.params = params
        return self


def msg(template: str, **params) -> Msg:
    return Msg(template, **params)


def t(text, lang: str = "ko", **params) -> str:
    """한 문장을 옮긴다. `Msg` 면 원문 틀로 찾는다."""
    if isinstance(text, Msg):
        template, params = text.template, {**text.params, **params}
    else:
        template = str(text)
    out = EN.get(template, template) if lang == "en" else template
    if lang == "en":
        # 자리표에 들어가는 값도 표에 있으면 옮긴다 — 좌표계 이름 같은 것
        params = {k: EN.get(v, v) if isinstance(v, str) else v for k, v in params.items()}
    return out.format(**params) if params else out


def client_table(lang: str) -> dict:
    """브라우저에 실어 보낼 표. 한국어판이면 비운다 — 옮길 것이 없다."""
    if lang != "en":
        return {}
    return {**EN, **PROP_EN}


# ── 화면·메시지 ──────────────────────────────────────────────────────

EN = {
    # 이름
    "대돌여지도": "Great Stone Map",
    "GSM — 한국지질자원연구원 지오빅데이터 오픈플랫폼 오픈API 지도뷰어":
        "GSM — a map viewer for the KIGAM Geo Big Data Open Platform API",
    "불러오는 중": "Loading",

    # 띠
    "<b>임시 경로로 받고 있다.</b> 인증키가 아직 없어 문서에 없는 주소 (<code>/mgeo/geoserver/wms</code>)로 지도를 받는다. 키가 들어오면 <code>dev_direct_wms</code> 를 지우고 다시 띄운다 — 그때부터 문서화된 <code>/openapi/wms</code> 로 간다.":
        "<b>Using a temporary route.</b> There is no API key yet, so maps come from an undocumented address (<code>/mgeo/geoserver/wms</code>). Once a key arrives, delete <code>dev_direct_wms</code> and restart — requests then go to the documented <code>/openapi/wms</code>.",
    "인증키가 없다. 타일 자리에 안내가 뜬다 — <code>GSM_KIGAM_KEY</code> 를 채우거나 <code>kigam_key</code> 파일을 둔다.":
        "No API key. Tiles show a notice instead — set <code>GSM_KIGAM_KEY</code> or add a <code>kigam_key</code> file.",

    # 패널
    "레이어": "Layers",
    "불러오기": "Import",
    "레이어 고르기": "Choose layers",
    "배경": "Basemap",
    "지명 보이기": "Show place names",
    "켠 지질 레이어": "Active layers",
    "위가 앞이다": "top is front",
    "아직 켠 레이어가 없다": "No layers on yet",
    "기본 지질도": "Geological maps",
    "추가 지질도": "More maps",
    "오픈API 로 그려지는지 아직 대조하지 않았다": "Not yet checked against the Open API",
    "위로": "Move up",
    "아래로": "Move down",
    "범": "L",
    "범례를 펼친다": "Show legend",
    "{title} 범례": "{title} legend",
    "범례를 받지 못했다": "Could not load the legend",
    "이 레이어가 있는 곳으로 범위를 맞춘다": "Zoom to this layer's extent",
    "끈다": "Turn off",
    "끌어서 차례를 바꾼다": "Drag to reorder",
    "실험": "experimental",
    "실험 기능": "Experimental features",
    "켬": "On",
    "다 여물지 않은 기능을 먼저 써 본다. 지금은 3D 보기(지도 오른쪽 도구 막대).":
        "Try features that are not finished yet. For now: 3D view (map toolbar on the right).",
    "3D 로 본다 (실험) — 지금 보던 자리를 연다": "View in 3D (experimental) — opens where you are",
    "지질 레이어": "Geology layer",
    "투명도": "Opacity",
    "지형 과장": "Terrain exaggeration",
    "음영 보이기": "Show hillshade",
    "오른쪽 단추를 누른 채 끌면(또는 Ctrl+끌기) 기울이고 돌린다.":
        "Drag with the right button (or Ctrl+drag) to tilt and rotate.",
    "표고: AWS Terrain Tiles (SRTM 등, 약 30 m). 지질도: 한국지질자원연구원.":
        "Elevation: AWS Terrain Tiles (SRTM etc., about 30 m). Geology: KIGAM.",
    "2D 로 돌아간다": "Back to 2D",
    "지역": "Regions",
    "한국": "Korea",
    "그린란드": "Greenland",
    "남극": "Antarctica",
    "얀마옌": "Jan Mayen",
    # 스발바르와, 그린란드·스발바르·얀마옌을 한 화면에 모은 북극 탭 (devlog 021)
    "스발바르": "Svalbard",
    "북극": "Arctic",
    # 일본과, 한국·일본을 한 화면에 모은 동아시아 탭 (devlog 024)
    "일본": "Japan",
    "동아시아": "East Asia",
    # 중국 — USGS geo3al 을 우리가 그린다 (devlog 025)
    "중국": "China",
    "추가 지역": "Add region",
    "준비 중": "coming soon",
    "이 지역을 탭에서 뺀다": "Remove this region from the tabs",
    "<b>남극 지질도는 준비 중이다.</b> 남극점을 가운데 둔 평사도법 화면과 배경지도를 먼저 띄워 둔다. GeoMAP 레이어는 곧 붙인다.":
        "<b>Antarctic geology is coming soon.</b> For now the map opens in a South-Pole-centred polar stereographic view with basemaps. GeoMAP layers will follow.",
    # 극지 투영·배경 (017)
    "Sentinel-2 위성 (EOX)": "Sentinel-2 satellite (EOX)",
    "EOX · Copernicus Sentinel-2 (2023). 비상업 이용만 된다":
        "EOX · Copernicus Sentinel-2 (2023). Non-commercial use only",
    "지형 음영 (EOX)": "Terrain shading (EOX)",
    "EOX · OpenStreetMap. 비상업 이용만 된다": "EOX · OpenStreetMap. Non-commercial use only",
    "ArcticDEM 음영": "ArcticDEM hillshade",
    "REMA 음영": "REMA hillshade",
    "Polar Geospatial Center. 2 m 표고에서 그린 음영":
        "Polar Geospatial Center. Hillshade drawn from 2 m elevation",
    "Blue Marble 위성 (NASA)": "Blue Marble satellite (NASA)",
    "NASA GIBS. 500 m 해상도라 넓게 볼 때 쓴다": "NASA GIBS. 500 m resolution, for wide views",
    "왼쪽 위": "Top left",
    "오른쪽 위": "Top right",
    "오른쪽 아래": "Bottom right",
    "왼쪽 아래": "Bottom left",
    "주제도 비교": "Compare maps",
    "끔": "Off",
    "밀어 보기": "Swipe",
    "나란히": "Side by side",
    "끌어서 견준다": "Drag to compare",
    "막대 왼쪽": "Left of bar",
    "오른쪽": "Right",
    "고른 레이어가 막대 왼쪽에만 보인다. 막대를 끌어 견준다.":
        "The chosen layer shows only left of the bar. Drag the bar to compare.",
    "왼쪽은 켠 레이어, 오른쪽은 고른 레이어. 두 지도가 함께 움직인다.":
        "Left: your active layers. Right: the chosen layer. Both maps move together.",
    "먼저 레이어를 둘 이상 켠다.": "Turn on two or more layers first.",

    # 배경지도
    "없음 (바탕만)": "None (plain)",
    "VWorld 배경지도": "VWorld basemap",
    "VWorld 백지도": "VWorld white",
    "VWorld 야간": "VWorld night",
    "VWorld 위성": "VWorld satellite",
    "국토지리정보원": "National Geographic Information Institute",
    "국토지리정보원 · VWorld": "NGII · VWorld",
    "구분 {value}": "Class {value}",
    "국토지리정보원. 지질도 밑에 깔기 좋다":
        "National Geographic Information Institute. Good under geological maps",
    "국토지리정보원. 지명을 끄고 켤 수 있다":
        "National Geographic Information Institute. Place names can be toggled",

    # 그리기
    "그리기": "Drawing",
    "지도에 얹은 내 것": "your things on the map",
    "찍고 잰 것": "Points & measurements",
    "저장 전까지 임시": "temporary until saved",
    "아직 잰 것이 없다": "Nothing measured yet",
    "지도 오른쪽 위 <b>점</b> 도구로 찍는다": "Use the <b>Point</b> tool at the top right of the map",
    "점묶음으로 저장": "Save as point set",
    "찍은 점과 잰 것을 모두 지운다": "Clear all points and measurements",
    "모두 지운다": "Clear all",
    "점묶음": "Point sets",
    "불러오거나 저장한 자료": "imported or saved",
    "왼쪽 위 <b>불러오기</b> 탭에서 올린다": "Upload from the <b>Import</b> tab at the top left",
    "{n}점": "{n} pts",
    "이 자료로 범위를 맞춘다": "Zoom to this data",
    "GeoJSON 으로 내려받는다": "Download as GeoJSON",
    "지운다": "Delete",
    "'{name}' 을 지운다.": "Delete '{name}'?",
    "이 점으로 이동": "Go to this point",
    "눌러서 복사한다": "Click to copy",
    "복사": "Copy",
    "복사했다": "Copied",
    "저장할 점이 없다.": "No points to save.",
    "목록 이름": "Name for the list",
    "찍은 점 {date}": "Points {date}",
    "저장하는 중…": "Saving…",
    "점 {n}": "Point {n}",
    "저장하지 못했다": "Could not save",
    "'{name}' 으로 저장했다.": "Saved as '{name}'.",

    # 도구
    "그리기 도구": "Drawing tools",
    "범위": "Extent",
    "범위 {n}": "Extent {n}",
    "범위잡기 — 누른 채 끌어 네모를 그리면 꼭짓점·중앙·넓이가 뜬다":
        "Extent — press and drag a rectangle to get its corners, centre and area",
    "누른 채 끌어 네모를 그린다. 손을 떼면 꼭짓점·중앙·넓이가 뜬다.":
        "Press and drag to draw a rectangle. Release to see its corners, centre and area.",
    "누른 채 끌어 네모를 그린다": "Press and drag a rectangle",
    "북서": "NW", "북동": "NE", "남동": "SE", "남서": "SW",
    "중앙": "Centre",
    "가로 × 세로": "Width × height",
    "눌러서 꼭짓점·중앙·넓이를 복사한다": "Click to copy corners, centre and area",
    "이 범위로 가서 수치를 본다": "Go to this extent and show its figures",
    "점": "Point",
    "거리": "Distance",
    "넓이": "Area",
    "지우기": "Clear",
    "점 찍기 — 누른 자리에 점을 찍고 위경도를 적는다":
        "Point — drop a point where you click and note its coordinates",
    "거리 재기 — 눌러 가며 잇고, 두 번 누르면 끝난다":
        "Distance — click to add vertices, double-click to finish",
    "넓이 재기 — 눌러 가며 두르고, 두 번 누르면 끝난다":
        "Area — click to outline, double-click to finish",
    "지도를 누르면 그 지점의 지질 속성이 뜬다.": "Click the map to read the geology there.",
    "지도를 누르면 점이 찍히고 위경도가 적힌다. 점을 눌러 지운다.":
        "Click the map to drop a point with its coordinates. Click a point to remove it.",
    "눌러 가며 선을 잇는다. 두 번 누르면 끝난다.": "Click to draw a line. Double-click to finish.",
    "눌러 가며 둘레를 두른다. 두 번 누르면 끝난다.": "Click to outline an area. Double-click to finish.",
    "점 {n}개": "{n} points",
    "지도를 눌러 점을 찍는다": "Click the map to drop a point",
    "눌러 가며 잇는다 · 두 번 누르면 끝": "Click to draw · double-click to finish",
    "눌러 가며 두른다 · 두 번 누르면 끝": "Click to outline · double-click to finish",

    # 팝업
    "내 자료": "My data",
    "찍은 점 {n}": "Point {n}",
    "켠 레이어가 없다": "No layers are on",
    "읽는 중…": "Reading…",
    "이 자리에는 아무것도 없다": "Nothing here",
    "위도": "Latitude",
    "경도": "Longitude",
    "도분초": "DMS",
    "접기": "Collapse",
    "모두 표시 ({n})": "Show all ({n})",
    "닫는다": "Close",

    # 불러오기
    "바깥 자료를 지도에": "bring outside data onto the map",
    "CSV · GeoJSON 고르기": "Choose CSV · GeoJSON",
    "점묶음 이름 (비우면 파일 이름)": "Point set name (file name if empty)",
    "점 색": "Point colour",
    "올린다": "Upload",
    "위경도 열은 이름으로 알아낸다 — <code>lat</code>·<code>위도</code>·<code>y</code>, <code>lon</code>·<code>경도</code>·<code>x</code>. 나머지 열은 점을 누르면 뜬다.":
        "Coordinate columns are found by name — <code>lat</code>·<code>위도</code>·<code>y</code>, <code>lon</code>·<code>경도</code>·<code>x</code>. Other columns appear when you click a point.",
    "올렸다 — {what}.": "Uploaded — {what}.",
    "GeoJSON 은 점·선·면을 다 받는다.": "GeoJSON may hold points, lines and polygons.",
    "선 {n}": "{n} lines",
    "면 {n}": "{n} polygons",
    "올리지 못했다": "Upload failed",

    # 좌표 막대
    "좌표·주소·장소로 이동 — 36.378, 127.362 · 과학로 124 · 가정동":
        "Go to coordinates, address or place — 36.378, 127.362 · a Korean address or place name",
    "행정구역": "District",
    "도로명": "Road address",
    "지번": "Parcel",
    "장소": "Place",
    "찾는 중…": "Searching…",
    "찾지 못했다": "Search failed",
    "찾은 것이 없다 — 주소·장소·행정구역을 넣어 본다": "Nothing found — try an address, place or district",
    "주소 검색: VWorld (국토지리정보원)": "Address search: VWorld (National Geographic Information Institute)",
    "간다": "Go",
    "십진도와 도분초를 오간다": "Switch between decimal degrees and DMS",
    "좌표로 읽지 못했다": "Not a coordinate I can read",
    "보이는 지도의 북쪽 끝": "Northern edge of the visible map",
    "보이는 지도의 남쪽 끝": "Southern edge of the visible map",
    "보이는 지도의 서쪽 끝": "Western edge of the visible map",
    "보이는 지도의 동쪽 끝": "Eastern edge of the visible map",

    # 설정
    "설정": "Settings",
    "설정과 판 이력": "Settings and release notes",
    "모양": "Look",
    "판 이력": "Release notes",
    "지금 상태": "Status",
    "화면": "Theme",
    "먹갈색": "Ink brown",
    "한지": "Hanji",
    "먹갈색이 기본이다. 한지는 밝은 바탕에 갈색 글자다.":
        "Ink brown is the default. Hanji is brown text on a light background.",
    "글꼴": "Font",
    "고딕": "Sans",
    "명조": "Serif",
    "기기 기본": "System",
    "지질도 위의 글자는 상류가 그린 것이라 바뀌지 않는다.":
        "Text drawn on the geological maps comes from the source and does not change.",
    "글자 크기": "Text size",
    "작게": "Small",
    "보통": "Medium",
    "크게": "Large",
    "속성 값(지층명·암석명)은 상류가 한국어로 주는 것이라 그대로 둔다. 지질시대만 영어로 옮긴다.":
        "Attribute values (formation and rock names) come from the source in Korean and are left as they are. Only geologic ages are translated.",
    "고른 것은 이 브라우저에만 남는다. 서버로 가지 않는다.":
        "Choices stay in this browser only. Nothing is sent to the server.",
    "판 이력은 한국어로만 적는다.": "Release notes are written in Korean only.",
    "판 이력을 읽지 못했다.": "Could not load the release notes.",
    "아직 적힌 판이 없다.": "No releases yet.",
    "배경지도": "Basemap",
    "없음": "None",
    "켠 레이어": "Active layers",
    "찍은 점": "Points",
    "{n}개": "{n}",
    "올린 자료": "Uploads",
    "{n}묶음": "{n} sets",
    "좌표 표기": "Coordinates",
    "십진도": "Decimal",

    # 서버 메시지 (views.py)
    "인증키가 없다": "No API key",
    "layer 가 없다": "No layer given",
    "올린 파일이 없다": "No file uploaded",
    "읽지 못했다": "Could not read the request",
    "저장할 점이 없다": "No points to save",
    "한 번에 {n}점까지 저장한다": "Up to {n} points can be saved at once",
    "쓸 만한 좌표가 없다": "No usable coordinates",
    "상류에서 받지 못했다": "Could not get it from the source",
    "이미 되살렸다": "Already restored",
    "최근 지운 점묶음": "Recently deleted point sets",
    "지울 때 사본을 남겨 둔다. 잘못 지웠으면 되살린다.":
        "A copy is kept when a point set is deleted. Restore it if it was a mistake.",
    "지운 것이 없다": "Nothing deleted",
    "되살림": "restored",
    "되살리기": "Restore",
    "되살리지 못했다": "Could not restore",
    "주소 검색이 꺼져 있다 — VWorld 열쇠가 없다": "Address search is off — no VWorld key",
    "VWorld 가 답하지 않는다": "VWorld is not responding",

    # 업로드 알림 (pointsets.py)
    "글자를 읽지 못했다. UTF-8 이나 CP949 로 저장해 다시 올린다.":
        "Could not read the text. Save it as UTF-8 or CP949 and upload again.",
    "첫 줄에 열 이름이 없다.": "The first row has no column names.",
    "위경도 열을 찾지 못했다. 열 이름을 {lat} / {lon} 가운데 하나로 두고 다시 올린다. (읽은 열: {cols})":
        "No coordinate columns found. Name them one of {lat} / {lon} and upload again. (Columns read: {cols})",
    "{line}째 줄 — 좌표를 읽지 못해 건너뛰었다": "Row {line} — skipped, coordinates unreadable",
    "좌표를 하나도 읽지 못했다.": "No coordinates could be read.",
    "…모두 {n}줄을 건너뛰었다": "…{n} rows skipped in all",
    "GeoJSON 이 깨져 있다: {err}": "The GeoJSON is broken: {err}",
    "GeoJSON 에 features 가 없다.": "The GeoJSON has no features.",
    "점·선·면을 하나도 찾지 못했다.": "No points, lines or polygons found.",
    "'{n}' 를 북쪽, '{e}' 를 동쪽으로 읽었다 (측량 관례).":
        "Read '{n}' as northing and '{e}' as easting (surveying convention).",
    "'{e}' 를 동쪽, '{n}' 를 북쪽으로 읽었다. 측량 관례(X=북)면 열 이름을 X좌표·Y좌표 로 바꿔 다시 올린다.":
        "Read '{e}' as easting and '{n}' as northing. If the file uses the surveying convention (X = north), rename the columns to X좌표·Y좌표 and upload again.",
    "{line}째 줄 — {name} 좌표로 읽지 못해 건너뛰었다": "Row {line} — skipped, not a readable {name} coordinate",
    "{name} 좌표로 읽지 못했다 — 한반도 밖으로 간다": "Not a readable {name} coordinate — it lands outside Korea",
    "{name} 좌표로 읽히는 줄이 없다. 좌표계를 다시 고른다.":
        "No rows read as {name} coordinates. Choose the coordinate system again.",
    "좌표가 위경도 범위를 벗어난다. TM 좌표면 올리기 전에 좌표계를 고른다.":
        "Coordinates are outside latitude/longitude range. If they are TM, choose the coordinate system before uploading.",
    "평면 좌표 열을 찾지 못했다. 열 이름을 {east} / {north} 가운데 하나로 두고 다시 올린다. (읽은 열: {cols})":
        "No planar coordinate columns found. Name them one of {east} / {north} and upload again. (Columns read: {cols})",
    # 좌표계 이름 (crs.SYSTEMS)
    "위경도 (WGS84)": "Lat/lon (WGS84)",
    "중부원점 (GRS80)": "Korea Central Belt (GRS80)",
    "서부원점 (GRS80)": "Korea West Belt (GRS80)",
    "동부원점 (GRS80)": "Korea East Belt (GRS80)",
    "동해원점 (GRS80)": "Korea East Sea Belt (GRS80)",
    "UTM-K (GRS80)": "UTM-K (GRS80)",
    "UTM 52N (WGS84)": "UTM 52N (WGS84)",
    "옛 중부원점 (Bessel, 보정)": "Old Central Belt (Bessel, modified)",
    "옛 중부원점 (Bessel)": "Old Central Belt (Bessel)",
    "좌표계": "Coordinates",
    "좌표 칸이 받는 좌표계. 평면 좌표계면 팝업에도 그 좌표가 뜬다":
        "Coordinate system for the search box. For planar systems the popup also shows those coordinates",
    "{name} — 동 북 두 수, 또는 N 420005 E 232509 · 주소·장소도 된다":
        "{name} — easting northing, or N 420005 E 232509 · addresses and places work too",
    "동 {e} · 북 {n}": "E {e} · N {n}",
    "적은 차례": "as typed",
    "좌표": "Coordinate",
    "두 차례 모두 한반도 안이다 — 고른다. 이름을 붙여 적으면(N 420005 E 232509) 곧장 간다.":
        "Both orders land in Korea — pick one. Label them (N 420005 E 232509) to go straight there.",
    "동": "E",
    "북": "N",
    "읽지 못한 것 {n}개를 건너뛰었다 (기하가 없거나 깨졌거나 GeometryCollection)":
        "Skipped {n} unreadable features (no geometry, broken, or GeometryCollection)",
    "모양 하나의 꼭짓점이 {n}개로 너무 많다 (한도 {max}개).":
        "One shape has {n} vertices — too many (limit {max}).",
    "꼭짓점이 모두 {max}개를 넘는다. 파일을 나눠 올린다.":
        "More than {max} vertices in total. Split the file and upload again.",
    # 점 레이어 — 그린란드 정부 포털 (grportal.py, map.js 의 vectorLayerFor)
    "그런 점 레이어가 없다": "No such point layer",
    "그린란드 정부 광물자원 포털": "Government of Greenland mineral portal",
    "포털의 원본 항목 — 이용 조건 표시 없음": "Source item on the portal — no licence stated",
    "이용 조건 표시 없음": "no licence stated",
    "색은 포털이 시료 갈래마다 매긴 것이다": "Colours are the portal's, one per sample type",
    "점을 받지 못했다": "Could not load the points",
    "받는 중…": "Loading…",
    "열기": "open",
    # 연대 갈래 (map.js 의 AGE_CLASSES) — ICS 국제층서표의 이름
    "신생대": "Cenozoic",
    "중생대": "Mesozoic",
    "고생대": "Paleozoic",
    "신원생대": "Neoproterozoic",
    "중원생대": "Mesoproterozoic",
    "고원생대": "Paleoproterozoic",
    "신시생대": "Neoarchean",
    "중시생대 이전": "Mesoarchean and older",
    # 남극 지질도 (geomap.py)
    "남극 지질도 자료(GeoMAP)가 서버에 없다": "The Antarctic geology data (GeoMAP) is not on the server",
    # 얀마옌 지질도 (janmayen.py, map.js 의 dataLegend)
    "얀마옌 지질도 자료(NPI)가 서버에 없다": "The Jan Mayen geology data (NPI) is not on the server",
    "얀마옌 지질도 자료(NPI)를 읽지 못했다": "Could not read the Jan Mayen geology data (NPI)",
    "원본 자료 — Norsk Polarinstitutt, CC BY 4.0": "Source dataset — Norsk Polarinstitutt, CC BY 4.0",
    "그런 타일은 없다": "No such tile",
    # 스발바르 — 노르웨이 극지연구소 (npolar.py·map.js, devlog 021)
    "Sentinel-2 위성 (NPI)": "Sentinel-2 satellite (NPI)",
    "노르웨이 극지연구소 · Copernicus Sentinel-2. CC BY 4.0":
        "Norwegian Polar Institute · Copernicus Sentinel-2. CC BY 4.0",
    "스발바르 지형도 (NPI)": "Svalbard topographic map (NPI)",
    "노르웨이 극지연구소. CC BY 4.0": "Norwegian Polar Institute. CC BY 4.0",
    "이 지역에서는 좌표로 간다 — 주소·장소는 한국, 지명은 스발바르·북극 탭에서 찾는다":
        "Here you go by coordinates — addresses and places work in Korea, place names in the Svalbard and Arctic tabs",
    "좌표·지명으로 이동 — 78.223, 15.647 · Longyearbyen": "Go to coordinates or a place name — 78.223, 15.647 · Longyearbyen",
    "좌표로 이동 — 위도, 경도 (예: {example})": "Go to coordinates — latitude, longitude (e.g. {example})",
    "지명 검색: 노르웨이 극지연구소 (스발바르)": "Place names: Norwegian Polar Institute (Svalbard)",
    "찾은 것이 없다 — 스발바르 지명을 넣어 본다": "Nothing found — try a Svalbard place name",
    "지명": "Place name",
    # 일본 — GSJ 심리스 지질도·국토지리원 배경 (gsj.py·map.js, devlog 024)
    "일본 담색 지도 (국토지리원)": "Japan pale map (GSI)",
    "일본 국토지리원. 지질도 밑에 깔기 좋다": "Geospatial Information Authority of Japan. Good under a geological map",
    "일본 표준 지도 (국토지리원)": "Japan standard map (GSI)",
    "일본 국토지리원": "Geospatial Information Authority of Japan",
    "일본 항공사진 (국토지리원)": "Japan aerial photos (GSI)",
    "일본 국토지리원. 일본 밖은 줌 8 까지만 그린다":
        "Geospatial Information Authority of Japan. Outside Japan it draws only up to zoom 8",
    "일본 음영기복 (국토지리원)": "Japan hillshade (GSI)",
    "일본 국토지리원. 지형을 지질도와 견줄 때":
        "Geospatial Information Authority of Japan. For comparing terrain with geology",
    "줌 {n} 부터 그려진다": "Drawn from zoom {n}",
    "선·기호의 범례는 GSJ 가 따로 주지 않는다": "GSJ gives no separate legend for lines and symbols",
    "원본 뷰어에서 본다 — GSJ": "See it in the original viewer — GSJ",
    # 중국 — USGS geo3al (geo3al.py·views.py·map.js, devlog 025)
    "중국 지질도 자료(USGS geo3al)가 서버에 없다": "The China geology data (USGS geo3al) is not on the server",
    "중국 지질도 자료(USGS geo3al)를 읽지 못했다": "Could not read the China geology data (USGS geo3al)",
    "원본 자료 — USGS geo3al (OFR 97-470F). 연구실 내부용, 재배포 금지":
        "Source dataset — USGS geo3al (OFR 97-470F). Internal lab use only, no redistribution",
    "관입 화성암": "Intrusive igneous rock",
    "분출 화성암": "Extrusive igneous rock",
    "초염기성암·오피올라이트": "Ultrabasic rock or ophiolite",
    "풍성 퇴적물": "Eolian deposits",
    "기호 풀이 없음 (x)": "Code not explained (x)",
    "지금 보는 범위에 든 것 {n}칸": "{n} units in the current extent",
    "지금 보는 범위에는 칠해진 것이 없다": "Nothing is mapped in the current extent",
    "…그 밖 {n}칸 — 더 들어가면 줄어든다": "…and {n} more — zoom in to narrow it down",
    "layer·lat·lon 이 없다": "layer, lat or lon is missing",
    "범례가 없는 레이어다": "This layer has no legend",
    "bbox 가 없다": "bbox is missing",
    # 암맥 기록 — phyloserver (devlog 026)
    "산성암맥": "Felsic dikes",
    "중성암맥": "Intermediate dikes",
    "염기성암맥": "Mafic dikes",
    "석영맥·광맥": "Quartz & ore veins",
    "그 밖·미상": "Other / unknown",
    "암맥 {n}건 · 줌 {z} 아래에서는 도폭 {m}곳의 로즈": "{n} dikes · below zoom {z}, rose diagrams for {m} map sheets",
    "갈래는 적힌 암석 이름에서 GSM 이 가른 것이다": "Classes are GSM's grouping of the recorded rock names",
    "원본 기록 — phyloserver": "Original records — phyloserver",
}


# ── 속성 이름 ────────────────────────────────────────────────────────
#
# 상류가 팝업에 주는 열 이름. 2026-09-27 에 레이어 61 개를 두세 곳씩 눌러
# 모았다. 영문 열(`symnum`·`GRAY_INDEX` …)은 그대로 둔다.

PROP_EN = {
    "지질시대": "Geologic age",
    "시대": "Age",
    "도폭": "Map sheet",
    "도폭명": "Sheet name",
    "도첩명": "Map series",
    "도곽": "Map frame",
    "지층명": "Formation",
    "지층": "Formation",
    "지질기호": "Symbol",
    "기호": "Symbol",
    "대표암석": "Main rocks",
    "대표암상": "Main lithology",
    "암석명": "Rock name",
    "정보": "Info",
    "설명": "Description",
    "영문지층명": "Formation (English)",
    "영문지질시대": "Geologic age (English)",
    "영문도곽": "Map frame (English)",
    "제작연도": "Year made",
    "발행년도": "Year published",
    "연도": "Year",
    "조사자": "Surveyed by",
    "작성자": "Compiled by",
    "저자": "Author",
    "축척": "Scale",
    "출처": "Source",
    "링크": "Link",
    "키워드": "Keywords",
    "위치": "Location",
    "지질노두명": "Outcrop",
    "지질노두명_영문": "Outcrop (English)",
    "지질분포": "Distribution",
    "지체구조구": "Tectonic province",
    "지체구조운동": "Tectonic event",
    "심도": "Depth",
    "유기탄소량": "Organic carbon",
    "퇴적물명": "Sediment",
    "퇴적물시기": "Sediment age",
    "표층퇴적물": "Surface sediment",
    "평균입도1": "Mean grain size 1",
    "평균입도2": "Mean grain size 2",
    "평균입도3": "Mean grain size 3",
    "등층후유형": "Isopach type",
    "해안선유형": "Coastline type",
    "물탐측선명": "Survey line",
    "이름표": "Label",
    # GEUS 속성 (geus.FRIENDLY)
    "지질 단위": "Geological unit",
    "최소 연대 (Ma)": "Minimum age (Ma)",
    "최대 연대 (Ma)": "Maximum age (Ma)",
    # VWorld 속성 (vworld.FRIENDLY) — "지질 참고" 레이어군, devlog 020
    "구분": "Class",
    "길이 (m)": "Length (m)",
    "수문지질단위": "Hydrogeologic unit",
    "시도": "Province",
    "시군구": "City / county",
    "읍면동": "Town / township",
    "리": "Village (ri)",
    "행정구역": "Administrative area",
    "지구": "Zone",
    "산": "Mountain",
    "구간": "Section",
    "난이도": "Difficulty",
    "지명": "Place name",
    "하천명": "River",
    "하천 등급": "River class",
    # 그린란드 정부 포털의 점 레이어 (grportal.LAYERS 의 label)
    "시료 번호": "Sample no.",
    "연대 (Ma)": "Age (Ma)",
    "오차 (Ma)": "Uncertainty (Ma)",
    "해석": "Interpretation",
    "광물": "Mineral",
    "측정법": "Technique",
    "계산법": "Approach",
    "암상": "Lithology",
    "암석 갈래": "Rock type",
    "지괴": "Terrane",
    "단위": "Unit",
    "문헌": "Reference",
    "GEUS 상세": "GEUS details",
    "이름": "Name",
    # 얀마옌 지질도 (janmayen.LABELS)
    "노르웨이어 이름": "Norwegian name",
    "층서 계통": "Lithostratigraphic hierarchy",
    "암층 코드": "Unit code (geo_code)",
    # 노르웨이 극지연구소 — 스발바르·드로닝모드랜드 (npolar.FRIENDLY·POINTS, devlog 021)
    "주 암상": "Main lithology",
    "시대 하한": "Age (base)",
    "시대 상한": "Age (top)",
    "상위 단위": "Superior unit",
    "갈래": "Type",
    "연대 근거": "Dating method",
    "정확도": "Accuracy",
    "범례 번호": "Legend code",
    "층서명": "Stratigraphic unit",
    "모식지": "Type section / area",
    "모식지 갈래": "Nature of section",
    "UTM 위치": "UTM position",
    "번호": "ID",
    "옛 이름": "Former name",
    "비고": "Remarks",
    "층서 사전": "Stratigraphic lexicon",
    "채취 연도": "Year collected",
    "탐사": "Expedition",
    "위치 정확도": "Position accuracy",
    "보관함": "Cabinet",
    "시료 보관소": "Sample archive",
    "사진": "Photo",
    "연대 갈래": "Age type",
    "암석": "Rock",
    "문헌 번호": "Reference no.",
    # 일본 — GSJ 심리스 지질도 (gsj.friendly, devlog 024)
    "암상 (원문)": "Lithology (original)",
    "위치 근거": "Location basis",
    "기재": "Description",
    "지점": "Locality",
    "시료": "Samples",
    "광종": "Commodity",
    "광종 무리": "Commodity group",
    "경제성": "Economic status",
    "보고서": "Report",
    "시료 갈래": "Sample type",
    "시료 기재": "Sample description",
    "채취 지점": "Locality",
    "채취자": "Collector",
    "채취일": "Collected",
    # 중국 — USGS geo3al (geo3al.LABELS)
    "암종": "Rock type",
    "원도 기호": "Source map code",
    # 남극 GeoMAP 속성 (geomap.PROPS)
    "간추린 지질": "Simplified geology",
    "노두 갈래": "Outcrop type",
    "층서 단위": "Stratigraphic rank",
    "지역": "Region",
    "신뢰도": "Confidence",
    "관찰 방법": "Observation method",
    "위치 정확도 (m)": "Positional accuracy (m)",
    "출처 문헌": "Reference",
    "단층 갈래": "Fault type",
    "노출": "Exposure",
    "위치 정확성": "Location accuracy",
    "운동 갈래": "Movement type",
    "경사 (°)": "Dip (°)",
    "경사 방향 (°)": "Dip direction (°)",
    "자료 품질 (1–5)": "Data quality (1–5)",
    "노두": "Outcrop",
    "자료": "Dataset",
    # 암맥 기록 — phyloserver (devlog 026)
    "주향 (끝점에서 잰 값)": "Strike (from endpoints)",
    "메모": "Memo",
    "기록 번호": "Record ID",
    "phyloserver 기록": "phyloserver record",
    "암맥 수": "Dikes",
    "평균 주향": "Mean strike",
}


# ── 지질시대 ────────────────────────────────────────────────────────
#
# 상류의 값은 낱말을 겹쳐 쓴다 — `현생누대 고생대 석탄기~페름기`,
# `트라이아스기 후기~쥐라기 전기`. 낱말마다 옮기고 차례는 둔다. 옛 표기
# (오오도비스기·쥬라기·고제3기 — 100만 지질도)도 받는다. 모르는 낱말이
# 하나라도 있으면 **통째로 원문을 둔다** — 반만 옮긴 것은 틀린 것보다 나쁘다.

AGE_WORDS = {
    "선캄브리아시대": "Precambrian",
    "시생누대": "Archean", "시생대": "Archean",
    "고시생대": "Paleoarchean", "중시생대": "Mesoarchean", "신시생대": "Neoarchean",
    "원생누대": "Proterozoic", "원생대": "Proterozoic",
    "고원생대": "Paleoproterozoic", "중원생대": "Mesoproterozoic", "신원생대": "Neoproterozoic",
    "시데리아기": "Siderian", "리아시아기": "Rhyacian",
    "오로세이라기": "Orosirian", "스타테로스기": "Statherian",
    "칼리미아기": "Calymmian", "엑타시스기": "Ectasian", "스테노스기": "Stenian",
    "토노스기": "Tonian", "크라이오제니아기": "Cryogenian", "에디아카라기": "Ediacaran",
    "현생누대": "Phanerozoic",
    "고생대": "Paleozoic",
    "캄브리아기": "Cambrian", "캠브리아기": "Cambrian",
    "오르도비스기": "Ordovician", "오오도비스기": "Ordovician",
    "실루리아기": "Silurian", "사일루리아기": "Silurian",
    "데본기": "Devonian", "석탄기": "Carboniferous", "페름기": "Permian",
    "중생대": "Mesozoic",
    "트라이아스기": "Triassic", "쥐라기": "Jurassic", "쥬라기": "Jurassic",
    "백악기": "Cretaceous",
    "신생대": "Cenozoic",
    "고진기": "Paleogene", "고제3기": "Paleogene",
    "신진기": "Neogene", "신제3기": "Neogene",
    "제3기": "Tertiary", "제4기": "Quaternary",
    "팔레오세": "Paleocene", "에오세": "Eocene", "올리고세": "Oligocene",
    "마이오세": "Miocene", "플라이오세": "Pliocene",
    "플라이스토세": "Pleistocene", "홀로세": "Holocene",
}
#: 앞 낱말을 꾸미는 말. 영어는 앞에 둔다 — `트라이아스기 후기` → `Late Triassic`.
AGE_MODIFIERS = {"전기": "Early", "중기": "Middle", "후기": "Late"}
#: 통째로 옮기는 값.
AGE_WHOLE = {"미분류": "Unclassified", "시대 미상": "Age unknown", "시대미상": "Age unknown",
             # 지체구조도(`L_1M_tectonic_litho`)
             "고생대화성활동": "Paleozoic igneous activity"}


def age_en(value: str) -> str:
    """지질시대 값 하나를 영어로. 못 옮기면 원문을 그대로 돌려준다."""
    text = str(value or "").strip()
    if not text:
        return value
    if text in AGE_WHOLE:
        return AGE_WHOLE[text]
    parts, last_noun = [], ""
    for part in re.split(r"\s*[~\-]\s*", text):
        words = []
        for word in part.replace("시대 미상", "시대미상").split():
            if word in AGE_MODIFIERS and not words and last_noun:
                # `원생대 후기-전기` 의 뒤쪽처럼 꾸밈말만 오면 앞의 낱말을 잇는다
                words.append(f"{AGE_MODIFIERS[word]} {last_noun}")
            elif word in AGE_MODIFIERS and words:
                words[-1] = f"{AGE_MODIFIERS[word]} {words[-1]}"
            elif word in AGE_WORDS:
                words.append(AGE_WORDS[word])
                last_noun = AGE_WORDS[word]
            elif word in AGE_WHOLE:
                words.append(AGE_WHOLE[word])
            else:
                return value
        parts.append(" ".join(words))
    return " – ".join(parts)


# ── 지질시대 — 거꾸로 (영어 → 한국어) ──
#
# 노르웨이 극지연구소(NPI)의 지질도는 시대를 **영문 ICS 명칭**으로 준다 —
# `late Paleocene`·`Early - Middle Triassic`·`Carboniferous - Permian`. 한국어판에서는
# 위의 표를 거꾸로 써서 옮긴다(devlog 021). 규칙은 `age_en` 과 같다 — 모르는
# 낱말이 하나라도 있으면 **통째로 원문을 둔다.** 절(Age) 이름(`Bashkirian`·
# `Aptian`)은 한국어 표기가 하나로 굳지 않아 표에 넣지 않았다 — 그런 값은 원문이다.

#: 영어 → 한국어. `AGE_WORDS` 에서 먼저 나온 한국어를 고른다(`시생누대`·`고진기`).
AGE_WORDS_KO = {}
for _ko, _en in AGE_WORDS.items():
    AGE_WORDS_KO.setdefault(_en.lower(), _ko)
# 영국식 철자 — NPI 가 섞어 쓴다(`Palaeoproterozoic`·`Early Palaeozoic`)
for _en in list(AGE_WORDS_KO):
    if "paleo" in _en:
        AGE_WORDS_KO.setdefault(_en.replace("paleo", "palaeo"), AGE_WORDS_KO[_en])
AGE_WORDS_KO.setdefault("archaean", AGE_WORDS_KO["archean"])
AGE_MODIFIERS_KO = {"early": "전기", "middle": "중기", "late": "후기"}
#: 사이를 잇는 말. 범위는 상류(KIGAM)처럼 `~` 로 붙여 적는다
AGE_JOINERS_KO = {"-": "~", "–": "~", "and/or": " 및/또는 ", "or": " 또는 ", "and": " 및 ",
                  ",": ", ", ";": ", "}
_AGE_TOKEN = re.compile(r"and/or|[A-Za-z]+|\?|[-–,;]")


def age_ko(value: str) -> str:
    """영문 지질시대 값 하나를 한국어로. 못 옮기면 원문을 그대로 돌려준다.

        late Paleocene              → 팔레오세 후기
        Early - Middle Triassic     → 트라이아스기 전기~중기
        Carboniferous - Permian     → 석탄기~페름기
        Neoproterozoic (?)          → 신원생대(?)
    """
    text = str(value or "").strip()
    if not text:
        return value
    rest = _AGE_TOKEN.sub("", text.replace("(?)", "?"))
    if rest.replace("(", "").replace(")", "").strip():
        return value                                   # 숫자·괄호 말 같은 모르는 것이 섞였다
    segments, joiners, current = [], [], {"mods": [], "noun": None, "doubt": False}
    for token in _AGE_TOKEN.findall(text.replace("(?)", "?")):
        low = token.lower()
        if low in AGE_JOINERS_KO:
            if not (current["mods"] or current["noun"]):
                return value
            segments.append(current)
            joiners.append(AGE_JOINERS_KO[low])
            current = {"mods": [], "noun": None, "doubt": False}
        elif token == "?":
            # 뒤에 붙은 것(`Paleocene ?`)도, 앞에 붙은 것(`- ? Oligocene`)도 지금 조각의 것이다
            current["doubt"] = True
        elif low in AGE_MODIFIERS_KO and not current["noun"]:
            current["mods"].append(AGE_MODIFIERS_KO[low])
        elif low in AGE_WORDS_KO and not current["noun"]:
            current["noun"] = AGE_WORDS_KO[low]
        else:
            return value
    if not (current["mods"] or current["noun"]):
        return value
    segments.append(current)
    # 꾸밈말만 있는 조각(`Early - Middle Triassic` 의 앞)은 뒤 조각의 낱말을 빌린다
    out, shown = [], None
    for index, seg in enumerate(segments):
        noun = seg["noun"]
        if noun is None:
            noun = next((s["noun"] for s in segments[index + 1:] if s["noun"]), None)
            if noun is None or not seg["mods"]:
                return value
        mods = " ".join(seg["mods"])
        if noun == shown and mods:
            piece = mods                               # 앞에서 적은 낱말은 되풀이하지 않는다
        else:
            piece = f"{noun} {mods}".strip()
        shown = noun
        out.append(piece + ("(?)" if seg["doubt"] else ""))
    return "".join(p + (joiners[i] if i < len(joiners) else "") for i, p in enumerate(out))


def age_ko_stacked(value: str) -> str:
    """위 단위부터 겹쳐 적은 영문 지질시대(일본 GSJ, devlog 024)를 한국어로.

        Cenozoic Quaternary Holocene              → 신생대 제4기 홀로세
        Mesozoic Early Triassic - Late Triassic   → 중생대 트라이아스기 전기~트라이아스기 후기
        Mesozoic Jurassic Early - Middle          → 중생대 쥐라기 전기~중기
        Neogene and Paleogene                     → 신진기 및 고진기

    `age_ko` 는 한 조각에 낱말 하나를 받아 이 꼴을 못 옮긴다. 꾸밈말은 뒤 낱말에
    붙이고(`Early Triassic`), 뒤에 낱말이 없으면 앞 낱말 뒤에 둔다(`Jurassic Early`).
    규칙은 같다 — 절(Age) 이름 같은 **모르는 낱말이 하나라도 있으면 원문**이다.
    꾸밈말이 겹친 것(`late Late Pleistocene` — 후기 플라이스토세를 다시 나눈 것)도
    원문이다. "플라이스토세 후기 후기" 는 읽히지 않는다.
    """
    text = str(value or "").strip()
    if not text:
        return value
    out = []
    for index, piece in enumerate(re.split(r"\s+(-|–|and)\s+", text)):
        if index % 2:
            out.append("~" if piece in "-–" else " 및 ")
            continue
        words, pending = [], []
        for word in piece.split():
            low = word.lower()
            if low in AGE_MODIFIERS_KO:
                pending.append(AGE_MODIFIERS_KO[low])
            elif low in AGE_WORDS_KO:
                words.append(" ".join([AGE_WORDS_KO[low]] + pending))
                pending = []
            else:
                return value
            if len(pending) > 1:
                return value
        words.extend(pending)
        if not words:
            return value
        out.append(" ".join(words))
    return "".join(out)


#: 값을 지질시대로 읽는 속성 이름.
AGE_PROPS =("지질시대", "시대", "퇴적물시기")


#: 5만 도폭 칸에 딸려 오는 링크의 이름표. 상류가 붙이는 고정된 말이다.
LINK_EN = {"(원도)": "(original map)", "(수치지질도)": "(digital map)", "열기": "open"}


def props_en(props: dict) -> dict:
    """팝업에 보일 속성을 영어로. 이름은 표로, 지질시대 값은 `age_en` 으로,
    링크 이름표는 `LINK_EN` 으로. 나머지 값은 상류가 준 그대로다."""
    out = {}
    for key, value in props.items():
        if key in AGE_PROPS and isinstance(value, str):
            value = age_en(value)
        elif isinstance(value, dict) and value.get("links"):
            value = dict(value, links=[dict(link, label=LINK_EN.get(link["label"], link["label"]))
                                       for link in value["links"]])
        out[PROP_EN.get(key, key)] = value
    return out


# ── 레이어 ──────────────────────────────────────────────────────────
#
# 제목은 DB(`Layer.title`)에 한국어로 있고 사람이 손질한다. 영어 제목은
# 레이어 이름을 열쇠로 여기 둔다. 없으면 한국어 제목이 뜬다.

GROUP_EN = {
    "지질도": "Geological maps",
    "탄전지질도": "Coalfield geological maps",
    "지구물리이상도": "Geophysical anomaly maps",
    "지화학도": "Geochemical maps",
    "좋은물지도": "Groundwater quality maps",
    "해저지질도": "Marine geological maps",
    "동위원소 연대지도": "Isotope age maps",
    "그 밖": "Other",
    "지질 참고": "Geological reference",
    # 그린란드 (GEUS)
    "야외 관찰": "Field observations",
    "지화학": "Geochemistry",
    "탄성파 탐사": "Seismic surveys",
    # 그린란드 정부 포털
    "시료·연대 (정부 포털)": "Samples & ages (government portal)",
    # 남극 (GeoMAP)
    "GeoMAP 지질도": "GeoMAP geological maps",
    # 얀마옌 (NPI)
    "얀마옌 지질 (NPI)": "Jan Mayen geology (NPI)",
    # 노르웨이 극지연구소 (npolar.py, devlog 021)
    "스발바르 지질 (NPI)": "Svalbard geology (NPI)",
    "스발바르 시료·층서 (NPI)": "Svalbard samples & stratigraphy (NPI)",
    "드로닝모드랜드 (NPI)": "Dronning Maud Land (NPI)",
    # 일본 (gsj.py, devlog 024)
    "심리스 지질도 (GSJ)": "Seamless geological map (GSJ)",
    # 중국 (geo3al.py, devlog 025)
    "중국·동아시아 지질 (USGS)": "China & East Asia geology (USGS)",
    # 우리가 모은 자료로 그린 레이어 — 첫째가 phyloserver 의 암맥 (devlog 026)
    "커스텀 지질도": "Custom geological maps",
}

LAYER_EN = {
    "L_1M_Geology_Map": "1:1M geology",
    "L_250K_Geology_Map": "1:250K geology",
    "L_50K_Geology_Map": "1:50K geology",
    "l_50k_geology_frame_latest": "1:50K sheet index",
    "L_10k_coalfield_geologic_map": "1:10K coalfield geology",
    "L_25k_coalfield_geologic_map": "1:25K coalfield geology",
    "Bouguer_Gravity_Raster_2018": "Bouguer gravity anomaly",
    "Magnetic_Raster_2018": "Magnetic anomaly",
    "Isostatic_Gravity_Raster_2018": "Isostatic gravity anomaly",
    "L_geochemMP_CU": "Copper (Cu)",
    "L_geochemMP_PB": "Lead (Pb)",
    "L_geochemMP_NI": "Nickel (Ni)",
    "L_geochemMP_RB": "Rubidium (Rb)",
    "L_geochemMP_LI": "Lithium (Li)",
    "L_geochemMP_MGO": "Magnesium (MgO)",
    "L_geochemMP_MNO": "Manganese (MnO)",
    "L_geochemMP_V": "Vanadium (V)",
    "L_geochemMP_BA": "Barium (Ba)",
    "L_geochemMP_SW_PH": "Stream water pH",
    "L_geochemMP_SR": "Strontium (Sr)",
    "L_geochemMP_ZN": "Zinc (Zn)",
    "L_geochemMP_SW_EC": "Stream water conductivity",
    "L_geochemMP_ZR": "Zirconium (Zr)",
    "L_geochemMP_FE2O3": "Iron (Fe₂O₃)",
    "L_geochemMP_K2O": "Potassium (K₂O)",
    "L_geochemMP_CAO": "Calcium (CaO)",
    "L_geochemMP_CO": "Cobalt (Co)",
    "L_geochemMP_CR": "Chromium (Cr)",
    "L_geochemMP_TIO2": "Titanium (TiO₂)",
    "gw_loct_att": "Water source information",
    "good_water_rgb_th": "Groundwater — hardness",
    "good_water_rgb_si": "Groundwater — silicon",
    "good_water_rgb_na": "Groundwater — sodium",
    "good_water_rgb_mg": "Groundwater — magnesium",
    "good_water_rgb_f": "Groundwater — fluoride",
    "good_water_rgb_ph": "Groundwater — pH",
    "good_water_rgb_cl": "Groundwater — chloride",
    "good_water_rgb_ec": "Groundwater — conductivity",
    "good_water_rgb_hco3": "Groundwater — bicarbonate",
    "good_water_rgb_no3": "Groundwater — nitrate",
    "good_water_rgb_tds": "Groundwater — total dissolved solids",
    "good_water_rgb_k": "Groundwater — potassium",
    "good_water_rgb_ca": "Groundwater — calcium",
    "good_water_rgb_so4": "Groundwater — sulfate",
    "M_geology_sample_location": "Sampling locations",
    "M_geology_organic_carbon": "Organic carbon content",
    "M_geology_magnetic": "Magnetic properties",
    "M_geology_gravity": "Gravity properties",
    "M_geology_seismic_sections": "Seismic section interpretation",
    "Marine_geology_prospect": "Survey track lines",
    "M_geology_deposits_type": "Surface sediment types",
    "M_geology_deposits_mean_particle": "Surface sediment mean grain size",
    "M_geology_topography": "Seafloor topography",
    "M_geology_deposits_isopach": "Seafloor sediment isopach",
    "L_1M_isotope_ore": "Isotope ages — ore deposits",
    "L_1M_isotope_metamorphic": "Isotope ages — metamorphic rocks",
    "L_1M_isotope_plutonic": "Isotope ages — plutonic rocks",
    "L_1M_isotope_volcanic": "Isotope ages — volcanic rocks",
    "medical_clay": "Medical clay",
    "G_tectonic": "Tectonic map",
    "outcrop_korea": "Geological outcrops of Korea",
    # 지질 참고 (VWorld)
    "lt_l_gimsfault": "Faults",
    "lt_l_gimslinea": "Geological lineaments",
    "lt_c_gimshydro": "Hydrogeologic units",
    "lt_c_uj401": "Hot spring zones",
    "lt_l_frstclimb": "Hiking trails",
    "lt_p_nsnmssitenm": "National place names",
    "lt_c_wkmstrm": "Stream network",
    "lt_c_adsido": "Boundaries — provinces",
    "lt_c_adsigg": "Boundaries — cities & counties",
    "lt_c_ademd": "Boundaries — towns & townships",
    "lt_c_adri": "Boundaries — villages (ri)",
    # 그린란드 (GEUS)
    "grl_g500_lithostr_search": "1:500K geology (lithostratigraphy)",
    "lithologies": "Field lithology observations",
    "geochemistry_greenland_v2_external": "Stream sediment geochemistry",
    "geochemistry_greenland_ss_sw": "Stream sediment atlas — South & West",
    "geochemistry_greenland_ss_n": "Stream sediment atlas — North",
    "geochemistry_greenland_soil": "Soil geochemistry",
    "seismic_surveys_grl": "Seismic survey areas",
    "seismic_lines_grl": "Seismic lines",
    "seismic_3d_surveys_grl": "3D seismic surveys",
    "seismic_csem_grl": "CSEM lines",
    # 그린란드 정부 포털 (grportal.py)
    "grportal:geochron": "Geochronology",
    "grportal:mineral_occurrences": "Mineral occurrences",
    "grportal:intrusions": "Intrusions",
    "grportal:samples": "Rock & sediment samples",
    # 남극 (SCAR GeoMAP)
    "geomap_simple_geology": "Geology (simplified)",
    "geomap_chronostratigraphic": "Chronostratigraphy",
    "geomap_simple_lithology": "Lithology (simplified)",
    "geomap_faults": "Faults",
    "geomap_quality": "Data quality",
    # 얀마옌 (NPI 지질도, janmayen.py)
    "janmayen:units": "Geological units (1:250K)",
    "janmayen:lines": "Eruptive fissures, lava fronts & caldera",
    "janmayen:vents": "Eruptive centres & fumaroles",
    # 노르웨이 극지연구소 — 스발바르·드로닝모드랜드 (npolar.py)
    "npolar:svalbard_units": "Geological units (1:250K · 1:750K)",
    "npolar:svalbard_faults": "Faults & folds",
    "npolar:svalbard_paper": "Printed geological map (hillshade)",
    "npolar:svalbard_type_localities": "Lithostratigraphic type localities",
    "npolar:rock_archive": "Rock sample archive",
    "npolar:dml_units": "Geological units (1:250K · 1:5M)",
    "npolar:dml_structures": "Structures",
    "npolar:dml_tectonic": "Major tectonic boundaries",
    "npolar:dml_geochron": "Geochronology",
    "npolar:dml_samples": "Rock sample archive (Antarctica)",
    "npolar:dml_sites": "Field sites",
    # 일본 — GSJ 심리스 지질도 V2 (gsj.py)
    "gsj:geology": "1:200K seamless geology",
    "gsj:geology_level2": "1:200K seamless geology — simplified (14 classes)",
    "gsj:boundaries": "Geological boundaries",
    "gsj:faults": "Faults & flexures",
    "gsj:symbols": "Legend symbols",
    # 중국 — USGS geo3al (geo3al.py)
    "geo3al:age": "Geologic age (1:5M)",
    "geo3al:rock": "Igneous rocks & eolian deposits",
    # 연구실의 암맥 기록 — phyloserver (devlog 026)
    "phyloserver:dikes": "Dike records",
    "phyloserver:peninsula": "Korean Peninsula geology (scan)",
}
