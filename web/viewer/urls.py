"""앱의 URL. 서브패스 접두사는 여기가 모른다 — `gsmweb/urls.py` 가 붙인다."""
from django.urls import path

from . import views

app_name = "viewer"

urlpatterns = [
    path("", views.map_view, name="map"),

    # 상류 프록시. 브라우저는 인증키를 모르고 이 둘만 부른다.
    path("wms/", views.wms, name="wms"),
    path("featureinfo/", views.feature_info, name="featureinfo"),

    path("legend/", views.legend, name="legend"),

    path("catalog/", views.catalog_json, name="catalog"),

    path("pointsets/", views.pointset_index, name="pointset-index"),
    path("pointsets/upload/", views.pointset_upload, name="pointset-upload"),
    path("pointsets/<int:pk>/geojson/", views.pointset_geojson, name="pointset-geojson"),
    path("pointsets/<int:pk>/delete/", views.pointset_delete, name="pointset-delete"),

    path("coords/parse/", views.coord_parse, name="coord-parse"),
]
