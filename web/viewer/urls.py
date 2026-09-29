"""앱의 URL. 서브패스 접두사는 여기가 모른다 — `gsmweb/urls.py` 가 붙인다."""
from django.urls import path, re_path

from . import views

app_name = "viewer"

urlpatterns = [
    path("", views.map_view, name="map"),
    path("3d/", views.map3d_view, name="map3d"),

    # 상류 프록시. 브라우저는 인증키를 모르고 이 둘만 부른다.
    path("wms/", views.wms, name="wms"),
    path("featureinfo/", views.feature_info, name="featureinfo"),

    path("legend/", views.legend, name="legend"),
    # 벡터 레이어(단층)의 모양. 1° 칸 하나씩 (devlog 020)
    path("vector/", views.vector, name="vector"),
    # 점 레이어(그린란드 정부 포털). 타일이 아니라 GeoJSON 한 덩이다 (devlog 019)
    path("points/", views.point_layer, name="points"),

    # 남극 지질도 — 우리가 그리는 EPSG:3031 타일 (geomap.py). `@2x` 는 512 px
    re_path(r"^geomap/(?P<layer>[\w-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,7})/(?P<y>\d{1,7})(?P<retina>@2x)?\.png$",
            views.geomap_tile, name="geomap-tile"),

    # 일본 지질도 — GSJ 심리스 지질도 타일·속성·범례 (gsj.py, devlog 024). 레이어는 `gsj:` 를 뗀 이름
    re_path(r"^gsj/(?P<layer>[\w-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,5})/(?P<y>\d{1,5})\.png$",
            views.gsj_tile, name="gsj-tile"),
    # 한반도 지질도 음영판 — 우리가 잘라 둔 EPSG:5179 타일 (peninsula.py, devlog 027)
    re_path(r"^peninsula/(?P<layer>[\w-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,4})/(?P<y>\d{1,4})\.webp$",
            views.peninsula_tile, name="peninsula-tile"),
    # 3D 가 쓰는 것 — 평면 격자(5179·5181) 타일을 3857 로 다시 편다 (warp.py)
    re_path(r"^warp/(?P<upstream>peninsula|phyloserver)/(?P<layer>[\w-]+)/(?P<z>\d{1,2})/(?P<x>\d{1,6})/(?P<y>\d{1,6})\.png$",
            views.warp_tile, name="warp-tile"),
    # 한반도 지질도 — phyloserver 의 카카오 격자 타일 (phyloserver.py, devlog 026)
    re_path(r"^phyloserver/(?P<layer>[\w-]+)/(?P<level>\d{1,2})/(?P<x>\d{1,5})_(?P<y>\d{1,5})\.png$",
            views.phyloserver_tile, name="phyloserver-tile"),
    path("gsj/info/", views.gsj_info, name="gsj-info"),
    path("gsj/legend/", views.gsj_legend, name="gsj-legend"),

    path("catalog/", views.catalog_json, name="catalog"),
    path("patchnotes/", views.patch_notes, name="patchnotes"),

    path("pointsets/", views.pointset_index, name="pointset-index"),
    path("pointsets/upload/", views.pointset_upload, name="pointset-upload"),
    path("pointsets/create/", views.pointset_create, name="pointset-create"),
    path("pointsets/<int:pk>/geojson/", views.pointset_geojson, name="pointset-geojson"),
    path("pointsets/deleted/", views.pointset_deleted, name="pointset-deleted"),
    path("pointsets/deleted/<int:pk>/restore/", views.pointset_restore, name="pointset-restore"),
    path("pointsets/<int:pk>/delete/", views.pointset_delete, name="pointset-delete"),

    path("coords/parse/", views.coord_parse, name="coord-parse"),
    path("coords/project/", views.coord_project, name="coord-project"),
    path("search/", views.place_search, name="place-search"),
    # 스발바르 지명 찾기 (NPI, devlog 021) — 한국의 search/ 자리
    path("placenames/", views.place_names, name="place-names"),
    path("whereis/", views.whereis, name="whereis"),
]
