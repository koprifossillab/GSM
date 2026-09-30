/* 대돌여지도 · 온 지구 (wetherilli P06·086).
 *
 * **화성 화면(`mars.js`)을 옮겨 와 지구의 자료로 바꿨다.** 틀 — 구(Cesium)와 평면(OpenLayers)을 오가는 것,
 * 레이어 목록·카드·범례·점묶음·그리기 도구·그림 내려받기 — 은 달·화성과 같다. 고친 것은 몸과 자료다.
 *
 * - 몸 — WGS84 타원체(Cesium 의 기본). 길이·넓이는 평균 반지름(6 371.0088 km)의 구로 잰다 — `ol.sphere` 와 같은
 *   값이다. 평면은 경위도(EPSG:4326) 그대로이고, 위도 65° 너머는 지역 탭이 쓰는 극 평사도법(북 3413·남 3031)이다.
 *   달·화성은 OpenLayers 가 4326 을 지구로 재서 따로 투영을 지었지만, 여기는 지구라 빌려 쓴다
 * - 지질도(Macrostrat)·속성·범례는 서버의 문(`macrostrat.py`)을 거친다. 배경(NASA GIBS Blue Marble)·표고(AWS
 *   Terrarium)는 브라우저가 곧장 부른다 — 지역 탭의 극지 배경·3D 가 이미 그렇게 쓴다
 *
 * 화성에만 있는 것(착륙지·로버 경로·크레이터·옛 지질도·Trek 판 목록·지명 찾기)은 뺐다.
 */
