"""자료의 층은 둘이고, 둘은 섞이지 않는다.

    레이어군 > 레이어        상류가 주는 것. 사람이 만들지 않는다
    점묶음   > 점            내가 올리는 것. 상류를 타지 않는다

화면에서만 같은 레이어 패널에 나란히 선다. 자세한 것은 CLAUDE.md 의 "자료의 층".
"""
from django.db import models


class LayerGroup(models.Model):
    """레이어를 묶는 것. 씨앗의 `group` 문자열이 여기 행이 된다."""

    name = models.CharField("이름", max_length=60, unique=True)
    order = models.IntegerField("차례", default=0)

    class Meta:
        ordering = ["order", "name"]
        verbose_name = "레이어군"

    def __str__(self):
        return self.name


class Layer(models.Model):
    """상류 WMS 의 레이어 하나.

    `name` 은 상류에 그대로 넘기는 이름이다. 씨앗은 `geoOpen:` 워크스페이스
    접두사를 떼고 넣는다 — 문서화된 `/openapi/wms` 가 접두사 없는 이름을
    받기 때문이다(`L_250K_Geology_Map`).
    """

    name = models.CharField("레이어명", max_length=120, unique=True)
    title = models.CharField("제목", max_length=200)
    group = models.ForeignKey(LayerGroup, on_delete=models.PROTECT,
                              related_name="layers", verbose_name="레이어군")
    abstract = models.TextField("설명", blank=True)

    # EX_GeographicBoundingBox (EPSG:4326). 레이어로 범위를 맞출 때 쓴다.
    bbox_west = models.FloatField(null=True, blank=True)
    bbox_south = models.FloatField(null=True, blank=True)
    bbox_east = models.FloatField(null=True, blank=True)
    bbox_north = models.FloatField(null=True, blank=True)

    queryable = models.BooleanField("클릭해 속성을 읽을 수 있다", default=True)
    enabled = models.BooleanField("레이어 패널에 보인다", default=True)
    order = models.IntegerField("차례", default=0)

    # 문서화된 `/openapi/wms` 로 실제로 그려짐을 확인한 때.
    # 씨앗은 문서에 없는 주소(GetCapabilities)에서 왔으므로, 이것이 비어 있는
    # 레이어는 "상류가 안다고 말했을 뿐 오픈API 로 열렸는지는 모르는" 것이다.
    verified_at = models.DateTimeField("확인한 때", null=True, blank=True)
    verify_note = models.CharField("확인 기록", max_length=200, blank=True)

    class Meta:
        ordering = ["group__order", "order", "title"]
        verbose_name = "레이어"

    def __str__(self):
        return f"{self.title} ({self.name})"

    @property
    def bbox(self):
        vals = (self.bbox_west, self.bbox_south, self.bbox_east, self.bbox_north)
        return list(vals) if all(v is not None for v in vals) else None


class PointSet(models.Model):
    """올린 좌표 묶음 하나. CSV 한 장이 점묶음 하나가 된다."""

    name = models.CharField("이름", max_length=120)
    source_filename = models.CharField("올린 파일", max_length=255, blank=True)
    color = models.CharField("색", max_length=7, default="#e4572e")
    created_at = models.DateTimeField("올린 때", auto_now_add=True)
    visible = models.BooleanField("지도에 보인다", default=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "점묶음"

    def __str__(self):
        return f"{self.name} ({self.points.count()}점)"


class Point(models.Model):
    """점 하나. 위경도는 언제나 EPSG:4326 이다 — 화면이 3857 이어도 그렇다."""

    pointset = models.ForeignKey(PointSet, on_delete=models.CASCADE,
                                 related_name="points", verbose_name="점묶음")
    label = models.CharField("이름표", max_length=200, blank=True)
    lat = models.FloatField("위도")
    lon = models.FloatField("경도")
    # 원본의 나머지 열. 클릭하면 그대로 표로 뜬다.
    props = models.JSONField("딸린 속성", default=dict, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "점"

    def __str__(self):
        return self.label or f"({self.lat:.5f}, {self.lon:.5f})"
