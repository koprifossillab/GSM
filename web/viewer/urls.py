"""앱의 URL. 서브패스 접두사는 여기가 모른다 — `gsmweb/urls.py` 가 붙인다."""
from django.urls import path

from . import views

app_name = "viewer"

urlpatterns = [
    path("", views.map_view, name="map"),
    path("3d/", views.map3d_view, name="map3d"),

    # 상류 프록시. 브라우저는 인증키를 모르고 이 둘만 부른다.
    path("wms/", views.wms, name="wms"),
    path("featureinfo/", views.feature_info, name="featureinfo"),

    path("legend/", views.legend, name="legend"),
    # 점 레이어(그린란드 정부 포털). 타일이 아니라 GeoJSON 한 덩이다
    path("vector/", views.vector_layer, name="vector"),

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
    path("whereis/", views.whereis, name="whereis"),
]