(function () {
  "use strict";

  var BASE = location.pathname.replace(/earth\/?$/, "");
  var LANG = document.documentElement.lang === "en" ? "en" : "ko";
  var I18N = JSON.parse((document.getElementById("i18n-data") || {}).textContent || "{}");
  function T(text, vars) {
    var out = (LANG === "en" && I18N[text]) || text;
    if (vars) out = out.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; });
    return out;
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }
  function saved(key, fallback) {
    try { var v = localStorage.getItem(key); return v == null ? fallback : v; } catch (e) { return fallback; }
  }
  function save(key, value) {
    try { localStorage.setItem(key, String(value)); } catch (e) { /* 사생활 모드 */ }
  }
  function $(id) { return document.getElementById(id); }

  // ══ 지구와 격자 ═══════════════════════════════════════════════════
  var R = 6371008.8;                                 // 길이·넓이를 재는 구 (평균 반지름, `ol.sphere` 와 같다)
  var M_PER_DEG = Math.PI * 6378137 / 180;           // 평면(4326)의 1° — 적도 반지름으로. 축척 막대는 OpenLayers 가 잰다
  // 배경 — NASA GIBS 의 Blue Marble(500 m). 셋 다 4326·3413·3031 판이 있어 구·평면·극 평면이 같은 영상이다.
  // 구는 WMS(4326)로, 평면은 WMTS 로 받는다 — GIBS 의 4326 WMTS 는 줌 0 이 288° 한 장이라 Cesium 의 격자와 맞지 않는다
  var GIBS_WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi";
  var GIBS_WMTS = "https://gibs.earthdata.nasa.gov/wmts/epsg{e}/best/{name}/default/500m/{z}/{y}/{x}.jpeg";
  var BASES = {
    bm: { name: "BlueMarble_ShadedRelief_Bathymetry", credit: "Blue Marble shaded relief & bathymetry · NASA EOSDIS GIBS" },
    bmng: { name: "BlueMarble_NextGeneration", credit: "Blue Marble Next Generation · NASA EOSDIS GIBS" },
    relief: { name: "BlueMarble_ShadedRelief", credit: "Blue Marble shaded relief · NASA EOSDIS GIBS" },
  };
  // 지질 레이어 목록 — 달·화성과 같은 꼴이다. 이름은 서버 `earth/tiles/<이름>` 의 것
  //   info    누르면 읽는 갈래 (`earth/info/`)   legend  범례 칸의 갈래   src  카드 밑의 출처
  var CATALOG = [
    // 나라마다 가장 자세한 지도를 이어 붙인 판 — 빈 곳은 GSC 세계 지질도(1:3500만)가 채운다 (`macrostrat.py`)
    { group: "온 지구 지질도 (Macrostrat)", layers: [
      { name: "geology", title: "지질 단위", info: "geology", legend: "geology",
        src: "Macrostrat carto · CC BY 4.0" },
    ] },
    // 판 회전에 쓰는 대륙 조각의 경계 — 오늘의 것. 옛 연대에는 서버가 돌려 칠한 판이 배경이 된다 (wetherilli 091)
    { group: "판 조각 (PALEOMAP 2016)", layers: [
      { name: "plates", title: "판 조각 경계", grid: "ll", src: "PALEOMAP 2016 (Scotese) · CC BY 4.0" },
    ] },
    // 그때의 지구에만 뜨는 것 — 연대(1 Ma 부터)를 따라 타일이 바뀐다 (P07·wetherilli 097)
    //   then  1 Ma 부터만 뜬다. 오늘의 레이어는 그 반대다
    { group: "그때의 지구", layers: [
      { name: "coast", title: "옛 해안선", grid: "ll", then: true,
        src: "PaleoCoastlines v7.1 (Kocsis & Scotese 2021) · CC BY 4.0" },
    ] },
  ];
  var THEN = JSON.parse(($("then-data") || {}).textContent || "{}");
  var LAYER = {};
  CATALOG.forEach(function (g) { g.layers.forEach(function (l) { LAYER[l.name] = l; }); });
  var ALL_NAMES = Object.keys(LAYER);
  var GEO_NAMES = ALL_NAMES;
  var GEO_MAX = 16;            // 서버의 `macrostrat.MAX_ZOOM`
  function geoUrl(name) {
    if (name === "plates") return paleoUrl("edge", 0);
    if (name === "coast") return paleoUrl("coast", paleoOn() ? age : 0);
    return BASE + "earth/tiles/" + name + "/{z}/{x}/{y}.png";
  }
  var GEO_CREDIT = "Macrostrat (CC BY 4.0) · Peters, Husson & Czaplewski 2018, G-cubed";
  var PALEO_CREDIT = "PALEOMAP 2016 (CC BY 4.0) · Scotese 2016, PALEOMAP PaleoAtlas for GPlates";
  var COAST_CREDIT = "PaleoCoastlines v7.1 (CC BY 4.0) · Kocsis & Scotese 2021, Earth-Science Reviews";
  function creditOf(name) {
    return { geology: GEO_CREDIT, plates: PALEO_CREDIT, coast: COAST_CREDIT }[name];
  }
  // 판 조각 타일 — 서버가 연대마다 돌려 그린다(`paleo.render_tile`). 경위도 격자, 줌 0 이 180° 두 장이다
  var PALEO_MAX = 6;           // 서버의 `paleo.MAX_ZOOM`
  function paleoUrl(style, age) { return BASE + "earth/paleo/tiles/" + style + "/" + age + "/{z}/{x}/{y}.png"; }

  // ── 켠 것 — 구와 평면이 함께 쓴다. 이 브라우저에 기억한다 ──
  var look = {
    base: saved("gsm.earth.base", "bm"),
    terrain: saved("gsm.earth.terrain", "on") !== "off",
    exag: +saved("gsm.earth.exag", "15"),
  };
  if (!BASES[look.base]) look.base = "bm";
  // 연대 (wetherilli 091) — Ma, 0 이 오늘. 주소(`?age=`)가 이기고, 없으면 이 브라우저에 남긴 것
  var AGE_MAX = 1100;          // PALEOMAP 2016 이 덮는 끝
  var PALEO_FROM = 1;          // 이 연대부터는 판을 돌린 그때의 지구다. 그 안쪽은 오늘의 지구에 얹는다
  function snapAge(a) {
    if (!(a > 0)) return 0;
    if (a >= PALEO_FROM - 0.0005) return Math.min(AGE_MAX, Math.round(a));       // 판 조각 타일은 1 Myr 마다다
    return Math.max(0.001, Math.round(a * 1000) / 1000);                         // 1 ka 마다
  }
  var age = snapAge(parseFloat(new URLSearchParams(location.search).get("age") || saved("gsm.earth.age", "0")));
  function paleoOn() { return age >= PALEO_FROM; }
  // 켠 지질 레이어 — 맨 앞이 위다. `[{name, opacity}]`. 처음이면 지질 단위 하나를 반쯤 비치게
  var active = (function () {
    try {
      var list = JSON.parse(saved("gsm.earth.layers", "null"));
      if (Array.isArray(list)) {
        return list.filter(function (e) { return e && LAYER[e.name]; })
                   .map(function (e) { return { name: e.name, opacity: isFinite(e.opacity) ? +e.opacity : 1 }; });
      }
    } catch (e) { /* 깨진 값 */ }
    return [{ name: "geology", opacity: 0.6 }];
  })();
  // 옛 해안선(097)은 처음 한 번 켜 둔다 — 전에 기억한 목록에도. 사람이 끄면 그대로 꺼진다
  if (saved("gsm.earth.coast.added", "") !== "1") {
    if (!active.some(function (e) { return e.name === "coast"; })) active.push({ name: "coast", opacity: 1 });
    save("gsm.earth.coast.added", "1");
    save("gsm.earth.layers", JSON.stringify(active));
  }
  function entryOf(name) { return active.filter(function (e) { return e.name === name; })[0]; }
  function isOn(name) { return !!entryOf(name); }
  function saveLayers() { save("gsm.earth.layers", JSON.stringify(active)); }

  // ══ 구 — Cesium ═══════════════════════════════════════════════════
  // 몸은 Cesium 의 기본(WGS84)이다. 달·화성처럼 구를 따로 짓지 않는다 — 지구의 자료가 다 WGS84 다
  var ELL = Cesium.Ellipsoid.WGS84;
  function cesiumBase(key) {
    return new Cesium.ImageryLayer(new Cesium.WebMapServiceImageryProvider({
      url: GIBS_WMS, layers: BASES[key].name, parameters: { format: "image/jpeg", transparent: false },
      tilingScheme: new Cesium.GeographicTilingScheme(), maximumLevel: 8, credit: BASES[key].credit,
    }));
  }

  // 지형 — AWS Terrarium(3D 가 쓰는 것과 같다). 메르카토르 격자라 위도 ±85° 너머는 평평하다. 256 칸 타일을 받아
  // 높이로 푼 뒤 65×65 로 뽑는다 — 색을 먼저 줄이면 Terrarium 의 세 바이트가 따로 섞여 높이가 튄다
  var DEM_SIZE = 65;
  var DEM_MAX = 12;            // 서버의 `elevation.TERRARIUM_ZOOM`. 그 너머는 부모 격자를 늘려 쓴다
  var DEM_URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";
  var demMemo = {};
  function demGrid(x, y, level) {
    var id = level + "/" + x + "/" + y;
    if (!demMemo[id]) {
      demMemo[id] = fetch(DEM_URL.replace("{z}", level).replace("{x}", x).replace("{y}", y)).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.blob();
      }).then(function (blob) {
        return createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
      }).then(function (bitmap) {
        var n = bitmap.width, canvas = document.createElement("canvas");
        canvas.width = canvas.height = n;
        var ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(bitmap, 0, 0);
        var px = ctx.getImageData(0, 0, n, n).data;
        var src = new Float32Array(n * n);
        for (var i = 0; i < src.length; i++) src[i] = px[i * 4] * 256 + px[i * 4 + 1] + px[i * 4 + 2] / 256 - 32768;
        return sampleGrid(src, n, 0, 0, 1);
      }).catch(function () {
        delete demMemo[id];                    // 다음에 다시 묻는다. 이번에는 평평하게
        return new Float32Array(DEM_SIZE * DEM_SIZE);
      });
    }
    return demMemo[id];
  }
  /** `n`×`n` 격자의 한 조각([ox, oy] 에서 폭 `span`, 0–1)을 65×65 로 겹선형으로 뽑는다 */
  function sampleGrid(src, n, ox, oy, span) {
    var out = new Float32Array(DEM_SIZE * DEM_SIZE), last = n - 1, m = DEM_SIZE - 1;
    for (var j = 0; j < DEM_SIZE; j++) {
      var fy = (oy + span * j / m) * last, y0 = Math.min(last - 1, Math.floor(fy)), ty = fy - y0;
      for (var i = 0; i < DEM_SIZE; i++) {
        var fx = (ox + span * i / m) * last, x0 = Math.min(last - 1, Math.floor(fx)), tx = fx - x0;
        var a = src[y0 * n + x0], b = src[y0 * n + x0 + 1], c = src[(y0 + 1) * n + x0], d = src[(y0 + 1) * n + x0 + 1];
        out[j * DEM_SIZE + i] = (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
      }
    }
    return out;
  }
  function heights(x, y, level) {
    if (level <= DEM_MAX) return demGrid(x, y, level);
    var k = Math.pow(2, level - DEM_MAX);
    var ax = Math.floor(x / k), ay = Math.floor(y / k);
    return demGrid(ax, ay, DEM_MAX).then(function (src) {
      return sampleGrid(src, DEM_SIZE, (x - ax * k) / k, (y - ay * k) / k, 1 / k);
    });
  }
  var DEM_CREDIT = "Terrain: Mapzen/AWS Terrain Tiles (SRTM, GMTED, ETOPO1 …)";
  var demTerrain = new Cesium.CustomHeightmapTerrainProvider({
    width: DEM_SIZE, height: DEM_SIZE, tilingScheme: new Cesium.WebMercatorTilingScheme(), callback: heights,
    credit: DEM_CREDIT,
  });
  var flatTerrain = new Cesium.EllipsoidTerrainProvider();

  // 배경은 한 겹이다(`cBase`). 달은 밑을 깔았지만(043) 지구의 배경은 모두 온 지구를 덮는다
  var cBase = cesiumBase(look.base);
  var viewer = new Cesium.Viewer("globe", {
    baseLayer: cBase,
    terrainProvider: look.terrain && !paleoOn() ? demTerrain : flatTerrain,
    baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
    navigationHelpButton: false, animation: false, timeline: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false,
  });
  var scene = viewer.scene;
  // 하늘의 대기는 둔다 — 지구다. 땅의 대기(푸른 안개)는 지질도의 색을 흐려 끈다
  scene.globe.showGroundAtmosphere = false;
  scene.globe.enableLighting = false;
  // 지형 뒤의 것은 가린다 — 끄면 자전축처럼 지구 속을 지나는 선이 가까이서 땅 위로 비친다 (045)
  scene.globe.depthTestAgainstTerrain = true;
  scene.globe.baseColor = Cesium.Color.fromCssColorString("#0b1a2a");
  scene.globe.maximumScreenSpaceError = 3;
  scene.fog.enabled = false;
  if (scene.moon) scene.moon.show = false;
  if (scene.sun) scene.sun.show = false;
  scene.backgroundColor = Cesium.Color.BLACK;
  scene.verticalExaggeration = look.exag / 10;
  window.__gsmEarth = viewer;

  // 지질도는 3857 타일이다 — 구도 메르카토르 격자로 받는다
  var cGeo = {};
  function cPaleoProvider(url, credit) {
    return new Cesium.UrlTemplateImageryProvider({
      url: url, tilingScheme: new Cesium.GeographicTilingScheme(), maximumLevel: PALEO_MAX,
      hasAlphaChannel: true, credit: credit,
    });
  }
  GEO_NAMES.forEach(function (name) {
    var layer = viewer.imageryLayers.addImageryProvider(LAYER[name].grid === "ll" ? cPaleoProvider(geoUrl(name), creditOf(name))
      : new Cesium.UrlTemplateImageryProvider({
      url: geoUrl(name), tilingScheme: new Cesium.WebMercatorTilingScheme(), maximumLevel: GEO_MAX,
      hasAlphaChannel: true, credit: creditOf(name),
    }));
    layer.show = false;
    cGeo[name] = layer;
  });

  // ══ 평면 — OpenLayers ═════════════════════════════════════════════
  //
  // 투영은 셋이다. 적도 쪽은 경위도(EPSG:4326, 도) 그대로다 — GIBS 의 4326 판을 옮기지 않고 받는다(배경의 영상
  // 보정이 WebGL 타일이라 옮겨 그리기를 못 한다, 042). 위도 65° 너머는 지역 탭과 같은 극 평사도법 — 북 3413
  // (기준 위도 70°, 경도 −45° 가 아래), 남 3031(기준 위도 −71°). 둘 다 GIBS 의 극지 격자(±4 194 304 m)로 편다.
  // 지질도(3857)는 OpenLayers 가 옮겨 그린다 — 위도 ±85° 너머는 없다
  proj4.defs("EPSG:3413", "+proj=stere +lat_0=90 +lat_ts=70 +lon_0=-45 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs");
  proj4.defs("EPSG:3031", "+proj=stere +lat_0=-90 +lat_ts=-71 +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs");
  ol.proj.proj4.register(proj4);
  var LL = ol.proj.get("EPSG:4326");
  var EQC = LL;                            // 화성의 `EQC` 자리 — 지구는 경위도 그대로다
  var POLAR_HALF = 4194304;                // GIBS 극지 격자의 반 폭
  var POLAR_LAT = 65;                      // 이 위도 너머는 극 평면. 넘나드는 문턱은 ±2° 되돌이
  var POLAR_TS = { n: 70, s: 71 };         // 참 축척의 위도 — 3413·3031 의 `lat_ts`
  function polarProj(code, pole) {
    var p = ol.proj.get(code);
    p.setExtent([-POLAR_HALF, -POLAR_HALF, POLAR_HALF, POLAR_HALF]);
    p.pole = pole;
    return p;
  }
  var NPS = polarProj("EPSG:3413", "n"), SPS = polarProj("EPSG:3031", "s");
  var proj = EQC;                          // 평면이 지금 쓰는 투영
  function toLL(xy) { return ol.proj.transform(xy, proj, LL); }
  function fromLL(ll) { return ol.proj.transform(ll, LL, proj); }
  /** 그 위도에 맞는 투영. 지금 투영(`cur`)을 주면 되돌이를 둔다 — 문턱에서 오락가락하지 않게 */
  function projFor(lat, cur) {
    var a = Math.abs(lat), edge = !cur ? POLAR_LAT : cur === EQC ? POLAR_LAT + 2 : POLAR_LAT - 2;
    return a < edge ? EQC : lat > 0 ? NPS : SPS;
  }
  /** 평면의 한 단위가 땅의 몇 미터인가. 경위도는 남북 1° 가, 극 평사도법은 그 위도의 축척 (구로 근사) */
  function groundScale(p, lat) {
    if (p === EQC) return M_PER_DEG;
    var ts = POLAR_TS[p.pole] * Math.PI / 180;
    return (1 + Math.sin(Math.abs(lat) * Math.PI / 180)) / (1 + Math.sin(ts));
  }
  function groundRes() {
    var v = flat.getView();
    return v.getResolution() * groundScale(proj, toLL(v.getCenter())[1]);
  }

  // GIBS 4326 격자 — 줌 0 이 512 칸 두 장(한 장이 288°), 줌마다 반씩. 여덟까지다
  var GIBS_MAX = 8;
  function gibsGrid() {
    var res = [];
    for (var z = 0; z <= GIBS_MAX; z++) res.push(0.5625 / Math.pow(2, z));
    return new ol.tilegrid.TileGrid({ extent: [-180, -90, 180, 90], origin: [-180, 90], resolutions: res, tileSize: 512 });
  }
  // GIBS 극지 격자 — 줌 0 이 512 칸 2×2 장(한 칸 8 192 m, ±4 194 304 m). 500 m 판은 넷까지다(지역 탭의 `gibsLayer` 와 같다)
  var GIBS_POLAR_MAX = 4;
  function gibsPolarGrid() {
    var res = [];
    for (var z = 0; z <= GIBS_POLAR_MAX; z++) res.push(8192 / Math.pow(2, z));
    return new ol.tilegrid.TileGrid({ extent: [-POLAR_HALF, -POLAR_HALF, POLAR_HALF, POLAR_HALF],
                                      origin: [-POLAR_HALF, POLAR_HALF], resolutions: res, tileSize: 512 });
  }
  // 배경은 WebGL 타일이다 — 영상 보정(밝기·대비·감마·채도)을 GPU 셰이더로 건다(042). 셰이더가 영상을 읽으려면
  // CORS 로 받아야 한다(GIBS 는 `*`)
  function baseSource(key) {
    var polar = proj !== EQC, e = polar ? (proj === NPS ? "3413" : "3031") : "4326";
    return new ol.source.XYZ({
      url: GIBS_WMTS.replace("{e}", e).replace("{name}", BASES[key].name),
      projection: proj, tileGrid: polar ? gibsPolarGrid() : gibsGrid(), crossOrigin: "anonymous",
      attributions: BASES[key].credit, wrapX: !polar,
    });
  }
  function baseLayer(className, key) {
    return new ol.layer.WebGLTile({
      className: className, source: baseSource(key),
      style: { variables: { exposure: 0, contrast: 0, gamma: 1, saturation: 0 },
               exposure: ["var", "exposure"], contrast: ["var", "contrast"],
               gamma: ["var", "gamma"], saturation: ["var", "saturation"] },
    });
  }
  var oBase = baseLayer("moon-base", look.base);
  // 지질도 — 3857 z/x/y 를 어느 투영에서나 OpenLayers 가 옮겨 그린다. 그래서 투영을 바꿔도 소스를 갈지 않는다
  function geoSource(name) {
    if (LAYER[name].grid === "ll") return paleoSource(geoUrl(name), creditOf(name));
    return new ol.source.XYZ({ url: geoUrl(name), maxZoom: GEO_MAX, attributions: creditOf(name),
                               crossOrigin: "anonymous" });            // CORS — 그림으로 뽑으려면 (048)
  }
  // 판 조각 — 경위도 격자(줌 0 이 180° 두 장, 256 칸). 극 평면에서는 OpenLayers 가 옮겨 그린다
  function paleoSource(url, credit) {
    var res = [];
    for (var z = 0; z <= PALEO_MAX; z++) res.push(180 / 256 / Math.pow(2, z));
    return new ol.source.XYZ({
      url: url, projection: LL, attributions: credit || PALEO_CREDIT, crossOrigin: "anonymous",
      tileGrid: new ol.tilegrid.TileGrid({ extent: [-180, -90, 180, 90], origin: [-180, 90], resolutions: res, tileSize: 256 }),
    });
  }
  var oGeo = {};
  GEO_NAMES.forEach(function (name) {
    oGeo[name] = new ol.layer.Tile({ source: geoSource(name), visible: false });
  });
  var oPoints = new ol.layer.Group({ layers: [] });
  var flat = new ol.Map({
    target: "map",
    layers: [oBase].concat(GEO_NAMES.map(function (n) { return oGeo[n]; }), [oPoints]),
    view: new ol.View({ projection: EQC, center: [0, 0], resolution: 0.05, maxResolution: 180 / 256,
                        constrainResolution: false }),
    controls: ol.control.defaults.defaults({ attributionOptions: { collapsible: true } }).extend([
      new ol.control.ScaleLine({ target: $("scalebar"), bar: true, steps: 4, text: true, minWidth: 110 }),
    ]),
  });
  window.__gsmEarthFlat = flat;
  var cRaise = {};
  GEO_NAMES.forEach(function (n) { cRaise[n] = [cGeo[n]]; });

  // ══ 구 ⇄ 평면 ═════════════════════════════════════════════════════
  //
  // 넘는 높이를 둘로 둔다(되돌이). 구에서 800 km 밑으로 곧장 내려다보면 평면으로, 평면에서 1 280 km
  // 높이만큼 멀어지면 구로. 둘이 같으면 문턱에서 오락가락한다. 화성(400·640 km)의 두 배 — 지구가 두 배 크다
  var TO_FLAT_H = 800000, TO_GLOBE_H = 1280000;
  var HOME_H = 20000000;                  // 처음·"처음 자리" 의 높이 — 반지름의 세 배쯤, 한 반구가 다 든다
  var HOME = [127.5, 30];                 // 처음 자리 — 한반도가 가운데 조금 위에 선다
  var mode = "globe";
  var autoFlat = true;                    // 손으로 구로 돌아오면, 한 번 멀어질 때까지 저절로 넘지 않는다
  var wrap = $("map-wrap");

  function fovy() {
    var f = viewer.camera.frustum;
    return f.fovy || f.fov || Math.PI / 3;
  }
  function heightToRes(h) { return 2 * h * Math.tan(fovy() / 2) / Math.max(1, scene.canvas.clientHeight); }
  function resToHeight(res) { return res * Math.max(1, scene.canvas.clientHeight) / (2 * Math.tan(fovy() / 2)); }
  function cameraLL() {
    var c = ELL.cartesianToCartographic(viewer.camera.positionWC);
    return c ? { lon: Cesium.Math.toDegrees(c.longitude), lat: Cesium.Math.toDegrees(c.latitude), h: c.height } : null;
  }
  function flyGlobe(lon, lat, h, duration) {
    var dest = Cesium.Cartesian3.fromDegrees(lon, lat, h, ELL);
    var orient = { heading: 0, pitch: -Math.PI / 2, roll: 0 };
    if (duration) viewer.camera.flyTo({ destination: dest, orientation: orient, duration: duration });
    else viewer.camera.setView({ destination: dest, orientation: orient });
  }

  function setMode(next, at) {
    if (next === mode) return;
    closePopup();
    cancelSketch();                         // 끝내지 않은 선은 넘어가지 않는다. 끝낸 것은 둘 다 그린다
    if (next === "flat") {
      var c = at || cameraLL();
      if (!c) return;
      // 위도가 투영을 고른다 — 65° 너머는 극 평사도법 (065)
      var ground = Math.min(heightToRes(c.h), heightToRes(TO_GLOBE_H) * 0.9);
      useProj(projFor(c.lat), [c.lon, c.lat], ground);
      var view = flat.getView();
      view.setCenter(fromLL([c.lon, c.lat]));
      view.setResolution(ground / groundScale(proj, c.lat));
      view.setRotation(0);
      mode = "flat";
      wrap.className = "moon-flat";
      // 숨은 구는 그리기를 멈춘다 — 안 보이는데 GPU 를 먹고, 평면의 WebGL 배경과 다툰다 (042)
      viewer.useDefaultRenderLoop = false;
      flat.updateSize();
    } else {
      var v = flat.getView(), ll = toLL(v.getCenter());
      flyGlobe(ll[0], ll[1], (at && at.h) || resToHeight(groundRes()));
      mode = "globe";
      viewer.useDefaultRenderLoop = true;
      wrap.className = "moon-globe";
    }
    save("gsm.earth.mode", mode);
  }

  /** 평면의 투영을 바꾼다 (화성의 065·달의 052). 타일 소스를 갈아 끼우고, 벡터는 모양을 옮기고, 찍고 잰 것은
   *  경위도에서 다시 그린다. 새 뷰는 `ll` 을 가운데에, 땅의 해상도 `ground` 로 연다. 바뀌었으면 true */
  function useProj(p, ll, ground) {
    if (p === proj) return false;
    var from = proj;
    proj = p;
    cancelSketch();
    function each(layer) {
      if (layer instanceof ol.layer.Group) { layer.getLayers().forEach(each); return; }
      if (layer.get("gsmBox")) layer.setExtent(ol.proj.transformExtent(layer.get("gsmBox"), LL, p, 16));
      if (layer instanceof ol.layer.Vector && layer.getSource() !== drawSource) {
        layer.getSource().getFeatures().forEach(function (f) {
          if (f.getGeometry()) f.getGeometry().transform(from, p);
        });
      }
    }
    flat.getLayers().forEach(each);
    oBase.setSource(baseSource(look.base));       // 지질도(3857)는 OpenLayers 가 새 투영으로 옮겨 그린다
    var polar = p !== EQC;
    flat.setView(new ol.View({
      projection: p, center: fromLL(ll), resolution: ground / groundScale(p, ll[1]), constrainResolution: false,
      maxResolution: polar ? 2 * POLAR_HALF / 256 : 180 / 256,
      // 가운데만 격자 안에 묶는다 — 화면 전체를 묶으면 멀리서 볼 때 가운데가 극에서 떠나지 못한다
      extent: polar ? [-POLAR_HALF, -POLAR_HALF, POLAR_HALF, POLAR_HALF] : undefined, constrainOnlyCenter: polar,
    }));
    installFlat();
    renderDrawn();
    applyTune();
    return true;
  }

  viewer.camera.moveEnd.addEventListener(function () {
    var c = cameraLL();
    if (!c) return;
    save("gsm.earth.view", JSON.stringify({
      lon: +c.lon.toFixed(5), lat: +c.lat.toFixed(5), h: Math.round(c.h),
      heading: +viewer.camera.heading.toFixed(4), pitch: +viewer.camera.pitch.toFixed(4),
    }));
    if (mode !== "globe") return;
    if (c.h > TO_FLAT_H) { autoFlat = true; return; }
    var straight = viewer.camera.pitch < Cesium.Math.toRadians(-80);
    if (autoFlat && straight && !drawing() && !tilting) setMode("flat", c);
  });
  flat.on("moveend", function () {
    if (mode !== "flat") return;
    var v = flat.getView(), ll = toLL(v.getCenter()), ground = groundRes();
    // 해상도는 땅의 미터로 적는다 — 투영마다 단위의 뜻이 달라서다 (065)
    save("gsm.earth.flat", JSON.stringify({ lon: +ll[0].toFixed(5), lat: +ll[1].toFixed(5), res: Math.round(ground) }));
    if (drawing()) return;                // 그리던 선이 끊기지 않게 (041)
    if (ground > heightToRes(TO_GLOBE_H)) { setMode("globe"); return; }
    // 극으로 가면 극 평사도법으로, 돌아오면 등거리 원통으로 — 문턱 둘레 2° 는 되돌이다 (065)
    useProj(projFor(ll[1], proj), ll, ground);
  });

  $("tool-mode").addEventListener("click", function () {
    if (mode === "globe") {
      var c = cameraLL();
      if (!c) return;
      // 멀리서 누르면 문턱 높이까지 내려와 평면으로. 극이면 극 평사도법이다 (065)
      setMode("flat", { lon: c.lon, lat: c.lat, h: Math.min(c.h, TO_FLAT_H) });
    } else {
      autoFlat = false;
      setMode("globe", { h: Math.max(resToHeight(groundRes()), TO_FLAT_H * 1.4) });
    }
  });
  $("tool-home").addEventListener("click", function () {
    if (mode === "flat") setMode("globe", { h: HOME_H });
    flyGlobe(HOME[0], HOME[1], HOME_H, 1.5);
  });
  // 북쪽 위 — 가운데 점 위로 올라가 곧장 내려다본다. 가까우면 다 내려다본 뒤 평면으로 넘어간다
  $("tool-top").addEventListener("click", function () {
    var p = pivot(true);
    if (p) { orbit(p, 0, -90, 0.8); return; }
    var c = cameraLL();
    if (c) flyGlobe(c.lon, c.lat, c.h, 0.8);
  });

  // ══ 자세 — 가운데 점 · 거리 · 방위 · 기울기 (045) ═══════════════════
  //
  // 지구 3D(MapLibre)와 같은 네 값으로 본다. **돌고 기울이는 중심은 화면 한가운데 아래의 지형 점**이다 —
  // 보던 산이 가운데에 머문다.
  //
  // - 방위는 **지구의 북극**(자전축을 그 점의 수평면에 내린 쪽)이 0°, 시계 방향. 극점 위에서는 북쪽이 없으므로
  //   **위도 89.5° 너머는 본초 자오선(경도 0°, 그리니치, +X 축) 쪽이 0°** 다 — 화성의 것을 그대로 두었다
  // - 기울기는 그 점에서 **타원체에 접하는 수평면**으로 잰다. 지형의 경사로 재면 절벽에서 값이
  //   춤춘다. 보이는 값은 지구 3D 처럼 곧장 내려다봄이 0°, 수평이 90° 다
  //
  // 손 — 오른쪽 단추(또는 Ctrl)로 끌면 기울이고 돈다. 휠은 당기고 민다. 평면에서 그렇게 끌면 같은
  // 가운데·같은 넓이로 구로 넘어가며 기울기가 붙는다. 평면은 지도 읽기, 기울이는 순간부터는 3D 다
  var cam = scene.screenSpaceCameraController;
  cam.tiltEventTypes = [Cesium.CameraEventType.MIDDLE_DRAG, Cesium.CameraEventType.PINCH,
                        Cesium.CameraEventType.RIGHT_DRAG,
                        { eventType: Cesium.CameraEventType.LEFT_DRAG, modifier: Cesium.KeyboardEventModifier.CTRL }];
  cam.zoomEventTypes = [Cesium.CameraEventType.WHEEL, Cesium.CameraEventType.PINCH];
  var tilting = false;                     // 평면에서 넘어와 끄는 중 — 그동안은 평면으로 되넘지 않는다
  var X_AXIS = new Cesium.Cartesian3(1, 0, 0), Z_AXIS = new Cesium.Cartesian3(0, 0, 1);

  /** 화면 한가운데 아래의 점과 거기까지의 거리. `terrain` 이면 지형을, 아니면 타원체를 짚는다(가볍다). */
  function pivot(terrain) {
    var cv = scene.canvas, mid = new Cesium.Cartesian2(cv.clientWidth / 2, cv.clientHeight / 2);
    var pos = null;
    if (terrain) {
      var ray = viewer.camera.getPickRay(mid);
      pos = ray && scene.globe.pick(ray, scene);
    }
    if (!pos) pos = viewer.camera.pickEllipsoid(mid, ELL);
    return pos ? { pos: pos, range: Cesium.Cartesian3.distance(viewer.camera.positionWC, pos) } : null;
  }
  /** 점 `pos` 의 수평면에서 본 카메라의 방위·기울기(도). `cesium` 이면 Cesium 의 동-북-위를 쓴다 —
   *  `lookAt` 에 넘길 값이다. 아니면 위의 기준(극 가까이는 지구 쪽)이다. */
  function anglesAt(pos, cesium) {
    var up = ELL.geodeticSurfaceNormal(pos, new Cesium.Cartesian3());
    var north, east;
    if (cesium) {
      var m = Cesium.Transforms.eastNorthUpToFixedFrame(pos, ELL);
      east = Cesium.Matrix4.getColumn(m, 0, new Cesium.Cartesian4());
      north = Cesium.Matrix4.getColumn(m, 1, new Cesium.Cartesian4());
      east = new Cesium.Cartesian3(east.x, east.y, east.z);
      north = new Cesium.Cartesian3(north.x, north.y, north.z);
    } else {
      var lat = Cesium.Math.toDegrees(ELL.cartesianToCartographic(pos).latitude);
      var ref = Math.abs(lat) > 89.5 ? X_AXIS : Z_AXIS;
      north = Cesium.Cartesian3.subtract(ref, Cesium.Cartesian3.multiplyByScalar(up, Cesium.Cartesian3.dot(ref, up),
                                                                                   new Cesium.Cartesian3()), new Cesium.Cartesian3());
      Cesium.Cartesian3.normalize(north, north);
      east = Cesium.Cartesian3.cross(north, up, new Cesium.Cartesian3());
    }
    var d = viewer.camera.directionWC;
    // 곧장 내려다보면 시선이 수평면에 그림자를 남기지 않는다 — 그때는 화면의 위쪽(카메라 up)이 향한 쪽이 방위다
    var f = Math.abs(Cesium.Cartesian3.dot(d, up)) > 0.999 ? viewer.camera.upWC : d;
    var heading = Cesium.Math.toDegrees(Math.atan2(Cesium.Cartesian3.dot(f, east), Cesium.Cartesian3.dot(f, north)));
    return { heading: (heading + 360) % 360,
             pitch: Cesium.Math.toDegrees(Math.asin(Math.max(-1, Math.min(1, Cesium.Cartesian3.dot(d, up))))) };
  }
  /** 가운데 점 둘레로 돈다 — 방위(위의 기준)·기울기(수평면 기준, −90 이 곧장 내려다봄)·거리는 그대로. */
  function orbit(p, heading, pitch, duration) {
    // 우리 방위와 Cesium 방위의 어긋남(극 가까이에서만 0 이 아니다)을 얹어 Cesium 의 값으로 바꾼다
    var shift = anglesAt(p.pos, true).heading - anglesAt(p.pos, false).heading;
    var hpr = new Cesium.HeadingPitchRange(Cesium.Math.toRadians(heading + shift), Cesium.Math.toRadians(pitch), p.range);
    if (duration) {
      viewer.camera.flyToBoundingSphere(new Cesium.BoundingSphere(p.pos, 0), { offset: hpr, duration: duration });
    } else {
      viewer.camera.lookAt(p.pos, hpr);
      viewer.camera.lookAtTransform(Cesium.Matrix4.IDENTITY);
    }
  }

  // 방위 단추(나침반) — 바늘이 지구의 북쪽을 가리킨다. 누르면 기울기는 두고 북쪽을 위로 돌린다
  var needle = $("compass-needle"), poseOut = $("pose"), topBtn = $("tool-top"), compassBtn = $("tool-compass");
  $("tool-compass").addEventListener("click", function () {
    var p = pivot(true);
    if (!p) return;
    orbit(p, 0, anglesAt(p.pos, false).pitch, 0.6);
  });
  var lastView = new Cesium.Matrix4();
  scene.postRender.addEventListener(function () {
    if (mode !== "globe" || Cesium.Matrix4.equalsEpsilon(lastView, viewer.camera.viewMatrix, 1e-9)) return;
    Cesium.Matrix4.clone(viewer.camera.viewMatrix, lastView);
    syncAxisNear();
    var p = pivot(false);
    if (!p) { poseOut.textContent = ""; topBtn.disabled = compassBtn.disabled = false; return; }
    var a = anglesAt(p.pos, false);
    needle.setAttribute("transform", "rotate(" + (-a.heading).toFixed(1) + " 12 12)");
    // 이미 북쪽이 위이고 곧장 내려다보면 "북쪽 위" 는 할 일이 없다 — 흐리게 해 눌러도 그대로인 까닭을 보인다.
    // 가운데 점을 못 짚으면(하늘을 보면) 켜 둔다 — 그때도 카메라 발밑으로 내려다보는 일은 한다
    // 방위 단추도 같다 — 북쪽이 이미 위면 흐리게. 곧장 내려다보면 방위는 화면의 위쪽으로 읽는다(`anglesAt`)
    var north = Math.min(a.heading, 360 - a.heading) < 0.5;
    compassBtn.disabled = north;
    topBtn.disabled = north && 90 + a.pitch < 0.5;
    poseOut.textContent = T("기울기 {tilt}° · 방위 {heading}°", { tilt: Math.round(90 + a.pitch), heading: Math.round(a.heading) % 360 });
  });

  // 평면에서 오른쪽 단추·Ctrl 로 끌면 — 구로 넘어가며 기울인다. 넘어간 뒤의 끌기는 우리가 받는다
  // (누르는 순간 구는 숨어 있어 Cesium 이 그 끌기를 모른다). 위로 끌면 눕고, 옆으로 끌면 돈다
  var flatEl = $("map");
  flatEl.addEventListener("contextmenu", function (e) { e.preventDefault(); });
  flatEl.addEventListener("pointerdown", function (e) {
    if (mode !== "flat" || !(e.button === 2 || (e.button === 0 && e.ctrlKey))) return;
    e.preventDefault();
    e.stopPropagation();
    var v = flat.getView(), ll = wrapLon(toLL(v.getCenter())), h = resToHeight(groundRes());
    var ground = scene.globe.getHeight(Cesium.Cartographic.fromDegrees(ll[0], ll[1])) || 0;
    tilting = true;
    setMode("globe", { h: h });
    var p = { pos: Cesium.Cartesian3.fromDegrees(ll[0], ll[1], ground, ELL), range: h - ground };
    var x0 = e.clientX, y0 = e.clientY, heading = 0, pitch = -90;
    function move(ev) {
      heading = ((ev.clientX - x0) * 0.4 % 360 + 360) % 360;
      pitch = Math.max(-90, Math.min(-8, -90 + (y0 - ev.clientY) * 0.35));
      orbit(p, heading, pitch);
    }
    function up() {
      window.removeEventListener("pointermove", move, true);
      window.removeEventListener("pointerup", up, true);
      tilting = false;
      viewer.camera.moveEnd.raiseEvent();       // 거의 안 기울였으면 다시 평면으로
    }
    window.addEventListener("pointermove", move, true);
    window.addEventListener("pointerup", up, true);
  }, true);

  // ══ 패널 ══════════════════════════════════════════════════════════
  document.querySelectorAll(".tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      document.querySelectorAll(".tab").forEach(function (t) { t.classList.toggle("on", t === tab); });
      document.querySelectorAll(".tabbody").forEach(function (b) {
        b.classList.toggle("on", b.id === "tab-" + tab.dataset.tab);
      });
    });
  });
  (function emblemMenu() {
    var button = $("emblem-btn"), menu = $("hidden-menu");
    function show(open) { menu.hidden = !open; button.setAttribute("aria-expanded", open ? "true" : "false"); }
    button.addEventListener("click", function (e) { e.stopPropagation(); show(menu.hidden); });
    document.addEventListener("click", function (e) { if (!menu.hidden && !menu.contains(e.target)) show(false); });
    document.addEventListener("keydown", function (e) { if (e.key === "Escape" && !menu.hidden) show(false); });
  })();

  // 배경
  var baseSelect = $("basemap");
  baseSelect.value = look.base;
  baseSelect.addEventListener("change", function () {
    look.base = baseSelect.value;
    save("gsm.earth.base", look.base);
    var layers = viewer.imageryLayers;
    layers.remove(cBase, true);
    cBase = cesiumBase(look.base);
    layers.add(cBase, 0);
    oBase.setSource(baseSource(look.base));
    applyTune();
  });

  // ── 영상 보정 (042) ──
  //
  // 배경 영상만 고친다 — 지질도의 색은 약속이라 건드리지 않는다. 구는 Cesium 의 ImageryLayer 속성을,
  // 평면은 WebGL 타일의 셰이더 변수를 쓴다. **둘의 공식이 같다** — 밝기는 곱(OL 의 exposure = 밝기 − 1),
  // 대비는 0.5 를 축으로 늘이기(OL 의 contrast = 대비 − 1), 감마는 색^(1/감마), 채도는 OL 의 saturation = 채도 − 1.
  // 처음에는 평면에 CSS 필터와 SVG 감마(feComponentTransfer)를 걸었는데, 캔버스의 SVG 필터는 CPU 로 그려
  // 헤드리스 크롬에서 화면이 멎었다 — 그래서 셰이더로 옮겼다
  //
  // 화성의 "음영 겹치기" 는 뺐다 — 지구의 배경(Blue Marble)은 이미 음영을 품었다
  var TUNE_DEFAULT = { bright: 100, contrast: 100, gamma: 100, sat: 100, shade: false };
  var PRESETS = {
    crisp: { bright: 105, contrast: 160, gamma: 90, sat: 100, shade: false },
    relief: { bright: 110, contrast: 130, gamma: 110, sat: 100, shade: false },
  };
  var tune = (function () {
    try { return Object.assign({}, TUNE_DEFAULT, JSON.parse(saved("gsm.earth.tune", "{}")) || {}); }
    catch (e) { return Object.assign({}, TUNE_DEFAULT); }
  })();
  var TUNES = ["bright", "contrast", "gamma", "sat"];
  function tuneText(key, v) { return key === "gamma" ? (v / 100).toFixed(2) : v + "%"; }
  function applyTune() {
    cBase.brightness = tune.bright / 100;
    cBase.contrast = tune.contrast / 100;
    cBase.gamma = tune.gamma / 100;
    cBase.saturation = tune.sat / 100;
    [oBase].forEach(function (layer) {
      layer.updateStyleVariables({ exposure: tune.bright / 100 - 1, contrast: tune.contrast / 100 - 1,
                                   gamma: tune.gamma / 100, saturation: tune.sat / 100 - 1 });
    });
    TUNES.forEach(function (k) {
      $("tune-" + k).value = tune[k];
      $("tune-" + k + "-num").textContent = tuneText(k, tune[k]);
    });
    var changed = TUNES.some(function (k) { return tune[k] !== TUNE_DEFAULT[k]; });
    $("tune-state").textContent = changed ? T("고침") : "";
    save("gsm.earth.tune", JSON.stringify(tune));
  }
  TUNES.forEach(function (k) {
    $("tune-" + k).addEventListener("input", function () { tune[k] = +this.value; applyTune(); });
  });
  $("tune-reset").addEventListener("click", function () { tune = Object.assign({}, TUNE_DEFAULT); applyTune(); });
  document.querySelectorAll("#tune [data-preset]").forEach(function (b) {
    b.addEventListener("click", function () { tune = Object.assign({}, PRESETS[b.dataset.preset]); applyTune(); });
  });
  applyTune();

  // ── 지질 레이어 — 2D 처럼 목록에서 켜고, 켠 것은 카드로 쌓는다 ──
  //
  // 쌓는 차례는 구와 평면이 같다. 구는 배경(0 번) 위로 아래 것부터 `raiseToTop`, 평면은 `zIndex`
  function applyStack() {
    Object.keys(cGeo).forEach(function (name) {
      var e = entryOf(name);
      // 오늘의 것은 오늘에만, 그때의 것(`then`)은 1 Ma 부터만 뜬다 (P07 §2)
      var shown = !!e && (LAYER[name].then ? paleoOn() : !paleoOn());
      cGeo[name].show = shown;
      oGeo[name].setVisible(shown);
      if (e) { cGeo[name].alpha = e.opacity; oGeo[name].setOpacity(e.opacity); }
    });
    // 구 — 영상 레이어만 차례가 있다(벡터 데이터 소스는 늘 영상 위다). 평면 — zIndex
    active.slice().reverse().forEach(function (e, i) {
      (cRaise[e.name] || []).forEach(function (l) { viewer.imageryLayers.raiseToTop(l); });
      // 평면도 구처럼 벡터(착륙 지점·동선)는 영상 레이어 위에 둔다 — 사진을 나중에 켜도 점을 덮지 않게
      oGeo[e.name].setZIndex((LAYER[e.name].kind === "vector" ? 50 : 0) + i + 1);
    });
    // 점묶음은 늘 지질 위다
    oPoints.setZIndex(100);
    syncLegend();
  }
  function addLayer(name) {
    if (isOn(name)) return;
    active.unshift({ name: name, opacity: name === "geology" ? 0.6 : 1 });
    saveLayers(); applyStack(); renderActive(); renderCatalog();
  }
  function removeLayer(name) {
    active = active.filter(function (e) { return e.name !== name; });
    saveLayers(); applyStack(); renderActive(); renderCatalog();
  }
  function moveLayer(name, step) {
    var i = active.indexOf(entryOf(name)), j = i + step;
    if (i < 0 || j < 0 || j >= active.length) return;
    var e = active.splice(i, 1)[0];
    active.splice(j, 0, e);
    saveLayers(); applyStack(); renderActive();
  }
  function renderActive() {
    var host = $("active-list");
    $("count-layers").textContent = active.length;
    host.innerHTML = "";
    if (!active.length) {
      host.innerHTML = '<li class="empty">' + esc(T("아직 켠 레이어가 없다")) + "</li>";
      return;
    }
    active.forEach(function (e, index) {
      var li = document.createElement("li");
      var head = document.createElement("div");
      head.className = "active-head";
      var title = document.createElement("span");
      title.className = "active-title";
      title.textContent = T(LAYER[e.name].title);
      head.append(
        iconButton("↑", T("위로"), index === 0, function () { moveLayer(e.name, -1); }),
        iconButton("↓", T("아래로"), index === active.length - 1, function () { moveLayer(e.name, 1); }),
        title,
        iconButton("×", T("끈다"), false, function () { removeLayer(e.name); }));
      var foot = document.createElement("div");
      foot.className = "active-foot";
      var range = document.createElement("input");
      range.type = "range";
      range.min = 0; range.max = 100; range.value = Math.round(e.opacity * 100);
      range.setAttribute("aria-label", T("투명도"));
      var num = document.createElement("span");
      num.className = "opacity-num";
      num.textContent = range.value + "%";
      range.addEventListener("input", function () {
        e.opacity = range.value / 100;
        cGeo[e.name].alpha = e.opacity;
        oGeo[e.name].setOpacity(e.opacity);
        num.textContent = range.value + "%";
      });
      range.addEventListener("change", saveLayers);
      foot.append(range, num);
      var src = document.createElement("p");
      src.className = "active-src";
      src.textContent = LAYER[e.name].src || "";
      li.append(head, foot, src);
      host.appendChild(li);
    });
  }
  function renderCatalog() {
    var host = $("layer-catalog");
    host.innerHTML = "";
    CATALOG.forEach(function (g) {
      var details = document.createElement("details");
      details.className = "group";
      details.open = true;
      var summary = document.createElement("summary");
      summary.innerHTML = esc(T(g.group)) + ' <span class="count">' + g.layers.length + "</span>";
      details.appendChild(summary);
      g.layers.forEach(function (l) { details.appendChild(layerRow(l)); });
      host.appendChild(details);
    });
  }
  function layerRow(l) {
    var row = document.createElement("div");
    row.className = "layer-row";
    var box = document.createElement("input");
    box.type = "checkbox";
    box.id = "lyr-" + l.name;
    box.checked = isOn(l.name);
    box.addEventListener("change", function () { if (box.checked) addLayer(l.name); else removeLayer(l.name); });
    var label = document.createElement("label");
    label.htmlFor = box.id;
    label.textContent = T(l.title);
    row.append(box, label);
    return row;
  }

  // 지형 (구에서만)
  var terrainBox = $("moon-terrain"), exag = $("moon-exag");
  terrainBox.checked = look.terrain;
  exag.disabled = !look.terrain;
  terrainBox.addEventListener("change", function () {
    look.terrain = terrainBox.checked;
    scene.terrainProvider = look.terrain && !paleoOn() ? demTerrain : flatTerrain;
    exag.disabled = !look.terrain;
    save("gsm.earth.terrain", look.terrain ? "on" : "off");
  });
  exag.value = look.exag;
  function applyExag() {
    look.exag = +exag.value;
    scene.verticalExaggeration = look.exag / 10;
    $("moon-exag-num").textContent = "×" + (look.exag / 10).toFixed(1);
    save("gsm.earth.exag", look.exag);
  }
  exag.addEventListener("input", applyExag);
  applyExag();

  // ══ 좌표 ══════════════════════════════════════════════════════════
  function fmt(ll) {
    return T("위도 {lat}° · 경도 {lon}°", { lat: ll[1].toFixed(4), lon: ll[0].toFixed(4) });
  }
  function globeLL(position) {
    var ray = viewer.camera.getPickRay(position);
    var cartesian = ray && scene.globe.pick(ray, scene);
    if (!cartesian) cartesian = viewer.camera.pickEllipsoid(position, ELL);
    if (!cartesian) return null;
    var c = ELL.cartesianToCartographic(cartesian);
    return [Cesium.Math.toDegrees(c.longitude), Cesium.Math.toDegrees(c.latitude)];
  }
  function wrapLon(ll) {
    var lon = ((ll[0] + 180) % 360 + 360) % 360 - 180;
    return [lon, ll[1]];
  }
  var readout = $("readout");
  var handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
  handler.setInputAction(function (movement) {
    var ll = globeLL(movement.endPosition);
    readout.textContent = ll ? fmt(ll) : "";
  }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
  flat.on("pointermove", function (e) {
    if (e.dragging) return;
    readout.textContent = fmt(wrapLon(toLL(e.coordinate)));
  });

  // ══ 팝업 — 누른 자리에 뜬다 ═══════════════════════════════════════
  var popup = $("popup"), popupBody = $("popup-body");
  var asked = 0;
  function closePopup() { popup.classList.remove("on"); ++asked; markAt(null); }
  $("popup-close").addEventListener("click", closePopup);
  function showPopup(html, pixel) {
    popupBody.innerHTML = html;
    popup.classList.add("on");
    var w = wrap.clientWidth, h = wrap.clientHeight;
    var pw = popup.offsetWidth, ph = popup.offsetHeight;
    var left = Math.min(Math.max(8, pixel[0] + 14), w - pw - 8);
    var top = Math.min(Math.max(8, pixel[1] - ph / 2), h - ph - 64);
    // 오른쪽 위 손잡이(도구·자세 두 묶음)를 덮지 않게 그 왼쪽으로 비킨다 — 팝업이 위라 덮으면 못 누른다 (041)
    var bar = $("toolbar");
    if (top < bar.offsetTop + bar.offsetHeight + 8 && left + pw > bar.offsetLeft - 8) {
      left = Math.max(8, Math.min(pixel[0] - pw - 14, bar.offsetLeft - pw - 8));
    }
    popup.style.left = left + "px";
    popup.style.top = Math.max(8, top) + "px";
  }
  // 첫 줄은 누른 자리의 위경도 — 2D 처럼 누르면 "위도, 경도" 로 복사한다(아래 `popupBody` 의 click, 041)
  function coordHead(ll) {
    var lat = ll[1].toFixed(6), lon = ll[0].toFixed(6);
    return '<button type="button" class="popup-coord" title="' + esc(T("눌러서 복사한다")) + '" data-copy="' +
           lat + ", " + lon + '"><span class="k">' + esc(T("위도")) + '</span><span class="v">' + lat +
           '</span><span class="k">' + esc(T("경도")) + '</span><span class="v">' + lon +
           '</span><span class="copy">' + esc(T("복사")) + "</span></button>";
  }
  // 그때의 자리 (wetherilli 087) — 누른 자리를 아무 연대로나 옮겨 본다. 서버가 PALEOMAP 2016 판 회전으로 셈한다
  // (`paleo.py`). 점묶음의 점에 연대(Ma) 열이 있으면 그 값을 미리 넣는다
  function paleoForm(ll, age) {
    return '<form class="paleo-form" data-lon="' + ll[0].toFixed(5) + '" data-lat="' + ll[1].toFixed(5) + '">' +
           '<label title="' + esc(T("PALEOMAP 2016 판 회전으로 셈한 것이다 — 관측이 아니다")) + '">' + esc(T("그때의 자리")) +
           ' <input type="number" name="age" min="0" max="1100" step="any" placeholder="250" value="' +
           (age == null ? "" : esc(age)) + '"> Ma</label><button type="submit">' + esc(T("옮긴다")) + "</button>" +
           '<output class="paleo-out"></output></form>';
  }
  popupBody.addEventListener("submit", function (e) {
    var form = e.target.closest(".paleo-form");
    if (!form) return;
    e.preventDefault();
    var out = form.querySelector(".paleo-out"), age = form.elements.age.value;
    if (age === "") return;
    out.textContent = T("읽는 중");
    fetch(BASE + "earth/paleo/?lon=" + form.dataset.lon + "&lat=" + form.dataset.lat + "&age=" + encodeURIComponent(age))
      .then(function (r) { return r.json(); })
      .then(function (d) {
        out.textContent = d.error || d.text;
        if (d.lon != null) out.insertAdjacentHTML("beforeend", " " + ettLink([+form.dataset.lon, +form.dataset.lat], d.age));
      })
      .catch(function () { out.textContent = T("속성을 받지 못했다"); });
  });
  // 켠 레이어 가운데 읽을 수 있는 것을 위에서부터 다 묻는다 — 달·화성에서 온 틀이다. 지구는 지질도 하나다.
  // Macrostrat 는 줌마다 그리는 판(축척)이 달라, 보는 줌을 함께 보낸다 — 타일과 같은 판을 읽는다
  function hereZoom() {
    var res = mode === "flat" ? groundRes() : heightToRes(hereHeight());
    return Math.max(0, Math.min(GEO_MAX, Math.round(Math.log(40075016.7 / 256 / Math.max(0.5, res)) / Math.LN2)));
  }
  // ══ EarthThruTime3D 로 건너가기 (wetherilli 088) ════════════════
  //
  // 옛 위치를 ETT 의 고지리 지구본에서 본다. 주소는 ETT 의 것 그대로다(`docs/site-map.md`) — 핀은 **오늘의 좌표**를
  // 넘기고 옮기기는 ETT 가 한다. 둘 다 PALEOMAP 2016 이라 우리가 적은 자리에 핀이 선다(087). 고도 격자(PaleoDEM)는
  // 540 Ma 까지라 그보다 오랜 연대는 기본 판(PaleoAtlas 육지 마스크, 750 Ma 까지 — 그 너머는 판 재구성만)으로 연다.
  // ETT 는 연대를 가장 가까운 시점에 맞춘다. 링크일 뿐이라 자료는 넘어가지 않는다
  var ETT_URL = "https://earththrutime.nopeoplestime.info/";
  var ETT_DEM_MAX = 540;
  function ettHref(ll, age) {
    var w = wrapLon(ll), q = [];
    if (age <= ETT_DEM_MAX) q.push("masks=paleodem2018");
    q.push("age=" + (+age).toFixed(age < 10 ? 3 : 1).replace(/\.?0+$/, ""));
    q.push("pin=" + w[0].toFixed(2) + "," + w[1].toFixed(2));
    return ETT_URL + "?" + q.join("&");
  }
  function ettLink(ll, age) {
    return '<a class="ett-link" target="_blank" rel="noopener" href="' + esc(ettHref(ll, age)) + '" title="' +
           esc(T("EarthThruTime3D 의 고지리 지구본에서 이 자리를 그 연대로 본다 — 새 창")) + '">' +
           esc(T("ETT 에서 {age} Ma", { age: age })) + "</a>";
  }
  function unitTable(u, ll) {
    var chip = u.color ? '<span class="swatch-img" style="display:inline-block;background:' + esc(u.color) + '"></span>' : "";
    var rows = u.rows.map(function (row, k) {
      return "<tr><th>" + esc(row[0]) + "</th><td>" + (k === 0 ? chip : "") + esc(row[1]) + "</td></tr>";
    });
    if (u.then && u.then.length) {
      rows.push('<tr><th>EarthThruTime3D</th><td>' + u.then.map(function (age) { return ettLink(ll, age); }).join(" · ") +
                "</td></tr>");
    }
    return "<table>" + rows.join("") + "</table>";
  }
  function askUnit(ll, pixel) {
    markAt(ll);
    var head = coordHead(ll) + paleoForm(ll);
    var layers = active.filter(function (e) { return LAYER[e.name].info; }).map(function (e) { return LAYER[e.name]; });
    if (!layers.length) { showPopup(head, pixel); return; }
    var mine = ++asked;
    showPopup(head + '<p class="none">' + esc(T("읽는 중")) + "</p>", pixel);
    var at = "?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) + "&z=" + hereZoom();
    Promise.all(layers.map(function () {
      return fetch(BASE + "earth/info/" + at).then(function (r) { return r.json(); }).catch(function () { return { error: true }; });
    })).then(function (all) {
      if (mine !== asked) return;
      var html = head;
      all.forEach(function (data, i) {
        html += "<h3>" + esc(T(layers[i].title)) + "</h3>";
        if (data.error) { html += '<p class="none">' + esc(T("속성을 받지 못했다")) + "</p>"; return; }
        if (!data.units || !data.units.length) {
          html += '<p class="none">' + esc(T("여기에는 지질 단위가 없다")) + "</p>";
          return;
        }
        // 한 자리에 단위가 여럿일 수 있다(판이 겹친 곳) — 다 싣는다
        html += data.units.map(function (u) { return unitTable(u, ll); }).join("");
      });
      showPopup(html, pixel);
    });
  }
  // 점묶음의 점·모양 — 2D 의 팝업과 같이 딸린 속성을 받은 차례 그대로
  function showFeature(props, ps, ll, pixel) {
    ++asked;
    markAt(ll);
    var title = props["이름표"] || ps.name || "";
    var rows = Object.keys(props).filter(function (k) {
      return k !== "이름표" && k.charAt(0) !== "_" && props[k] !== "" && props[k] != null && typeof props[k] !== "object";
    });
    // 그때의 지구에서 옮겨 그린 점 — 팝업의 위경도·옛 위치는 오늘의 좌표로 (091)
    if (Array.isArray(props._today)) ll = props._today;
    // 연대(Ma) 열 — "연대 (Ma)"·"age_ma" 따위. 숫자면 옛 위치 칸에 미리 넣는다
    var ageKey = rows.filter(function (k) { return /Ma\)?$|_ma$|^age$/i.test(k) && isFinite(parseFloat(props[k])); })[0];
    showPopup((ll ? coordHead(ll) + paleoForm(ll, ageKey ? parseFloat(props[ageKey]) : null) : "") +
              (props._paleo ? '<p class="none">' + esc(props._paleo) + "</p>" : "") +
              "<h3>" + esc(title) + '</h3><p class="from"><span class="swatch" style="background:' +
              esc(ps.color) + '"></span>' + esc(ps.name) + "</p>" +
              (rows.length ? "<table>" + rows.map(function (k) {
                return "<tr><th>" + esc(T(k)) + "</th><td>" + esc(props[k]) + "</td></tr>";
              }).join("") + "</table>" : ""), pixel);
  }
  handler.setInputAction(function (click) {
    if (tool) { drawClick(globeLL(click.position)); return; }     // 도구가 켜져 있으면 도구가 받는다 (041)
    var picked = scene.pick(click.position);
    var entity = picked && picked.id;
    var px = [click.position.x, click.position.y];
    if (entity && entity.gsmProps) {
      var pos = entity.position && entity.position.getValue(Cesium.JulianDate.now());
      var ll = null;
      if (pos) { var c = ELL.cartesianToCartographic(pos); ll = [Cesium.Math.toDegrees(c.longitude), Cesium.Math.toDegrees(c.latitude)]; }
      showFeature(entity.gsmProps, entity.gsmSet, ll, px);
      return;
    }
    var at = globeLL(click.position);
    if (at) (paleoOn() ? askPaleo : askUnit)(at, px);
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);
  flat.on("singleclick", function (e) {
    // 도구가 켜져 있으면 도구가 받는다. 선·면·범위는 평면의 Draw·DragBox 가 따로 받는다 (041)
    if (tool) { if (tool === "point") addTemp(toLL(e.coordinate)); return; }
    var hit = flat.forEachFeatureAtPixel(e.pixel, function (f, layer) { return [f, layer]; }, { hitTolerance: 4 });
    if (hit && hit[1] && hit[1].get("gsmSet")) {
      var g = hit[0].getGeometry();
      var ll = g && g.getType() === "Point" ? wrapLon(toLL(g.getCoordinates())) : null;
      var props = Object.assign({}, hit[0].getProperties());
      delete props.geometry;
      showFeature(props, hit[1].get("gsmSet"), ll, e.pixel);
      return;
    }
    (paleoOn() ? askPaleo : askUnit)(wrapLon(toLL(e.coordinate)), e.pixel);
  });

  // ══ 범례 — 오른쪽 아래, 펼쳐 둔다 ═══════════════════════════════
  //
  // 켠 레이어마다 칸 하나. Macrostrat 의 색은 단위의 시대(ICS)의 색이라 기(period)의 색으로 읽힌다 — 세·절까지
  // 가른 단위는 색이 조금 다르다. 젊은 것이 위다
  var legends = {};                // 갈래 → 그린 HTML (한 번 받는다)
  var dock = $("legend-dock");
  dock.open = saved("gsm.earth.legend", "open") !== "closed";
  dock.addEventListener("toggle", function () { save("gsm.earth.legend", dock.open ? "open" : "closed"); });
  function ma(v) { return v == null ? "" : (+v).toLocaleString(undefined, { maximumFractionDigits: 2 }); }
  function legendHtml(kind) {
    if (legends[kind] !== undefined) return Promise.resolve(legends[kind]);
    return fetch(BASE + "earth/legend/").then(function (r) { return r.json(); }).then(function (data) {
      var html = '<li class="empty">' + esc(T("색은 시대의 색이다 — 세·절까지 가른 단위는 조금 다르다")) + "</li>";
      html += (data.rows || []).map(function (row) {
        return '<li><span class="chip" style="background:' + esc(row.color) + '"></span>' + esc(row.name) +
               ' <span class="hint">' + esc(ma(row.b_age)) + "–" + esc(ma(row.t_age)) + " Ma</span></li>";
      }).join("");
      legends[kind] = html;
      return html;
    }).catch(function () { return '<li class="empty">' + esc(T("범례를 받지 못했다")) + "</li>"; });
  }
  var legendAsked = 0;
  function syncLegend() {
    var layers = active.filter(function (e) { return LAYER[e.name].legend && !paleoOn(); })
                       .map(function (e) { return LAYER[e.name]; });
    dock.hidden = !layers.length;
    if (!layers.length) return;
    var mine = ++legendAsked;
    Promise.all(layers.map(function (l) { return legendHtml(l.legend); })).then(function (parts) {
      if (mine !== legendAsked) return;
      $("legend-list").innerHTML = parts.map(function (html, i) {
        var head = parts.length > 1 ? '<li class="layer">' + esc(T(layers[i].title)) + "</li>" : "";
        return head + html;
      }).join("");
      $("legend-sub").textContent = layers.length === 1 ? T(layers[0].title) : "";
    });
  }

  // ══ 내 자료 — 지구 점묶음 (달의 037·화성의 058 을 옮겼다) ═══════════
  //
  // 지역 탭의 점묶음(`body: "earth"`) 그대로다 — 같은 것을 온 지구에서 본다. 구에는 Cesium 의 점·선·면으로,
  // 평면에는 OpenLayers 의 벡터 레이어로 같은 GeoJSON 을 그린다
  var pointsets = JSON.parse(($("pointset-data") || {}).textContent || "[]");
  var cSets = {}, oSets = {}, extents = {};
  var PS_OFF = "gsm.earth.pointsets.off";
  function offList() {
    try { return JSON.parse(saved(PS_OFF, "[]")) || []; } catch (e) { return []; }
  }
  function setOff(id, off) {
    var list = offList().filter(function (x) { return x !== id; });
    if (off) list.push(id);
    save(PS_OFF, JSON.stringify(list));
  }
  function csrf() {
    var input = document.querySelector("#upload-form [name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }
  function post(url, body) {
    return fetch(url, { method: "POST", headers: { "X-CSRFToken": csrf() }, body: body || new FormData() })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (d) {
          if (!r.ok) throw new Error(d.error || String(r.status));
          return d;
        });
      });
  }
  function countText(ps) {
    var bits = [T("{n}점", { n: ps.count || 0 })];
    if (ps.lines) bits.push(T("선 {n}", { n: ps.lines }));
    if (ps.polygons) bits.push(T("면 {n}", { n: ps.polygons }));
    if (!ps.count && (ps.lines || ps.polygons)) bits.shift();
    if (ps.elevated) bits.push(T("고도 {n}", { n: ps.elevated }));
    return bits.join(" · ");
  }

  // 구 — 점·이름표를 지형에 묻히지 않게 깊이 검사를 끄되, **가까울 때만**이다. 끝없이 끄면 뒷면의
  // 점이 지구를 뚫고 앞면에 비친다(달의 창어 4 호가 그랬다). 3 000 km 는 지구 반지름보다 짧다
  var NO_DEPTH = 3000000;
  function ringPositions(ring) {
    var flatArr = [];
    ring.forEach(function (c) { flatArr.push(c[0], c[1]); });
    return Cesium.Cartesian3.fromDegreesArray(flatArr, ELL);
  }
  function addEntity(source, ps, feature) {
    var g = feature.geometry || {}, props = feature.properties || {};
    var color = Cesium.Color.fromCssColorString(ps.color || "#e4572e");
    var label = props["이름표"] || "";
    function add(opts) {
      var e = source.entities.add(opts);
      e.gsmProps = props;
      e.gsmSet = ps;
      return e;
    }
    if (g.type === "Point") {
      add({
        position: Cesium.Cartesian3.fromDegrees(g.coordinates[0], g.coordinates[1], 0, ELL),
        point: { pixelSize: 8, color: color, outlineColor: Cesium.Color.BLACK, outlineWidth: 1.5,
                 heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: NO_DEPTH },
        // 이름표는 가까이 가야 뜬다 — 멀리서는 수천 개가 겹친다
        label: label ? { text: label, font: "12px system-ui, sans-serif", fillColor: Cesium.Color.WHITE,
                         outlineColor: Cesium.Color.BLACK, outlineWidth: 3,
                         style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(0, -14),
                         heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                         distanceDisplayCondition: new Cesium.DistanceDisplayCondition(0, 400000),
                         disableDepthTestDistance: NO_DEPTH } : undefined,
      });
    } else if (g.type === "LineString" || g.type === "MultiLineString") {
      (g.type === "LineString" ? [g.coordinates] : g.coordinates).forEach(function (line) {
        add({ polyline: { positions: ringPositions(line), width: 2.5, clampToGround: true, material: color } });
      });
    } else if (g.type === "Polygon" || g.type === "MultiPolygon") {
      (g.type === "Polygon" ? [g.coordinates] : g.coordinates).forEach(function (rings) {
        add({ polygon: { hierarchy: new Cesium.PolygonHierarchy(ringPositions(rings[0]),
                           rings.slice(1).map(function (r) { return new Cesium.PolygonHierarchy(ringPositions(r)); })),
                         material: color.withAlpha(0.25) } });
        add({ polyline: { positions: ringPositions(rings[0]), width: 2, clampToGround: true, material: color } });
      });
    }
  }
  // 평면 — 2D 의 점 모양과 같은 꼴
  function flatStyle(ps) {
    var fill = new ol.style.Fill({ color: ps.color }), edge = new ol.style.Stroke({ color: "#000", width: 1.5 });
    var point = new ol.style.Circle({ radius: 5, fill: fill, stroke: edge });
    var line = new ol.style.Stroke({ color: ps.color, width: 2.5 });
    var area = new ol.style.Fill({ color: ps.color + "40" });
    return function (feature, resolution) {
      var label = feature.get("이름표");
      var text = label && resolution < 400 ? new ol.style.Text({
        text: String(label), offsetY: -14, font: "12px system-ui, sans-serif",
        fill: new ol.style.Fill({ color: "#fff" }), stroke: new ol.style.Stroke({ color: "#000", width: 3 }) }) : undefined;
      var type = feature.getGeometry().getType();
      if (/Point/.test(type)) return new ol.style.Style({ image: point, text: text });
      if (/Line/.test(type)) return new ol.style.Style({ stroke: line, text: text });
      return new ol.style.Style({ stroke: line, fill: area, text: text });
    };
  }
  function extentOf(features) {
    var w = 180, s = 90, e = -180, n = -90;
    function walk(c) {
      if (typeof c[0] === "number") {
        w = Math.min(w, c[0]); e = Math.max(e, c[0]); s = Math.min(s, c[1]); n = Math.max(n, c[1]);
      } else c.forEach(walk);
    }
    features.forEach(function (f) { if (f.geometry) walk(f.geometry.coordinates); });
    return w <= e ? [w, s, e, n] : null;
  }
  var loading = {};
  var setGen = 0;              // 연대가 바뀌어 다시 받으면 늦게 온 옛 답을 버린다
  function loadSet(ps) {
    if (loading[ps.id]) return loading[ps.id];
    var gen = setGen;
    // 그때의 지구에서는 서버가 점을 그 연대의 자리로 옮겨 준다(`pointsets/<id>/paleo/`). 선·면은 오지 않는다 (091)
    var url = paleoOn() ? BASE + "pointsets/" + ps.id + "/paleo/?age=" + age : BASE + "pointsets/" + ps.id + "/geojson/";
    loading[ps.id] = fetch(url).then(function (r) { return r.json(); }).then(function (data) {
      if (gen !== setGen) return;
      var feats = data.features || [];
      extents[ps.id] = extentOf(feats);
      var source = new Cesium.CustomDataSource("ps-" + ps.id);
      feats.forEach(function (f) { addEntity(source, ps, f); });
      source.show = ps.visible;
      viewer.dataSources.add(source);
      cSets[ps.id] = source;
      var layer = new ol.layer.Vector({
        source: new ol.source.Vector({ features: new ol.format.GeoJSON().readFeatures(data,
                                         { dataProjection: LL, featureProjection: proj }) }),
        style: flatStyle(ps), declutter: true, visible: ps.visible,
      });
      layer.set("gsmSet", ps);
      oPoints.getLayers().push(layer);
      oSets[ps.id] = layer;
    });
    return loading[ps.id];
  }
  function dropSet(id) {
    if (cSets[id]) viewer.dataSources.remove(cSets[id], true);
    if (oSets[id]) oPoints.getLayers().remove(oSets[id]);
    delete cSets[id]; delete oSets[id]; delete loading[id]; delete extents[id];
  }
  function showSet(ps) {
    if (cSets[ps.id]) cSets[ps.id].show = ps.visible;
    if (oSets[ps.id]) oSets[ps.id].setVisible(ps.visible);
  }
  function goTo(lon, lat, h) {
    closePopup();
    if (mode === "flat" && h < TO_GLOBE_H) {
      useProj(projFor(lat, proj), [lon, lat], heightToRes(h));
      flat.getView().animate({ center: fromLL([lon, lat]), resolution: heightToRes(h) / groundScale(proj, lat),
                               duration: 600 });
    } else {
      if (mode === "flat") setMode("globe");
      flyGlobe(lon, lat, h, 1.5);
    }
  }
  function flyToSet(ps) {
    loadSet(ps).then(function () {
      var x = extents[ps.id];
      if (!x) return;
      var span = Math.max(x[2] - x[0], x[3] - x[1]);
      var h = Math.max(30000, span * M_PER_DEG * 1.4);
      goTo((x[0] + x[2]) / 2, (x[1] + x[3]) / 2, h);
    });
  }
  function iconButton(text, title, disabled, onClick) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "iconbtn";
    b.textContent = text;
    b.title = title;
    b.setAttribute("aria-label", title);
    b.disabled = !!disabled;
    b.addEventListener("click", onClick);
    return b;
  }
  function renderSets() {
    var host = $("pointset-list");
    $("count-points").textContent = pointsets.length;
    host.innerHTML = "";
    if (!pointsets.length) {
      host.innerHTML = '<li class="empty">' + T("왼쪽 위 <b>불러오기</b> 탭에서 올린다") + "</li>";
      return;
    }
    var off = offList();
    pointsets.forEach(function (ps) {
      ps.visible = off.indexOf(ps.id) < 0;
      loadSet(ps);
      showSet(ps);
      var li = document.createElement("li");
      var box = document.createElement("input");
      box.type = "checkbox";
      box.checked = ps.visible;
      box.setAttribute("aria-label", ps.name);
      box.addEventListener("change", function () {
        ps.visible = box.checked;
        setOff(ps.id, !ps.visible);
        showSet(ps);
      });
      var swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = ps.color;
      var text = document.createElement("span");
      text.className = "ps-text";
      text.innerHTML = '<span class="ps-name">' + esc(ps.name) + '</span><span class="ps-count">' +
                       esc(countText(ps)) + "</span>";
      var zoom = iconButton("⊙", T("이 자료로 범위를 맞춘다"), false, function () { flyToSet(ps); });
      var elev = iconButton("⛰", T("표고 채우기 — 표고 타일에서 점마다 고도를 읽는다 (극지 PGC · 일본 국토지리원 · 그 밖 SRTM)"),
                            !ps.count, function () {
        elev.disabled = true;
        post(BASE + "pointsets/" + ps.id + "/elevation/").then(function (d) {
          if (d.pointset) Object.assign(ps, d.pointset);
          alert(T("{n}점 채움 · {m}점은 자료 밖", { n: d.filled, m: d.missed }));
          dropSet(ps.id);
          renderSets();
        }).catch(function (e) {
          elev.disabled = false;
          alert((e && e.message) || T("표고를 받지 못했다"));
        });
      });
      var down = iconButton("⤓", T("GeoJSON 으로 내려받는다"), false, function () {
        location.href = BASE + "pointsets/" + ps.id + "/geojson/?download=1";
      });
      var del = iconButton("×", T("지운다"), false, function () {
        if (!confirm(T("'{name}' 을 지운다.", { name: ps.name }))) return;
        post(BASE + "pointsets/" + ps.id + "/delete/").then(function () {
          dropSet(ps.id);
          pointsets = pointsets.filter(function (x) { return x.id !== ps.id; });
          renderSets();
        }).catch(function (e) { alert((e && e.message) || ""); });
      });
      li.append(box, swatch, text, zoom, elev, down, del);
      host.appendChild(li);
    });
  }

  // ══ 시간 축 (wetherilli P07·091) ═══════════════════════════════════
  //
  // 연대 하나(`age`, Ma)를 로그 막대로 고른다 — 1 ka 에서 1 100 Ma 까지 여섯 자릿수가 한 막대에 선다. ETT 처럼
  // "전체 시대 / 최근 빙기" 창을 가르지 않았다 — 빙상 밑의 대륙을 묻는 물음이 두 화면으로 쪼개진다(P07 §2).
  //
  // **1 Ma 가 두 뜻을 가른다.** 그 안쪽은 오늘의 지구에 그 연대의 것을 얹는다(판이 움직인 것이 수십 km 안이다).
  // 1 Ma 부터는 서버가 판을 돌려 칠한 **그때의 지구**를 바다색 구 위에 그리고, 오늘의 것(영상·지형·지질도)은
  // 뜨지 않는다 — 오늘 드러난 암석이 그때 거기 드러나 있었다는 뜻으로 읽히지 않게. 판을 돌리는 셈은 서버의
  // `paleo.py` 하나다 — 브라우저에 한 벌 더 두지 않는다
  var AGE_LOG0 = Math.log(0.001) / Math.LN10, AGE_LOG1 = Math.log(AGE_MAX) / Math.LN10;
  var SLIDER = 1000;
  function toSlider(a) {
    if (!(a > 0)) return 0;
    return Math.max(1, Math.min(SLIDER, Math.round(1 + (SLIDER - 1) * (Math.log(a) / Math.LN10 - AGE_LOG0) / (AGE_LOG1 - AGE_LOG0))));
  }
  function fromSlider(v) {
    return v <= 0 ? 0 : snapAge(Math.pow(10, AGE_LOG0 + (v - 1) / (SLIDER - 1) * (AGE_LOG1 - AGE_LOG0)));
  }
  function ageText(a) {
    if (!(a > 0)) return T("오늘");
    if (a < PALEO_FROM) return Math.round(a * 1000).toLocaleString() + " ka";
    return a.toLocaleString() + " Ma";
  }
  /** "250"·"250 Ma"·"20 ka"·"1.2 Ga"·"오늘" → Ma. 못 읽으면 null */
  function parseAge(text) {
    var t = String(text).trim().toLowerCase();
    if (t === "" || t === "0" || t === T("오늘").toLowerCase() || t === "today") return 0;
    var m = /^(\d+(?:[.,]\d+)?)\s*(ka|ma|ga|kyr|myr|gyr)?$/.exec(t.replace(/\s+/g, " "));
    if (!m) return null;
    var v = parseFloat(m[1].replace(",", ".")), unit = (m[2] || "ma").charAt(0);
    return snapAge(unit === "k" ? v / 1000 : unit === "g" ? v * 1000 : v);
  }
  // 자료가 있는 구간 — 막대 위의 띠. 단계마다 한 줄씩 는다 (P07 §4)
  var AGE_BANDS = [
    { title: "판 조각 (PALEOMAP 2016)", from: PALEO_FROM, to: AGE_MAX },
  ];
  var COAST_AGES = (THEN.coast || []).filter(function (a) { return a >= PALEO_FROM; });
  if (COAST_AGES.length) AGE_BANDS.push({ title: "옛 해안선", from: COAST_AGES[0], to: COAST_AGES[COAST_AGES.length - 1] + 10 });
  /** 옛 해안선의 시점 — 가장 가까운 것, 10 Myr 안에서만 (서버의 `paleocoast.stop` 과 같다) */
  function coastStop(a) {
    var best = null;
    (THEN.coast || []).forEach(function (c) { if (best == null || Math.abs(c - a) < Math.abs(best - a)) best = c; });
    return best != null && Math.abs(best - a) <= 10 ? best : null;
  }
  var AGE_TICKS = [[0.001, "1 ka"], [0.01, "10 ka"], [0.1, "100 ka"], [1, "1 Ma"], [10, "10 Ma"], [100, "100 Ma"], [1000, "1 Ga"]];
  var ageRange = $("age-range"), ageInput = $("age-input");
  function pct(a) { return (toSlider(a) / SLIDER * 100).toFixed(2) + "%"; }
  $("age-ticks").innerHTML = AGE_TICKS.map(function (t) {
    return '<span style="left:' + pct(t[0]) + '">' + t[1] + "</span>";
  }).join("");
  $("age-bands").innerHTML = AGE_BANDS.map(function (b) {
    var left = toSlider(b.from) / SLIDER * 100, right = toSlider(b.to) / SLIDER * 100;
    return '<div class="tb-band" title="' + esc(T(b.title)) + " · " + esc(ageText(b.from)) + "–" + esc(ageText(b.to)) +
           '"><span style="left:' + left.toFixed(2) + "%;width:" + (right - left).toFixed(2) + '%"></span></div>';
  }).join("");
  $("age-bands").style.height = AGE_BANDS.length * 6 + "px";

  // 시대 이름 — 지질도 범례와 같은 ICS 기(period)의 목록을 한 번 받는다
  var periods = null;
  fetch(BASE + "earth/legend/").then(function (r) { return r.json(); })
    .then(function (d) { periods = d.rows || []; showAge(); }).catch(function () { periods = []; });
  function periodOf(a) {
    var hit = (periods || []).filter(function (r) { return r.t_age <= a && a < r.b_age; })[0];
    return hit ? hit.name : "";
  }

  // 그때의 지구 — 칠한 판 조각. 연대마다 타일 주소가 달라 레이어를 갈아 끼운다
  var cPaleo = null, paleoShown = null;
  var oPaleo = new ol.layer.Tile({ visible: false });
  flat.getLayers().insertAt(1, oPaleo);            // 배경 바로 위 — 점묶음·찍은 것은 그 위다
  var OCEAN = "#1b3a5e";
  function showPaleo(a) {
    if (a === paleoShown) return;
    paleoShown = a;
    if (cPaleo) { viewer.imageryLayers.remove(cPaleo, true); cPaleo = null; }
    if (a == null) { oPaleo.setVisible(false); return; }
    cPaleo = viewer.imageryLayers.addImageryProvider(cPaleoProvider(paleoUrl("land", a), PALEO_CREDIT), 1);
    oPaleo.setSource(paleoSource(paleoUrl("land", a)));
    oPaleo.setVisible(true);
  }

  // 그때의 레이어(`then`) — 연대마다 타일 주소가 달라 갈아 끼운다. 구는 같은 자리(차례)에 새로 넣는다
  var thenAt = null;
  function refreshThen(a) {
    if (a === thenAt || a == null) { thenAt = a == null ? thenAt : a; return; }
    thenAt = a;
    GEO_NAMES.filter(function (n) { return LAYER[n].then; }).forEach(function (name) {
      var at = viewer.imageryLayers.indexOf(cGeo[name]);
      viewer.imageryLayers.remove(cGeo[name], true);
      cGeo[name] = viewer.imageryLayers.addImageryProvider(cPaleoProvider(geoUrl(name), creditOf(name)), at);
      cRaise[name] = [cGeo[name]];
      oGeo[name].setSource(geoSource(name));
    });
    applyStack();
  }
  var wasPaleo = null, setsAt = 0;
  function showAge() {
    var p = paleoOn();
    ageRange.value = toSlider(age);
    if (document.activeElement !== ageInput) ageInput.value = ageText(age);
    var period = age > 0 ? periodOf(age) : "";
    $("age-period").textContent = period;
    $("age-now").disabled = !age;
    $("timebar").classList.toggle("paleo", p);
    var note = !age ? "" : p
      ? T("PALEOMAP 2016 판 회전으로 셈한 그때의 지구다 — 관측이 아니다. 오늘의 영상·지형·지질도는 오늘에만 뜬다")
      : T("오늘의 지구다 — 1 Ma 안에서 판이 움직인 것은 수십 km 안이다");
    if (p && isOn("coast")) {
      var c = coastStop(age);
      note += " " + (c == null ? T("옛 해안선은 이 연대에 없다 (0–535 Ma, 가까운 시점 10 Myr 안)")
                                : T("옛 해안선은 {age} Ma 의 것 — 화석이 가리키는 가장 깊은 바다", { age: c }));
    }
    $("age-note").textContent = note;
  }
  function applyAge(a) {
    a = snapAge(a);
    var changed = a !== age;
    age = a;
    save("gsm.earth.age", age);
    try {
      var q = new URLSearchParams(location.search);
      if (age) q.set("age", String(age)); else q.delete("age");
      var qs = q.toString();
      history.replaceState(null, "", location.pathname + (qs ? "?" + qs : "") + location.hash);
    } catch (e) { /* file:// 따위 */ }
    var p = paleoOn();
    showAge();
    if (p !== wasPaleo) {
      wasPaleo = p;
      cBase.show = !p;
      oBase.setVisible(!p);
      scene.globe.baseColor = Cesium.Color.fromCssColorString(p ? OCEAN : "#0b1a2a");
      $("map").style.background = p ? OCEAN : "";
      scene.terrainProvider = look.terrain && !p ? demTerrain : flatTerrain;
      terrainBox.disabled = p;
      exag.disabled = p || !look.terrain;
      applyStack();
    }
    showPaleo(p ? age : null);
    refreshThen(p ? age : null);
    // 점묶음 — 그때의 지구에서는 그 연대의 자리로 옮긴 것을 다시 받는다. 오늘의 지구끼리는 그대로다
    var want = p ? age : 0;
    if (want !== setsAt) {
      setsAt = want;
      ++setGen;
      pointsets.forEach(function (ps) { dropSet(ps.id); });
      renderSets();
    }
    if (changed) closePopup();
  }
  var ageTimer = 0;
  ageRange.addEventListener("input", function () {
    var a = fromSlider(+ageRange.value);
    ageInput.value = ageText(a);
    clearTimeout(ageTimer);
    ageTimer = setTimeout(function () { applyAge(a); }, 180);   // 끄는 동안 타일을 쏟아 묻지 않게
  });
  $("age-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var a = parseAge(ageInput.value);
    if (a == null) { ageInput.value = ageText(age); return; }
    ageInput.blur();
    applyAge(a);
  });
  ageInput.addEventListener("blur", function () { ageInput.value = ageText(age); });
  $("age-now").addEventListener("click", function () { applyAge(0); });

  // 그때의 지구를 누르면 — 그 자리에 있던 판 조각과, 그 판의 회전을 되돌린 **오늘의 자리**. 오늘의 자리에서
  // 지질 단위를 다시 묻는다. 계산이지 관측이 아니다
  function askPaleo(ll, pixel) {
    markAt(ll);
    var mine = ++asked, at = age;
    var head = "<h3>" + esc(T("그때의 지구 · {age}", { age: ageText(at) })) + "</h3>" + coordHead(ll);
    showPopup(head + '<p class="none">' + esc(T("읽는 중")) + "</p>", pixel);
    fetch(BASE + "earth/paleo/at/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) + "&age=" + at)
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (mine !== asked) return;
        if (d.error || !d.rows) { showPopup(head + '<p class="none">' + esc(d.error || d.text) + "</p>", pixel); return; }
        var today = [d.today_lon, d.today_lat];
        var html = head + "<table>" + d.rows.map(function (row) {
          return "<tr><th>" + esc(row[0]) + "</th><td>" + esc(row[1]) + "</td></tr>";
        }).join("") + "</table>" +
          '<button type="button" class="today-go" data-lon="' + today[0] + '" data-lat="' + today[1] + '">' +
          esc(T("오늘의 그 자리로")) + "</button>";
        showPopup(html + '<p class="none">' + esc(T("읽는 중")) + "</p>", pixel);
        return fetch(BASE + "earth/info/?lon=" + today[0].toFixed(4) + "&lat=" + today[1].toFixed(4) + "&z=" + hereZoom())
          .then(function (r) { return r.json(); })
          .then(function (info) {
            if (mine !== asked) return;
            html += "<h3>" + esc(T("오늘 그 자리의 지질 단위")) + "</h3>";
            html += info.units && info.units.length
              ? info.units.map(function (u) { return unitTable(u, today); }).join("")
              : '<p class="none">' + esc(T(info.error ? "속성을 받지 못했다" : "여기에는 지질 단위가 없다")) + "</p>";
            showPopup(html, pixel);
          });
      })
      .catch(function () { if (mine === asked) showPopup(head + '<p class="none">' + esc(T("속성을 받지 못했다")) + "</p>", pixel); });
  }
  function goToday(lon, lat) {
    var c = cameraLL();
    applyAge(0);
    goTo(lon, lat, Math.min(c ? c.h : HOME_H, 3000000));
  }

  renderSets();
  renderCatalog();
  renderActive();
  applyStack();
  setsAt = paleoOn() ? age : 0;
  applyAge(age);

  // 올리기 — 2D 의 불러오기와 같은 꼴. 몸은 지구다 — 지역 탭에도 뜬다
  var form = $("upload-form"), fileInput = $("upload-file"), msgBox = $("upload-msg");
  var PALETTE = ["#f2c14e", "#e4572e", "#4ea5d9", "#7bc47f", "#c879ff", "#ff8fab"];
  $("upload-color").value = PALETTE[pointsets.length % PALETTE.length];
  fileInput.addEventListener("change", function () {
    var label = form.querySelector(".filebox");
    label.classList.toggle("has", !!fileInput.files.length);
    label.querySelector("span").textContent = fileInput.files.length ? fileInput.files[0].name : T("CSV · GeoJSON 고르기");
  });
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    if (!fileInput.files.length) return;
    var data = new FormData(form);
    data.set("body", "earth");
    msgBox.className = "msg";
    msgBox.textContent = T("올리는 중");
    post(BASE + "pointsets/upload/", data).then(function (d) {
      pointsets.unshift(d.pointset);
      setOff(d.pointset.id, false);
      renderSets();
      flyToSet(d.pointset);
      form.reset();
      fileInput.dispatchEvent(new Event("change"));
      $("upload-color").value = PALETTE[pointsets.length % PALETTE.length];
      msgBox.className = "msg good";
      msgBox.textContent = [T("{n}점을 올렸다", { n: d.pointset.count })].concat(d.notes || []).join(" ");
    }).catch(function (err) {
      msgBox.className = "msg bad";
      msgBox.textContent = (err && err.message) || T("올리지 못했다");
    });
  });

  // ══ 좌표로 이동 — 좌표 막대 ════════════════════════════════════
  //
  // 지명 찾기는 아직 없다 — 지역 탭의 찾기는 VWorld(한국)라 온 지구를 덮지 못한다
  var gotoForm = $("goto-form"), gotoInput = $("goto-input");
  function parseLatLon(text) {
    var m = /^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/.exec(text);
    if (!m) return null;
    var lat = +m[1], lon = +m[2];
    return Math.abs(lat) <= 90 && Math.abs(lon) <= 360 ? { lat: lat, lon: lon > 180 ? lon - 360 : lon } : null;
  }
  gotoForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var ll = parseLatLon(gotoInput.value);
    if (ll) goTo(ll.lon, ll.lat, 120000);
  });

  // ══ 자전축 — 구에서 방향을 잡는 꼬챙이 (041·045) ═════════════════
  //
  // 구를 돌리고 기울이다 보면 어느 쪽이 북인지 놓친다. 지구 고정 좌표(ECEF)의 Z 축이 곧 자전축이다. 달(041·045)과
  // 같다 — 지구 속을 지나는 토막도 흐린 끊은 선으로 비쳐 남극점 → 중심 → 북극점이 한 막대로 읽힌다.
  // **가까이 가면 치운다**(카메라 높이 4 800 km 밑 — 화성의 두 배). 평면은 늘 북쪽이 위라 구에서만 보인다
  var AXIS_OUT = R * 1.45, AXIS_NEAR = 4800000;
  var axisOn = saved("gsm.earth.axis", "on") !== "off", axisFar = true;
  var WHITE_A = Cesium.Color.WHITE;
  var axisEntities = [
    viewer.entities.add({
      polyline: { positions: [new Cesium.Cartesian3(0, 0, -AXIS_OUT), new Cesium.Cartesian3(0, 0, AXIS_OUT)],
                  arcType: Cesium.ArcType.NONE, width: 2.5, material: WHITE_A.withAlpha(0.95),
                  depthFailMaterial: new Cesium.PolylineDashMaterialProperty({ color: WHITE_A.withAlpha(0.5), dashLength: 12 }) },
    }),
    // 중심 — 늘 비쳐 보인다
    viewer.entities.add({
      position: Cesium.Cartesian3.ZERO,
      point: { pixelSize: 6, color: WHITE_A.withAlpha(0.7), outlineColor: Cesium.Color.BLACK, outlineWidth: 1,
               disableDepthTestDistance: Number.POSITIVE_INFINITY },
    }),
  ].concat([[1, T("북극점")], [-1, T("남극점")]].reduce(function (all, end) {
    // 표면의 극점 — 뒤로 돌면 가려진다
    all.push(viewer.entities.add({
      position: new Cesium.Cartesian3(0, 0, end[0] * ELL.minimumRadius),     // 극 반지름
      point: { pixelSize: 8, color: WHITE_A, outlineColor: Cesium.Color.BLACK, outlineWidth: 2 },
    }));
    // 밖으로 뻗은 끝의 이름 — 극점이 뒤에 있어도 어느 쪽이 북인지 보인다
    all.push(viewer.entities.add({
      position: new Cesium.Cartesian3(0, 0, end[0] * AXIS_OUT),
      label: { text: end[1], font: "600 12px system-ui, sans-serif", fillColor: WHITE_A,
               outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
               verticalOrigin: end[0] > 0 ? Cesium.VerticalOrigin.BOTTOM : Cesium.VerticalOrigin.TOP,
               pixelOffset: new Cesium.Cartesian2(0, end[0] > 0 ? -4 : 4),
               disableDepthTestDistance: Number.POSITIVE_INFINITY },
    }));
    return all;
  }, []));
  function syncAxisNear() {
    var c = cameraLL(), far = !c || c.h > AXIS_NEAR;
    if (far !== axisFar) { axisFar = far; applyAxis(); }
  }
  function applyAxis() {
    axisEntities.forEach(function (e) { e.show = axisOn && axisFar; });
    $("tool-axis").classList.toggle("on", axisOn);
    $("tool-axis").setAttribute("aria-pressed", axisOn ? "true" : "false");
  }
  $("tool-axis").addEventListener("click", function () {
    axisOn = !axisOn;
    save("gsm.earth.axis", axisOn ? "on" : "off");
    applyAxis();
  });
  applyAxis();

  // ══ 누른 자리 — 속성을 읽은 곳에 표를 꽂는다 (041) ═══════════════
  //
  // 팝업만 뜨면 "어디를 읽었나" 가 모호하다 — 팝업은 누른 자리 옆으로 비켜 서고, 구를 돌리면 더
  // 멀어진다. 속이 빈 고리를 누른 자리에 꽂고, 팝업을 닫으면 뽑는다. 찍은 점(속이 찬 번호 점)과
  // 헷갈리지 않게 꼴을 달리했다
  var MARK_URL = (function () {
    var c = document.createElement("canvas"), s = 28;
    c.width = c.height = s;
    var g = c.getContext("2d");
    g.lineWidth = 5; g.strokeStyle = "rgba(0,0,0,.85)";
    g.beginPath(); g.arc(s / 2, s / 2, 9, 0, 2 * Math.PI); g.stroke();
    g.lineWidth = 2.5; g.strokeStyle = "#fff";
    g.beginPath(); g.arc(s / 2, s / 2, 9, 0, 2 * Math.PI); g.stroke();
    g.fillStyle = "#000"; g.beginPath(); g.arc(s / 2, s / 2, 3.2, 0, 2 * Math.PI); g.fill();
    g.fillStyle = "#fff"; g.beginPath(); g.arc(s / 2, s / 2, 2, 0, 2 * Math.PI); g.fill();
    return c.toDataURL();
  })();
  var markC = viewer.entities.add({
    show: false, position: Cesium.Cartesian3.fromDegrees(0, 0, 0, ELL),
    billboard: { image: MARK_URL, heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                 disableDepthTestDistance: NO_DEPTH },
  });
  var markO = new ol.Feature();
  markO.setStyle(new ol.style.Style({ image: new ol.style.Icon({ src: MARK_URL }) }));
  var oMark = new ol.layer.Vector({ source: new ol.source.Vector({ features: [markO] }), zIndex: 300 });
  flat.addLayer(oMark);
  function markAt(ll) {
    markC.show = !!ll;
    markO.setGeometry(ll ? new ol.geom.Point(fromLL(ll)) : undefined);
    if (ll) markC.position = Cesium.Cartesian3.fromDegrees(ll[0], ll[1], 0, ELL);
  }

  // ══ 도구 — 점 찍기·거리·넓이·범위 (041) ═══════════════════════════
  //
  // 2D 의 그리기 도구와 같은 넷이다. **찍고 잰 것은 경위도로 한 곳에 들고, 구와 평면이 저마다
  // 그린다** — 켠 레이어·점묶음처럼 넘어가도 그대로 남는다. 그리던 것(끝내지 않은 선)만 넘어갈 때
  // 버리므로, 그리는 동안은 저절로 넘어가지 않는다(`drawing()`).
  //
  // 길이·넓이는 **평균 반지름의 구**(6 371.0088 km)로 잰다 — 평면의 가로는 위도만큼 늘어나 있어 평면
  // 좌표로 재면 틀린다. 넓이는 OpenLayers 의 `ol.sphere.getArea` 와 같은 식이고 반지름도 같다
  var tool = "";                           // "" 이면 누르면 속성을 읽는다
  var temps = [], ranges = [], measured = null;
  var tempSeq = 0, rangeSeq = 0, lastMeasure = "";
  var sketch = [], hover = null, boxFrom = null, boxTo = null;   // 구에서 그리는 중인 것
  var flatSketching = false;

  function rad(d) { return d * Math.PI / 180; }
  function arc(a, b) {
    var dLat = rad(b[1] - a[1]), dLon = rad(b[0] - a[0]);
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
    return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)));
  }
  function lengthOf(coords) {
    var m = 0;
    for (var i = 1; i < coords.length; i++) m += arc(coords[i - 1], coords[i]);
    return m;
  }
  function areaOf(ring) {
    var sum = 0, n = ring.length;
    for (var i = 0; i < n; i++) {
      var p = ring[i], q = ring[(i + 1) % n];
      sum += rad(q[0] - p[0]) * (2 + Math.sin(rad(p[1])) + Math.sin(rad(q[1])));
    }
    return Math.abs(sum * R * R / 2);
  }
  // 경도를 앞 꼭짓점에서 180° 안쪽으로 — 날짜변경선(±180°)을 건너도 선이 지구를 한 바퀴 돌지 않게
  function unwrap(prev, ll) {
    if (!prev) return ll;
    var lon = ll[0];
    while (lon - prev[0] > 180) lon -= 360;
    while (prev[0] - lon > 180) lon += 360;
    return [lon, ll[1]];
  }
  function asLength(m) { return m >= 1000 ? (m / 1000).toFixed(2) + " km" : m.toFixed(1) + " m"; }
  function asArea(m2) {
    return m2 >= 1e6 ? Math.round(m2 / 1e6).toLocaleString() + " km²" : Math.round(m2).toLocaleString() + " m²";
  }
  function pair(ll) { var w = wrapLon(ll); return w[1].toFixed(5) + ", " + w[0].toFixed(5); }
  function measureOf(m) {
    return m.kind === "area" ? { kind: T("넓이"), text: asArea(areaOf(m.coords)) }
                             : { kind: T("거리"), text: asLength(lengthOf(m.coords)) };
  }

  // 범위 — 경위도 네모. 등거리 원통에서 끈 네모가 곧 경위도 네모다. 구에서는 두 귀를 잇는다
  function rangeFacts(r) {
    var mid = (r.s + r.n) / 2;
    return {
      nw: [r.w, r.n], ne: [r.e, r.n], se: [r.e, r.s], sw: [r.w, r.s],
      center: [(r.w + r.e) / 2, mid],
      area: R * R * rad(r.e - r.w) * (Math.sin(rad(r.n)) - Math.sin(rad(r.s))),
      // 가로는 가운데 위도에서 잰다 — 위아래 변은 위도가 달라 길이가 다르다
      width: R * rad(r.e - r.w) * Math.cos(rad(mid)),
      height: R * rad(r.n - r.s),
    };
  }
  function rangeRows(f) {
    var rows = {};
    rows[T("북서")] = pair(f.nw); rows[T("북동")] = pair(f.ne);
    rows[T("남동")] = pair(f.se); rows[T("남서")] = pair(f.sw);
    rows[T("중앙")] = pair(f.center);
    rows[T("넓이")] = asArea(f.area);
    rows[T("가로 × 세로")] = asLength(f.width) + " × " + asLength(f.height);
    return rows;
  }
  function rangeText(r) {
    var rows = rangeRows(rangeFacts(r));
    return [T("범위 {n}", { n: r.no })].concat(Object.keys(rows).map(function (k) { return k + "\t" + rows[k]; })).join("\n");
  }
  function rangeOf(a, b) {
    b = unwrap(a, b);
    return { w: Math.min(a[0], b[0]), e: Math.max(a[0], b[0]), s: Math.min(a[1], b[1]), n: Math.max(a[1], b[1]) };
  }

  // ── 그리기 — 평면 ──
  var drawSource = new ol.source.Vector();
  var sketchSource = new ol.source.Vector();
  var LABEL_FONT = "600 12px ui-monospace, Menlo, monospace";
  function olLabel(text, offsetY) {
    return new ol.style.Text({ text: text, font: LABEL_FONT, offsetY: offsetY || 0, overflow: true,
                               fill: new ol.style.Fill({ color: "#fff" }), stroke: new ol.style.Stroke({ color: "#000", width: 4 }) });
  }
  function drawStyle(feature) {
    var kind = feature.get("kind"), label = feature.get("label");
    if (kind === "temp") {
      return new ol.style.Style({
        image: new ol.style.Circle({ radius: 5.5, fill: new ol.style.Fill({ color: "#fff" }),
                                     stroke: new ol.style.Stroke({ color: "#000", width: 2 }) }),
        text: olLabel(String(feature.get("no")), -14),
      });
    }
    if (kind === "range") {
      return new ol.style.Style({
        fill: new ol.style.Fill({ color: "rgba(255,255,255,.10)" }),
        stroke: new ol.style.Stroke({ color: "#e4e4e4", width: 2 }),
        text: olLabel(label),
      });
    }
    // 잰 선·면, 그리는 중인 것 — 검은 테두리 위에 흰 끊은 선
    return [
      new ol.style.Style({ stroke: new ol.style.Stroke({ color: "rgba(0,0,0,.7)", width: 4.5 }) }),
      new ol.style.Style({
        fill: new ol.style.Fill({ color: "rgba(255,255,255,.14)" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 2.5, lineDash: [7, 5] }),
        image: new ol.style.Circle({ radius: 4, fill: new ol.style.Fill({ color: "#fff" }),
                                     stroke: new ol.style.Stroke({ color: "#000", width: 1.5 }) }),
        text: label ? olLabel(label) : undefined,
      }),
    ];
  }
  var oDraw = new ol.layer.Vector({ source: drawSource, style: drawStyle, zIndex: 200 });
  flat.addLayer(oDraw);
  var flatInteraction = null;
  function eqc(coords) { return coords.map(fromLL); }

  function installFlat() {
    if (flatInteraction) { flat.removeInteraction(flatInteraction); flatInteraction = null; }
    flatSketching = false;
    sketchSource.clear();
    if (tool === "box") {
      flatInteraction = new ol.interaction.DragBox({ condition: ol.events.condition.always, className: "range-box" });
      flatInteraction.on("boxend", function () {
        var x = flatInteraction.getGeometry().getExtent();
        if (ol.extent.getWidth(x) === 0 || ol.extent.getHeight(x) === 0) return;
        addRange(rangeOf(toLL([x[0], x[1]]), toLL([x[2], x[3]])));
      });
    } else if (tool === "line" || tool === "area") {
      flatInteraction = new ol.interaction.Draw({
        source: sketchSource, type: tool === "line" ? "LineString" : "Polygon", style: drawStyle,
      });
      var kind = tool;
      flatInteraction.on("drawstart", function (evt) {
        flatSketching = true;
        var geometry = evt.feature.getGeometry();
        geometry.on("change", function () {
          var coords = kind === "area" ? geometry.getCoordinates()[0] : geometry.getCoordinates();
          var got = measureOf({ kind: kind, coords: coords.map(toLL) });
          evt.feature.set("label", got.text);
          showMeasure(got);
        });
      });
      flatInteraction.on("drawend", function (evt) {
        var g = evt.feature.getGeometry();
        var coords = (kind === "area" ? g.getCoordinates()[0].slice(0, -1) : g.getCoordinates()).map(toLL);
        flatSketching = false;
        setTimeout(function () { sketchSource.clear(); });    // Draw 가 제 것을 넣은 뒤에 치운다
        finishMeasure(kind, coords);
      });
      flatInteraction.on("drawabort", function () { flatSketching = false; });
    }
    if (flatInteraction) flat.addInteraction(flatInteraction);
  }

  // ── 그리기 — 구 ──
  var cDraw = new Cesium.CustomDataSource("draw");
  viewer.dataSources.add(cDraw);
  var WHITE = Cesium.Color.WHITE, BLACK = Cesium.Color.BLACK;
  function dash() { return new Cesium.PolylineDashMaterialProperty({ color: WHITE, gapColor: BLACK.withAlpha(0.55), dashLength: 14 }); }
  function cLabel(text, offsetY) {
    return { text: text, font: LABEL_FONT, fillColor: WHITE, outlineColor: BLACK, outlineWidth: 4,
             style: Cesium.LabelStyle.FILL_AND_OUTLINE, pixelOffset: new Cesium.Cartesian2(0, offsetY || 0),
             heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: NO_DEPTH };
  }
  function positions(coords) { return ringPositions(coords); }
  function rangeRing(r) {
    // 위아래 변은 위선을 따라야 한다 — 대권으로 이으면 극 쪽으로 휜다. 촘촘히 찍어 위선을 따른다
    var out = [], steps = Math.max(2, Math.ceil((r.e - r.w) / 2));
    for (var i = 0; i <= steps; i++) out.push([r.w + (r.e - r.w) * i / steps, r.n]);
    for (i = steps; i >= 0; i--) out.push([r.w + (r.e - r.w) * i / steps, r.s]);
    out.push([r.w, r.n]);
    return out;
  }
  // 그리는 중인 선 — 누른 꼭짓점과 누르개 자리를 잇는다
  var sketchLine = cDraw.entities.add({
    polyline: { positions: new Cesium.CallbackProperty(function () {
      var pts = sketch.slice();
      if (hover && pts.length) pts.push(unwrap(pts[pts.length - 1], hover));
      if (tool === "area" && pts.length > 2) pts.push(pts[0]);
      return pts.length > 1 ? positions(pts) : [];
    }, false), width: 2.5, clampToGround: true, material: dash() },
  });
  var sketchBox = cDraw.entities.add({
    show: false,
    polyline: { positions: new Cesium.CallbackProperty(function () {
      return boxFrom && boxTo ? positions(rangeRing(rangeOf(boxFrom, boxTo))) : [];
    }, false), width: 2, clampToGround: true, material: WHITE },
  });
  var drawnEntities = [];
  function renderDrawn() {
    drawnEntities.forEach(function (e) { cDraw.entities.remove(e); });
    drawnEntities = [];
    drawSource.clear();
    function add(opts) { drawnEntities.push(cDraw.entities.add(opts)); }
    temps.forEach(function (t) {
      add({ position: Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0, ELL),
            point: { pixelSize: 10, color: WHITE, outlineColor: BLACK, outlineWidth: 2,
                     heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: NO_DEPTH },
            label: cLabel(String(t.no), -15) });
      drawSource.addFeature(new ol.Feature({ geometry: new ol.geom.Point(fromLL([t.lon, t.lat])), kind: "temp", no: t.no }));
    });
    ranges.forEach(function (r) {
      var ring = rangeRing(r), label = T("범위 {n}", { n: r.no });
      add({ polygon: { hierarchy: positions(ring), material: WHITE.withAlpha(0.1) } });
      add({ polyline: { positions: positions(ring), width: 2, clampToGround: true, material: Cesium.Color.fromCssColorString("#e4e4e4") } });
      add({ position: Cesium.Cartesian3.fromDegrees((r.w + r.e) / 2, (r.s + r.n) / 2, 0, ELL), label: cLabel(label) });
      drawSource.addFeature(new ol.Feature({ geometry: new ol.geom.Polygon([eqc(ring)]), kind: "range", label: label }));
    });
    if (measured) {
      var got = measureOf(measured), c = measured.coords;
      var line = measured.kind === "area" ? c.concat([c[0]]) : c;
      if (measured.kind === "area") add({ polygon: { hierarchy: positions(line), material: WHITE.withAlpha(0.14) } });
      add({ polyline: { positions: positions(line), width: 2.5, clampToGround: true, material: dash() } });
      var at = measured.kind === "area" ? centroid(c) : c[c.length - 1];
      add({ position: Cesium.Cartesian3.fromDegrees(at[0], at[1], 0, ELL), label: cLabel(got.text, measured.kind === "area" ? 0 : -16) });
      var geom = measured.kind === "area" ? new ol.geom.Polygon([eqc(line)]) : new ol.geom.LineString(eqc(line));
      drawSource.addFeature(new ol.Feature({ geometry: geom, kind: "measure", label: got.text }));
    }
    renderTemp();
  }
  function centroid(coords) {
    var x = 0, y = 0;
    coords.forEach(function (c) { x += c[0]; y += c[1]; });
    return [x / coords.length, y / coords.length];
  }

  // 구에서 누르고 끄는 것 — 읽는 처리기(LEFT_CLICK)와 따로 둔다
  var drawHandler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
  // Cesium 의 기본 두 번 누르기(개체를 따라가기)는 선을 끝내는 손과 부딪힌다
  viewer.screenSpaceEventHandler.removeInputAction(Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
  drawHandler.setInputAction(function (movement) {
    if (!tool) return;
    var ll = globeLL(movement.endPosition);
    if (tool === "box" && boxFrom) {
      if (ll) boxTo = ll;
      return;
    }
    hover = ll;
    if (sketch.length && ll) {
      var pts = sketch.concat([unwrap(sketch[sketch.length - 1], ll)]);
      showMeasure(measureOf({ kind: tool, coords: pts }));
    }
  }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);
  drawHandler.setInputAction(function () { finishGlobeSketch(); }, Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK);
  drawHandler.setInputAction(function (e) {
    if (tool !== "box") return;
    boxFrom = globeLL(e.position);
    boxTo = null;
    sketchBox.show = !!boxFrom;
  }, Cesium.ScreenSpaceEventType.LEFT_DOWN);
  drawHandler.setInputAction(function () {
    if (tool !== "box" || !boxFrom) return;
    var a = boxFrom, b = boxTo;
    boxFrom = boxTo = null;
    sketchBox.show = false;
    if (b && (a[0] !== b[0] || a[1] !== b[1])) addRange(rangeOf(a, b));
  }, Cesium.ScreenSpaceEventType.LEFT_UP);

  /** 도구가 켜져 있으면 누른 것을 도구가 받는다. 받았으면 true — 그때는 속성을 읽지 않는다. */
  function drawClick(ll) {
    if (!tool) return false;
    if (!ll) return true;
    if (tool === "point") addTemp(ll);
    else if (tool === "line" || tool === "area") {
      if (!sketch.length) { measured = null; lastMeasure = ""; renderDrawn(); }
      sketch.push(unwrap(sketch[sketch.length - 1], ll));
    }
    return true;
  }
  function finishGlobeSketch() {
    // 두 번 누르면 LEFT_CLICK 이 두 번 먼저 온다 — 겹친 꼭짓점을 걷어낸다
    var pts = sketch.filter(function (p, i) { return !i || arc(sketch[i - 1], p) > 1; });
    sketch = []; hover = null;
    if (pts.length >= (tool === "area" ? 3 : 2)) finishMeasure(tool, pts);
    else updateToolOut();
  }
  function cancelSketch() {
    sketch = []; hover = null; boxFrom = boxTo = null; sketchBox.show = false;
    if (flatInteraction && flatInteraction.abortDrawing) flatInteraction.abortDrawing();
    flatSketching = false;
    updateToolOut();
  }
  /** 무엇이든 그리는 중인가 — 그동안은 구와 평면을 저절로 넘지 않는다. */
  function drawing() { return sketch.length > 0 || !!boxFrom || flatSketching; }

  // ── 찍고 잰 것 ──
  // 재는 것은 한 번에 하나만 둔다 — 여럿이 겹치면 어느 수가 어느 선의 것인지 모른다. 범위는 여럿을 둔다
  function finishMeasure(kind, coords) {
    measured = { kind: kind, coords: coords };
    var got = measureOf(measured);
    renderDrawn();
    showMeasure(got, true);
  }
  function addTemp(ll) {
    var w = wrapLon(ll);
    tempSeq += 1;
    temps.push({ no: tempSeq, lon: w[0], lat: w[1] });
    renderDrawn();
  }
  function addRange(r) {
    rangeSeq += 1;
    r.no = rangeSeq;
    ranges.push(r);
    renderDrawn();
    showRange(r);
  }
  // 지금 보는 높이 — 점으로 옮겨 갈 때 당기거나 물리지 않는다
  function hereHeight() {
    if (mode === "flat") return resToHeight(groundRes());
    var c = cameraLL();
    return c ? Math.min(c.h, 200000) : 200000;
  }
  function pixelOf(ll) {
    if (mode === "flat") return flat.getPixelFromCoordinate(fromLL(ll));
    var p = scene.cartesianToCanvasCoordinates(Cesium.Cartesian3.fromDegrees(ll[0], ll[1], 0, ELL));
    return p ? [p.x, p.y] : [wrap.clientWidth / 2, wrap.clientHeight / 2];
  }
  function showRange(r) {
    var f = rangeFacts(r);
    lastMeasure = T("범위 {n}", { n: r.no }) + " " + asArea(f.area);
    var out = $("measure-out");
    out.textContent = lastMeasure;
    out.classList.add("done");
    updateToolOut();
    ++asked;
    markAt(null);
    showPopup("<h3>" + esc(T("범위 {n}", { n: r.no })) + "</h3><table>" + Object.keys(rangeRows(f)).map(function (k) {
      return "<tr><th>" + esc(k) + "</th><td>" + esc(rangeRows(f)[k]) + "</td></tr>";
    }).join("") + "</table>", pixelOf(f.center));
  }
  function showMeasure(got, done) {
    var out = $("measure-out");
    out.textContent = got.kind + " " + got.text;
    out.classList.toggle("done", !!done);
    lastMeasure = got.kind + " " + got.text;
    updateToolOut();
  }
  /** 손잡이 옆의 알림 — 누른 곳 가까이에서 답이 나와야 한다(2D 와 같다). */
  function updateToolOut() {
    var out = $("tool-out"), bits = [];
    if (lastMeasure) bits.push(lastMeasure);
    if (temps.length) bits.push(T("점 {n}개", { n: temps.length }));
    if (tool === "point" && !temps.length) bits.push(T("지도를 눌러 점을 찍는다"));
    if (tool === "line" && !lastMeasure) bits.push(T("눌러 가며 잇는다 · 두 번 누르면 끝"));
    if (tool === "area" && !lastMeasure) bits.push(T("눌러 가며 두른다 · 두 번 누르면 끝"));
    if (tool === "box" && !ranges.length) bits.push(T("누른 채 끌어 네모를 그린다"));
    out.textContent = bits.join("  ·  ");
    out.hidden = !bits.length;
  }
  // 복사 — 운영이 http 로 열리는 자리가 있어 clipboard API 가 없으면 옛 길(textarea)로 (2D 와 같다)
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () {
        return legacyCopy(text) ? undefined : Promise.reject();
      });
    }
    return legacyCopy(text) ? Promise.resolve() : Promise.reject();
  }
  function legacyCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.cssText = "position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;";
    document.body.appendChild(area);
    area.select();
    var ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    area.remove();
    return ok;
  }
  popupBody.addEventListener("click", function (e) {
    var go = e.target.closest(".today-go");
    if (go) { goToday(+go.dataset.lon, +go.dataset.lat); return; }
    var head = e.target.closest(".popup-coord");
    if (!head) return;
    var mark = head.querySelector(".copy");
    copyText(head.dataset.copy).then(function () {
      head.classList.add("copied");
      mark.textContent = T("복사했다");
      setTimeout(function () { head.classList.remove("copied"); mark.textContent = T("복사"); }, 900);
    }, function () {});
  });
  function copyButton(text, copied, title) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "temp-coord";
    b.title = title;
    b.textContent = text;
    b.addEventListener("click", function () {
      var done = function () { b.textContent = T("복사했다"); setTimeout(function () { b.textContent = text; }, 700); };
      copyText(copied).then(done, function () {});
    });
    return b;
  }
  function renderTemp() {
    var host = $("temp-list");
    $("count-temp").textContent = temps.length + ranges.length;
    updateToolOut();
    host.innerHTML = "";
    if (!temps.length && !ranges.length) {
      host.innerHTML = '<li class="empty">' + T("지도 오른쪽 위 <b>점</b> 도구로 찍는다") + "</li>";
      return;
    }
    ranges.forEach(function (r) {
      var li = document.createElement("li");
      li.className = "range-item";
      var no = document.createElement("span");
      no.className = "temp-no range";
      no.textContent = r.no;
      var f = rangeFacts(r);
      li.append(no,
        copyButton(asArea(f.area) + " · " + pair(f.center), rangeText(r), T("눌러서 꼭짓점·중앙·넓이를 복사한다")),
        iconButton("⊙", T("이 범위로 가서 수치를 본다"), false, function () {
          var span = Math.max((r.e - r.w) * Math.cos(rad(f.center[1])), r.n - r.s);
          goTo(f.center[0], f.center[1], Math.max(30000, span * M_PER_DEG * 1.6));
          setTimeout(function () { showRange(r); }, 1600);
        }),
        iconButton("×", T("지운다"), false, function () {
          ranges = ranges.filter(function (x) { return x !== r; });
          closePopup();
          renderDrawn();
        }));
      host.appendChild(li);
    });
    temps.forEach(function (t) {
      var li = document.createElement("li");
      var no = document.createElement("span");
      no.className = "temp-no";
      no.textContent = t.no;
      var text = pair([t.lon, t.lat]);
      li.append(no, copyButton(text, text, T("눌러서 복사한다")),
        iconButton("⊙", T("이 점으로 이동"), false, function () { goTo(t.lon, t.lat, hereHeight()); }),
        iconButton("×", T("지운다"), false, function () {
          temps = temps.filter(function (x) { return x !== t; });
          renderDrawn();
        }));
      host.appendChild(li);
    });
  }
  function clearDrawn() {
    cancelSketch();
    temps = []; ranges = []; measured = null;
    tempSeq = rangeSeq = 0;
    lastMeasure = "";
    var out = $("measure-out");
    out.textContent = T("아직 잰 것이 없다");
    out.classList.remove("done");
    closePopup();
    renderDrawn();
  }

  // 점묶음으로 저장 — 2D 와 같은 길(`pointsets/create/`)이고 몸도 지구다. 좌표는 ±180° 로 되돌려 싣는다
  function lonlat(coords) { return coords.map(wrapLon); }
  function saveTemp() {
    var msg = $("save-msg");
    if (!temps.length && !ranges.length && !measured) {
      msg.className = "msg bad";
      msg.textContent = T("저장할 점이 없다.");
      return;
    }
    var name = prompt(T("목록 이름"), T("찍은 점 {date}", { date: new Date().toLocaleDateString(LANG === "en" ? "en-GB" : "ko-KR") }));
    if (name === null) return;
    var shapes = ranges.map(function (r) {
      return { geometry: { type: "Polygon", coordinates: [lonlat(rangeRing(r))] },
               label: T("범위 {n}", { n: r.no }), props: rangeRows(rangeFacts(r)) };
    });
    if (measured) {
      var got = measureOf(measured), c = lonlat(measured.coords);
      shapes.push({ geometry: measured.kind === "area" ? { type: "Polygon", coordinates: [c.concat([c[0]])] }
                                                      : { type: "LineString", coordinates: c },
                    label: got.kind + " " + got.text, props: {} });
    }
    msg.className = "msg";
    msg.textContent = T("저장하는 중…");
    fetch(BASE + "pointsets/create/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({
        name: name, color: "#f2f2f2", body: "earth", shapes: shapes,
        points: temps.map(function (t) { return { lat: t.lat, lon: t.lon, label: T("점 {n}", { n: t.no }) }; }),
      }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.d.error || "");
        pointsets.unshift(res.d.pointset);
        setOff(res.d.pointset.id, false);
        renderSets();
        // 저장했으니 임시 표시는 치운다 — 같은 점이 두 겹으로 남으면 헷갈린다
        clearDrawn();
        msg.className = "msg good";
        msg.textContent = T("'{name}' 으로 저장했다.", { name: res.d.pointset.name });
      })
      .catch(function (e) {
        msg.className = "msg bad";
        msg.textContent = (e && e.message) || T("저장하지 못했다");
      });
  }

  function setTool(next) {
    cancelSketch();
    tool = next;
    document.querySelectorAll(".tool[data-draw]").forEach(function (b) { b.classList.toggle("on", b.dataset.draw === next); });
    $("globe").style.cursor = $("map").style.cursor = next ? "crosshair" : "";
    // 구에서 범위를 끄는 동안은 구가 끌려 돌지 않는다. 휠로 당기는 것은 된다
    var cam = scene.screenSpaceCameraController, still = next === "box";
    cam.enableRotate = cam.enableTranslate = cam.enableTilt = cam.enableLook = !still;
    if (next) { closePopup(); }
    installFlat();
    updateToolOut();
  }
  document.querySelectorAll(".tool[data-draw]").forEach(function (b) {
    // 누른 손잡이를 다시 누르면 꺼진다 — 아무것도 안 켜져 있으면 누르면 속성을 읽는다
    b.addEventListener("click", function () { setTool(tool === b.dataset.draw ? "" : b.dataset.draw); });
  });
  $("tool-clear").addEventListener("click", clearDrawn);
  $("clear-temp").addEventListener("click", clearDrawn);
  $("save-temp").addEventListener("click", saveTemp);
  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape" || /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) return;
    if (drawing()) cancelSketch();
    else if (tool) setTool("");
  });
  renderTemp();

  // ══ 그림으로 내려받기 (048) ═══════════════════════════════════════
  //
  // 2D·지구 3D 의 "그림" 과 같은 꼴 — 지금 보는 화면 한 장에 밑의 띠를 붙여 **무엇을 봤는지** 적는다.
  // 띠에는 구·평면, 배경(보정했으면 그 값), 켠 레이어, 점묶음, 가운데, 출처, 날짜가 들어간다.
  //
  // - 구는 Cesium 캔버스를 **그린 바로 그 프레임(`postRender`) 안에서** 옮겨 담는다. WebGL 은 그린 뒤 버퍼를
  //   비우는데, `preserveDrawingBuffer` 를 켜면 늘 느려진다(지구 3D 와 같은 판단). 타일이 다 올 때까지
  //   (`tilesLoaded`, 길어야 10 초) 기다린다. 기울인 화면은 앞뒤의 축척이 달라 **축척 막대를 넣지 않고**
  //   기울기·방위를 적는다
  // - 평면은 2D 처럼 레이어 캔버스들을 투명도·변환 그대로 겹친다. 배경이 WebGL 타일(042)이라 역시 그린
  //   바로 뒤(`rendercomplete`)에 담는다. 음영 겹치기는 화면에서 CSS 의 곱하기(mix-blend-mode)라 합칠 때도
  //   곱한다. 축척 막대를 넣는다 — 가운데 위도에서 잰다(`ol.proj.getPointResolution`)
  //
  // 팝업·패널은 HTML 이라 담기지 않는다. 찍고 잰 것·누른 자리의 고리·자전축은 캔버스에 있어 담긴다.
  // GIBS·Macrostrat 의 타일은 모두 CORS 로 받는다 — 하나라도 아니면 캔버스가 더럽혀져 뽑히지 않는다
  var exportBtn = $("tool-export");
  exportBtn.addEventListener("click", function () {
    exportBtn.disabled = true;
    var finish = function (canvas) {
      if (!canvas) { exportBtn.disabled = false; alert(T("그림을 만들지 못했다")); return; }
      canvas.toBlob(function (blob) {
        exportBtn.disabled = false;
        if (!blob) { alert(T("그림을 만들지 못했다")); return; }
        var a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = "GSM-earth-" + stampText().replace(/[-: ]/g, "").slice(0, 12) + ".png";
        document.body.appendChild(a);
        a.click();
        setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
      }, "image/png");
    };
    if (mode === "flat") captureFlat(finish); else captureGlobe(finish);
  });

  function captureGlobe(done) {
    var t0 = Date.now();
    var remove = scene.postRender.addEventListener(function () {
      if (!scene.globe.tilesLoaded && Date.now() - t0 < 10000) return;
      remove();
      var gl = scene.canvas, w = gl.clientWidth, h = gl.clientHeight;
      done(safely(function () { return compose(w, h, gl.width / w, function (ctx) { ctx.drawImage(gl, 0, 0); }); }));
    });
    scene.requestRender();
  }

  function captureFlat(done) {
    flat.once("rendercomplete", function () {
      var size = flat.getSize(), w = size[0], h = size[1], ratio = window.devicePixelRatio || 1;
      done(safely(function () {
        return compose(w, h, ratio, function (ctx) {
          flat.getViewport().querySelectorAll(".ol-layers canvas").forEach(function (c) {
            if (!c.width) return;
            var holder = c.parentNode, opacity = holder.style.opacity || c.style.opacity;
            ctx.globalAlpha = opacity === "" ? 1 : Number(opacity);
            ctx.globalCompositeOperation = getComputedStyle(holder).mixBlendMode === "multiply" ? "multiply" : "source-over";
            var m = /^matrix\(([^(]*)\)$/.exec(c.style.transform || "");
            var t = m ? m[1].split(",").map(Number) : [w / c.width, 0, 0, h / c.height, 0, 0];
            ctx.setTransform(t[0] * ratio, t[1] * ratio, t[2] * ratio, t[3] * ratio, t[4] * ratio, t[5] * ratio);
            ctx.drawImage(c, 0, 0);
          });
          ctx.globalAlpha = 1;
          ctx.globalCompositeOperation = "source-over";
        });
      }));
    });
    flat.renderSync();
  }

  /** 교차 출처 타일이 섞여 캔버스가 더럽혀지면 뽑을 때(`toBlob`) 막힌다 — 여기서 미리 걸러 null 을 낸다. */
  function safely(make) {
    try {
      var canvas = make();
      canvas.getContext("2d").getImageData(0, 0, 1, 1);
      return canvas;
    } catch (e) { return null; }
  }

  function stampText() {
    var d = new Date();
    function two(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + two(d.getMonth() + 1) + "-" + two(d.getDate()) + " " +
      two(d.getHours()) + ":" + two(d.getMinutes());
  }

  /** 화면 한 장(`paint` 가 그린다) + 밑의 띠. 띠는 달과 같은 흑백이다 — 인쇄해도 읽히게. */
  function compose(w, h, ratio, paint) {
    var lineH = 17, pad = 12, bar = mode === "flat" ? 170 : 0;
    // 넘치는 줄은 " · " 에서 끊어 다음 줄로 잇는다 — 출처는 잘리면 안 된다(누가 만든 그림인지가 거기 있다)
    var probe = document.createElement("canvas").getContext("2d");
    var lines = [];
    exportLines().forEach(function (line, i) {
      probe.font = (i === 0 ? "bold 14px " : "12px ") + "sans-serif";
      var max = w - pad * 2 - (i === 0 ? bar : 0), cur = "";
      line.split(" · ").forEach(function (bit) {
        var next = cur ? cur + " · " + bit : bit;
        if (cur && probe.measureText(next).width > max) { lines.push(cur); cur = "   " + bit; }
        else cur = next;
      });
      lines.push(i === 0 ? { head: cur } : cur);
    });
    var foot = pad * 2 + lineH * lines.length;
    var out = document.createElement("canvas");
    out.width = Math.round(w * ratio);
    out.height = Math.round((h + foot) * ratio);
    var ctx = out.getContext("2d");
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, out.width, out.height);
    paint(ctx);
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    ctx.fillStyle = "#f4f4f4";
    ctx.fillRect(0, h, w, foot);
    ctx.fillStyle = "#111";
    ctx.fillRect(0, h, w, 1);
    ctx.textBaseline = "top";
    lines.forEach(function (line, i) {
      var head = typeof line === "object";
      ctx.font = (head ? "bold 14px " : "12px ") + "sans-serif";
      ctx.fillStyle = head ? "#111" : "#333";
      ctx.fillText(fitText(ctx, head ? line.head : line, w - pad * 2 - (head ? bar : 0)), pad, h + pad + i * lineH + (i ? 3 : 0));
    });
    if (bar) drawScaleBar(ctx, w - pad - 150, h + pad + 2, 150);
    return out;
  }

  /** 띠에 적을 줄들. 첫 줄이 제목이다. */
  function exportLines() {
    var shown = active.filter(function (e) { return !LAYER[e.name].then === !paleoOn(); })
                      .map(function (e) { return T(LAYER[e.name].title); });
    var mine = pointsets.filter(function (ps) { return ps.visible; });
    var select = $("basemap"), base = select.options[select.selectedIndex].text;
    var tuned = TUNES.filter(function (k) { return tune[k] !== TUNE_DEFAULT[k]; });
    if (tuned.length || tune.shade) {
      base += " · " + T("영상 보정") + " " + tuned.map(function (k) { return tuneText(k, tune[k]); }).join("/") +
              (tune.shade ? (tuned.length ? " + " : "") + T("음영") : "");
    }
    var where;
    if (mode === "flat") {
      where = fmt(clean(wrapLon(toLL(flat.getView().getCenter()))));
    } else {
      var p = pivot(false);
      if (p) {
        var c = ELL.cartesianToCartographic(p.pos), a = anglesAt(p.pos, false);
        where = fmt(clean([Cesium.Math.toDegrees(c.longitude), Cesium.Math.toDegrees(c.latitude)])) + " · " +
                T("기울기 {tilt}° · 방위 {heading}°", { tilt: Math.round(90 + a.pitch), heading: Math.round(a.heading) % 360 });
      } else where = "—";
      if (look.terrain) where += " · " + T("지형 과장") + " ×" + (look.exag / 10).toFixed(1);
    }
    var credits = paleoOn() ? [PALEO_CREDIT] : [BASES[look.base].credit];
    active.forEach(function (e) {
      if (!LAYER[e.name].then === !paleoOn()) credits.push(creditOf(e.name) || LAYER[e.name].src);
    });
    if (mode === "globe" && look.terrain && !paleoOn()) credits.push(DEM_CREDIT);
    credits = credits.filter(function (c, i) { return c && credits.indexOf(c) === i; });
    var kind = mode !== "flat" ? T("구") : proj === EQC ? T("평면") :
      T("평면") + " (" + T(proj === NPS ? "북극 평사도법" : "남극 평사도법") + ")";
    var out = [T("대돌여지도") + " · " + T("온 지구") + " · " + kind + " · " + stampText()];
    if (age) out.push(T("연대") + ": " + ageText(age) + (paleoOn() ? " · " + T("PALEOMAP 2016 판 회전으로 셈한 그때의 지구") : ""));
    out.push(T("배경") + ": " + (paleoOn() ? T("판 조각 (PALEOMAP 2016)") : base));
    out.push(T("레이어") + ": " + (shown.length ? shown.join(" / ") : "—"));
    if (mine.length) out.push(T("점묶음") + ": " + mine.map(function (ps) { return ps.name; }).join(", "));
    out.push(T("가운데") + ": " + where);
    out.push(T("출처") + ": " + credits.join(" · "));
    return out;
  }

  // 소수 넷째 자리에서 0 이 되는 값은 0 으로 — "-0.0000°" 가 찍히지 않게
  function clean(ll) { return ll.map(function (v) { return Math.abs(v) < 5e-5 ? 0 : v; }); }
  function fitText(ctx, text, max) {
    if (ctx.measureText(text).width <= max) return text;
    while (text.length > 1 && ctx.measureText(text + "…").width > max) text = text.slice(0, -1);
    return text + "…";
  }

  /** 평면 가운데 위도의 땅 축척으로 막대를 그린다. 1·2·5 × 10ⁿ 로 반올림한다. */
  function drawScaleBar(ctx, x, y, maxWidth) {
    var v = flat.getView();
    var metersPerPx = ol.proj.getPointResolution(proj, v.getResolution(), v.getCenter(), "m");
    if (!isFinite(metersPerPx) || metersPerPx <= 0) return;
    var raw = metersPerPx * maxWidth;
    var pow = Math.pow(10, Math.floor(Math.log10(raw)));
    var nice = [5, 2, 1].map(function (k) { return k * pow; }).filter(function (n) { return n <= raw; })[0] || pow;
    var px = nice / metersPerPx;
    ctx.fillStyle = "#111";
    ctx.fillRect(x, y + 14, px, 4);
    ctx.fillRect(x, y + 10, 1.5, 8);
    ctx.fillRect(x + px - 1.5, y + 10, 1.5, 8);
    ctx.font = "12px sans-serif";
    ctx.fillText(nice >= 1000 ? (nice / 1000) + " km" : nice + " m", x, y - 4);
  }

  // ══ 대기 화면 (058) — 지구(`map.js`)와 같은 규칙이다 ═══════════════
  // 첫 화면의 타일이 다 오면 걷는다. 적어도 1.2 초는 보이고, 상류가 느려도 12 초 뒤에는 걷는다.
  // 구는 Cesium 의 타일 대기열이 비었을 때, 평면으로 열리면 OpenLayers 의 첫 `rendercomplete` 다
  (function () {
    var splash = document.getElementById("splash");
    if (!splash) return;
    var shownAt = Date.now(), done = false, off = null;
    function lift() {
      if (done) return;
      done = true;
      if (off) off();
      setTimeout(function () {
        splash.classList.add("gone");
        setTimeout(function () { splash.remove(); }, 600);
      }, Math.max(0, 1200 - (Date.now() - shownAt)));
    }
    off = viewer.scene.globe.tileLoadProgressEvent.addEventListener(function (queued) {
      if (queued === 0 && mode === "globe" && viewer.scene.globe.tilesLoaded) lift();
    });
    flat.once("rendercomplete", function () { if (mode === "flat") lift(); });
    setTimeout(lift, 12000);
  })();

  // ══ 처음 자리 — 기억한 것. 처음이면 한반도를 멀리서 ═══════════════
  // 맨 끝에 둔다 — 평면으로 여는 길이 팝업·목록을 다 만든 뒤라야 한다
  try {
    var v = JSON.parse(saved("gsm.earth.view", "null"));
    if (v && isFinite(v.lon) && isFinite(v.lat) && isFinite(v.h)) {
      viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(v.lon, v.lat, v.h, ELL),
                              orientation: { heading: v.heading || 0, pitch: isFinite(v.pitch) ? v.pitch : -Math.PI / 2, roll: 0 } });
    } else flyGlobe(HOME[0], HOME[1], HOME_H);
    var f = JSON.parse(saved("gsm.earth.flat", "null"));
    if (saved("gsm.earth.mode", "globe") === "flat" && f && isFinite(f.lon) && isFinite(f.res)) {
      setMode("flat", { lon: f.lon, lat: f.lat, h: resToHeight(f.res) });
    }
  } catch (e) { flyGlobe(HOME[0], HOME[1], HOME_H); }
})();
