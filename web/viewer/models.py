"""자료의 층은 둘이고, 둘은 섞이지 않는다.

    레이어군 > 레이어        상류가 주는 것. 사람이 만들지 않는다
    점묶음   > 점            내가 올리는 것. 상류를 타지 않는다

화면에서만 같은 레이어 패널에 나란히 선다. 자세한 것은 CLAUDE.md 의 "자료의 층".
"""
from django.db import models


#: 지역. 화면 위의 지역 탭이 이것으로 레이어 목록을 가른다 (devlog 016).
REGIONS = (("korea", "한국"), ("greenland", "그린란드"), ("antarctica", "남극"),
           # 얀마옌 — NPI 지질도를 우리가 그린다 (devlog 022)
           ("jan_mayen", "얀마옌"))


class LayerGroup(models.Model):
    """레이어를 묶는 것. 씨앗의 `group` 문자열이 여기 행이 된다.

    이름은 **지역 안에서만** 겹치지 않는다 — 그린란드에도 "지질도" 가 있다.
    """

    name = models.CharField("이름", max_length=60)
    region = models.CharField("지역", max_length=20, choices=REGIONS, default="korea")
    order = models.IntegerField("차례", default=0)

    class Meta:
        ordering = ["region", "order", "name"]
        verbose_name = "레이어군"
        constraints = [models.UniqueConstraint(fields=["region", "name"],
                                               name="layergroup_name_per_region")]

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

    #: 어느 문으로 나가나. kigam → `kigam.py`, geus → `geus.py`, vworld → `vworld.py`,
    #: grportal → `grportal.py` (타일이 아니라 점을 통째로 받는다 — devlog 019),
    #: geomap → `geomap.py` (상류가 아니라 우리 디스크의 파일이다 — devlog 018),
    #: janmayen → `janmayen.py` (NPI 지질도 파일, 모양을 통째로 준다 — devlog 022)
    upstream = models.CharField("상류", max_length=20, default="kigam")
    #: 어떻게 그리나. wms → 상류가 그린 타일을 얹는다. vector → 모양을 받아
    #: 우리가 그린다 (단층, devlog 020). 거의 전부가 wms 다
    kind = models.CharField("그리는 법", max_length=10, default="wms",
                            choices=(("wms", "타일"), ("vector", "벡터")))

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


class Shape(models.Model):
    """점묶음에 딸린 선·면 하나. 조사 경로·권역·잡아 둔 범위 같은 것이다.

    점(`Point`)과 가른 까닭 — **점은 위경도 하나**라는 뜻을 흐리지 않으려는
    것이다(CLAUDE.md "자료의 층"). 기하는 GeoJSON 그대로(EPSG:4326) 둔다.
    공간 연산을 하지 않으므로(TODOs "하지 않기로 한 것") 그릴 수만 있으면 된다.
    `lat`·`lon` 은 범위의 한가운데 — 목록·이름표·범위 맞추기가 쓴다. devlog 012.
    """

    KINDS = (("line", "선"), ("polygon", "면"))

    pointset = models.ForeignKey(PointSet, on_delete=models.CASCADE,
                                 related_name="shapes", verbose_name="점묶음")
    kind = models.CharField("갈래", max_length=10, choices=KINDS)
    geometry = models.JSONField("기하 (GeoJSON)")
    label = models.CharField("이름표", max_length=200, blank=True)
    lat = models.FloatField("가운데 위도")
    lon = models.FloatField("가운데 경도")
    props = models.JSONField("딸린 속성", default=dict, blank=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "모양"

    def __str__(self):
        return self.label or f"{self.get_kind_display()} ({self.lat:.5f}, {self.lon:.5f})"


class PointSetDeletion(models.Model):
    """지운 점묶음의 기록 — 누가(접속한 곳)·언제·무엇을.

    **지운 것의 사본(GeoJSON)도 남긴다.** 점묶음은 사람이 올리거나 찍은 것이라
    상류에서 다시 받을 길이 없다. 잘못 지웠으면 `manage.py deleted_pointsets
    --restore <번호>` 로 되살린다. devlog 014.
    """

    name = models.CharField("이름", max_length=120)
    color = models.CharField("색", max_length=7, blank=True)
    source_filename = models.CharField("올린 파일", max_length=255, blank=True)
    created_at = models.DateTimeField("올린 때", null=True, blank=True)
    deleted_at = models.DateTimeField("지운 때", auto_now_add=True)
    client = models.CharField("지운 곳 (접속 주소)", max_length=64, blank=True)
    points = models.PositiveIntegerField("점", default=0)
    lines = models.PositiveIntegerField("선", default=0)
    polygons = models.PositiveIntegerField("면", default=0)
    snapshot = models.JSONField("사본 (GeoJSON)", default=dict)
    restored_at = models.DateTimeField("되살린 때", null=True, blank=True)

    class Meta:
        ordering = ["-deleted_at"]
        verbose_name = "지운 점묶음"

    def __str__(self):
        return f"{self.deleted_at:%Y-%m-%d %H:%M} {self.name}"


class UpstreamDay(models.Model):
    """상류에 하루 몇 번 물었나. **한계를 재지 않고 지켜보려고** 둔다.

    KIGAM 은 호출 제한의 수치를 밝히지 않는다("지나치게 잦은 호출"). 걸릴
    때까지 두드려 재면 걸리는 순간 서버 IP 가 막힌다. 그래서 두드리지 않고
    평소에 얼마나 묻는지, 차단 조짐(403·429·`Request Blocked`)이 있었는지를
    날마다 센다. `manage.py upstream_stats` 가 보여준다. devlog 010.
    """

    day = models.DateField("날짜")
    upstream = models.CharField("상류", max_length=20)     # kigam · vworld
    ok = models.PositiveIntegerField("성공", default=0)
    fail = models.PositiveIntegerField("실패", default=0)
    blocked = models.PositiveIntegerField("차단 조짐", default=0)

    class Meta:
        ordering = ["-day", "upstream"]
        constraints = [models.UniqueConstraint(fields=["day", "upstream"],
                                               name="upstream_day_once")]

    def __str__(self):
        return f"{self.day} {self.upstream} {self.ok}/{self.fail}/{self.blocked}"
