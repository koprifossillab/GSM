/* 대돌여지도 · 달 (devlog 036·037·038, P05).
 *
 * **둥근 달로 들어가서, 가까이 가면 평면에서 본다.** 한 화면에 둘이 있다.
 *
 * - 구 — CesiumJS. 달 타원체를 알아 극까지 온전하다. LOLA 지형을 세우고 기울여 본다
 * - 평면 — OpenLayers. 2D 화면과 같은 손맛이고 축척 막대가 붙는다. 투영은 달의 등거리 원통
 *   (IAU_2015:30110, 미터)이다 — Trek 의 경위도 격자가 그대로 맞는다
 *
 * 곧장 내려다보며 가까이 가면 평면으로, 평면에서 멀어지면 구로 넘어간다. 기울여 보는 동안은 구에
 * 머문다. 극(위도 75° 너머)은 평면이 가로로 늘어나 구에 머문다 (P05 §3).
 *
 * 영상 배경(LRO WAC·LOLA 음영)은 브라우저가 Trek 을 곧장 부르고, 지질도·표고·속성·범례·지명은
 * 서버의 문(`trek.py`)을 거친다.
 */
(function () {
  "use strict";

  var BASE = location.pathname.replace(/moon\/?$/, "");
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

  // ══ 달과 격자 ═════════════════════════════════════════════════════
  var R = 1737400;                                   // 달 반지름 (IAU 2015, 구)
  var M_PER_DEG = Math.PI * R / 180;
  var TREK = "https://trek.nasa.gov/tiles/Moon/EQ/";
  // 줌 끝은 2026-09-29 에 한 장씩 받아 보았다 — WAC 는 8, LOLA 음영은 6 (7 은 404), Kaguya 는 10 (11 은 404)
  //
  // 고해상(`kaguya`)은 **WAC 위에 Kaguya 지형 카메라 정사 모자이크를 얹은 것**이다 (043). Kaguya 는 줌 10
  // (한 픽셀 약 21 m)까지라 WAC(약 100 m)보다 다섯 배 촘촘하지만 틈이 있다 — 위도 75° 안쪽도 곳곳이 비고
  // (0–2 %), 극 둘레는 40 % 넘게 빈다. 넓게 볼 때는 해가 낮은 WAC 쪽이 지형이 산다. 그래서 `under` 로 WAC 를
  // 늘 밑에 깔고 Kaguya 는 줌 `min`(8, WAC 가 원자료를 다 쓰는 줌)부터 얹는다 — 틈에는 WAC 가 비친다
  var BASES = {
    kaguya: { url: TREK + "Kaguya_TCortho_Mosaic_Global_4096ppd/1.0.0/default/default028mm/{z}/{y}/{x}.png",
              max: 10, min: 8, under: "wac", credit: "SELENE (Kaguya) TC · JAXA" },
    wac: { url: TREK + "LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{z}/{y}/{x}.jpg",
           max: 8, credit: "LRO LROC WAC · NASA/GSFC/Arizona State University" },
    lola: { url: TREK + "LRO_LOLA_Shade_Global_256ppd_v06/1.0.0/default/default028mm/{z}/{y}/{x}.png",
            max: 6, credit: "LRO LOLA · NASA/GSFC" },
  };
  // 지질 레이어 목록 — 2D 의 카탈로그처럼 골라 켜면 "켠 지질 레이어" 로 올라온다(오버레이).
  // 레이어군을 더하면(원소·광물 …) 목록에 저절로 선다. 이름은 서버 `trek.LAYERS` 의 열쇠다
  //   info    누르면 읽는 갈래 (`moon/info/?layer=`)   legend  범례 칸의 갈래   src  카드 밑의 출처
  var CATALOG = [
    { group: "달 지질 (USGS 1:500만, 2020)", layers: [
      { name: "units", title: "지질 단위", info: "units", legend: "units", src: "USGS · NASA Moon Trek" },
      { name: "contacts", title: "지질 경계", src: "USGS · NASA Moon Trek" },
      { name: "linear", title: "선 구조 (능선·열구·단층)", src: "USGS · NASA Moon Trek" },
    ] },
    // 원도 6 장 — 통합 지질도가 다듬기 전의 원래 단위(195 가지). 우리가 파일을 굽는다 (`moonmap.py`, 039)
    { group: "달 지질 원도 (USGS 1:500만, 1971–1979)", layers: [
      { name: "orig-units", title: "원도 지질 단위", info: "orig", legend: "orig",
        src: "USGS I-703·948·1034·1047·1062·1162 · colors E. Lutz" },
      { name: "orig-lines", title: "원도 구조선", legend: "orig-lines", src: "USGS 1971–1979" },
    ] },
  ];
  var LAYER = {};
  CATALOG.forEach(function (g) { g.layers.forEach(function (l) { LAYER[l.name] = l; }); });
  var GEO_NAMES = Object.keys(LAYER);
  var GEO_MAX = 12;
  function geoUrl(name) { return BASE + "moon/tiles/" + name + "/{z}/{x}/{y}.png"; }
  var GEO_CREDIT = "Unified Geologic Map of the Moon 1:5M (Fortezzo et al., 2020, USGS) via NASA Moon Trek";
  var ORIG_CREDIT = "USGS 1:5M lunar geologic maps 1971–1979 (renovated by Fortezzo & Hare, 2013); colors after E. Lutz";
  function creditOf(name) { return name === "units" ? GEO_CREDIT : name === "orig-units" ? ORIG_CREDIT : undefined; }

  // ── 켠 것 — 구와 평면이 함께 쓴다. 이 브라우저에 기억한다 ──
  var look = {
    base: saved("gsm.moon.base", "kaguya"),
    terrain: saved("gsm.moon.terrain", "on") !== "off",
    exag: +saved("gsm.moon.exag", "20"),
  };
  if (!BASES[look.base]) look.base = "kaguya";
  // 켠 지질 레이어 — 맨 앞이 위다. `[{name, opacity}]`. 처음이면 지질 단위 하나를 반쯤 비치게
  var active = (function () {
    try {
      var list = JSON.parse(saved("gsm.moon.layers", "null"));
      if (Array.isArray(list)) {
        return list.filter(function (e) { return e && LAYER[e.name]; })
                   .map(function (e) { return { name: e.name, opacity: isFinite(e.opacity) ? +e.opacity : 1 }; });
      }
    } catch (e) { /* 깨진 값 */ }
    return [{ name: "units", opacity: 0.6 }];
  })();
  function entryOf(name) { return active.filter(function (e) { return e.name === name; })[0]; }
  function isOn(name) { return !!entryOf(name); }
  function saveLayers() { save("gsm.moon.layers", JSON.stringify(active)); }

  // ══ 구 — Cesium ═══════════════════════════════════════════════════
  var MOON = Cesium.Ellipsoid.MOON;
  // 타원체를 넘기지 않는 곳(카메라 기본 범위·좌표 풀이)이 지구로 여기지 않게 기본값부터 바꾼다
  Cesium.Ellipsoid.default = MOON;
  function scheme() { return new Cesium.GeographicTilingScheme({ ellipsoid: MOON }); }
  // `min` 은 제공자의 minimumLevel 이 아니라 레이어의 minimumTerrainLevel 로 건다 — minimumLevel 은 그 줌의
  // 타일이 네 장을 넘으면 그리기가 흐트러진다(Cesium 문서). 구의 격자와 영상 격자가 같아 줌이 맞는다
  function cesiumBase(key) {
    var b = BASES[key];
    return new Cesium.ImageryLayer(new Cesium.UrlTemplateImageryProvider({
      url: b.url, tilingScheme: scheme(), maximumLevel: b.max, credit: b.credit,
    }), b.min ? { minimumTerrainLevel: b.min } : {});
  }

  // 지형 — LOLA 표고, 서버가 65×65 Terrarium 으로 옮겨 준다 (036)
  var DEM_SIZE = 65;
  var DEM_MAX = 8;             // 서버의 `trek.DEM_MAX_ZOOM`. 그 너머는 부모 격자를 늘려 쓴다
  var demMemo = {};
  function demGrid(x, y, level) {
    var id = level + "/" + x + "/" + y;
    if (!demMemo[id]) {
      demMemo[id] = fetch(BASE + "moon/dem/" + id + ".png").then(function (r) {
        if (!r.ok) throw new Error(r.status);
        return r.blob();
      }).then(function (blob) {
        return createImageBitmap(blob, { colorSpaceConversion: "none", premultiplyAlpha: "none" });
      }).then(function (bitmap) {
        var canvas = document.createElement("canvas");
        canvas.width = canvas.height = DEM_SIZE;
        var ctx = canvas.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(bitmap, 0, 0);
        var px = ctx.getImageData(0, 0, DEM_SIZE, DEM_SIZE).data;
        var out = new Float32Array(DEM_SIZE * DEM_SIZE);
        for (var i = 0; i < out.length; i++) {
          out[i] = px[i * 4] * 256 + px[i * 4 + 1] + px[i * 4 + 2] / 256 - 32768;
        }
        return out;
      }).catch(function () {
        delete demMemo[id];                    // 다음에 다시 묻는다. 이번에는 평평하게
        return new Float32Array(DEM_SIZE * DEM_SIZE);
      });
    }
    return demMemo[id];
  }
  function heights(x, y, level) {
    if (level <= DEM_MAX) return demGrid(x, y, level);
    // 부모(줌 8) 격자의 한 조각을 겹선형으로 늘린다
    var k = Math.pow(2, level - DEM_MAX);
    var ax = Math.floor(x / k), ay = Math.floor(y / k);
    var ox = (x - ax * k) / k, oy = (y - ay * k) / k, span = 1 / k, n = DEM_SIZE - 1;
    return demGrid(ax, ay, DEM_MAX).then(function (src) {
      var out = new Float32Array(DEM_SIZE * DEM_SIZE);
      for (var j = 0; j < DEM_SIZE; j++) {
        var fy = (oy + span * j / n) * n, y0 = Math.min(n - 1, Math.floor(fy)), ty = fy - y0;
        for (var i = 0; i < DEM_SIZE; i++) {
          var fx = (ox + span * i / n) * n, x0 = Math.min(n - 1, Math.floor(fx)), tx = fx - x0;
          var a = src[y0 * DEM_SIZE + x0], b = src[y0 * DEM_SIZE + x0 + 1];
          var c = src[(y0 + 1) * DEM_SIZE + x0], d = src[(y0 + 1) * DEM_SIZE + x0 + 1];
          out[j * DEM_SIZE + i] = (a * (1 - tx) + b * tx) * (1 - ty) + (c * (1 - tx) + d * tx) * ty;
        }
      }
      return out;
    });
  }
  var lolaTerrain = new Cesium.CustomHeightmapTerrainProvider({
    width: DEM_SIZE, height: DEM_SIZE, tilingScheme: scheme(), callback: heights,
    credit: "LRO LOLA DEM (NASA/GSFC)",
  });
  var flatTerrain = new Cesium.EllipsoidTerrainProvider({ ellipsoid: MOON });

  // 배경은 두 겹이다 — 맨 밑의 WAC(`cUnder`, 고해상일 때만 보인다)와 고른 배경(`cBase`). 영상 보정·배경 바꾸기는
  // 차례(`get(0)`)가 아니라 이 둘을 잡고 한다
  var cUnder = cesiumBase("wac");
  cUnder.show = !!BASES[look.base].under;
  var cBase = cesiumBase(look.base);
  var viewer = new Cesium.Viewer("globe", {
    globe: new Cesium.Globe(MOON),
    baseLayer: cUnder,
    terrainProvider: look.terrain ? lolaTerrain : flatTerrain,
    // 달에는 대기가 없다. 지구 전용 단추(주소 찾기·지도 고르개·시간 막대)도 뺀다
    skyAtmosphere: false,
    baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
    navigationHelpButton: false, animation: false, timeline: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false,
  });
  viewer.imageryLayers.add(cBase, 1);
  var scene = viewer.scene;
  scene.globe.showGroundAtmosphere = false;
  scene.globe.enableLighting = false;
  scene.globe.baseColor = Cesium.Color.fromCssColorString("#1a1a1a");
  // 타일을 조금 덜 촘촘하게 — 표고·지질도가 서버를 거치므로 한 화면의 요청을 줄인다
  scene.globe.maximumScreenSpaceError = 3;
  scene.fog.enabled = false;
  if (scene.moon) scene.moon.show = false;       // 하늘에 뜨는 지구의 달 — 달 위에서는 우습다
  if (scene.sun) scene.sun.show = false;
  scene.backgroundColor = Cesium.Color.BLACK;
  scene.verticalExaggeration = look.exag / 10;
  window.__gsmMoon = viewer;

  var cGeo = {};
  GEO_NAMES.forEach(function (name) {
    var layer = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: geoUrl(name), tilingScheme: scheme(), maximumLevel: GEO_MAX, hasAlphaChannel: true,
      credit: creditOf(name),
    }));
    layer.show = false;
    cGeo[name] = layer;
  });

  // ══ 평면 — OpenLayers ═════════════════════════════════════════════
  //
  // 투영은 둘이다. `IAU_2015:30100` 은 달의 경위도(도) — 자료가 그 꼴로 온다. `IAU_2015:30110` 은
  // 등거리 원통(미터)이고 화면이 쓴다. 둘 사이는 곱셈 하나다. 지구의 EPSG:4326 을 빌리지 않는다 —
  // OpenLayers 가 지구 반지름으로 거리·축척을 재 3.67 배 틀어진다 (P05 §3)
  var LL = new ol.proj.Projection({ code: "IAU_2015:30100", units: "degrees",
                                    extent: [-180, -90, 180, 90], global: true });
  var EQC = new ol.proj.Projection({
    code: "IAU_2015:30110", units: "m", global: true,
    extent: [-180 * M_PER_DEG, -90 * M_PER_DEG, 180 * M_PER_DEG, 90 * M_PER_DEG],
    // 등거리 원통은 남북이 참이고 동서가 위도만큼 늘어난다. 축척 막대는 동서로 잰다 — 가운데 위도의
    // cos 를 곱해 땅의 미터로 바꾼다
    getPointResolution: function (resolution, point) {
      return resolution * Math.cos(Math.max(-89.9, Math.min(89.9, point[1] / M_PER_DEG)) * Math.PI / 180);
    },
  });
  ol.proj.addProjection(LL);
  ol.proj.addProjection(EQC);
  ol.proj.addCoordinateTransforms(LL, EQC,
    function (c) { return [c[0] * M_PER_DEG, c[1] * M_PER_DEG]; },
    function (c) { return [c[0] / M_PER_DEG, c[1] / M_PER_DEG]; });
  function toLL(xy) { return [xy[0] / M_PER_DEG, xy[1] / M_PER_DEG]; }
  function fromLL(ll) { return [ll[0] * M_PER_DEG, ll[1] * M_PER_DEG]; }

  // Trek·우리 문의 격자 — 줌 0 이 가로 2·세로 1 장, y 는 북쪽부터
  function grid(maxZoom) {
    var res = [];
    for (var z = 0; z <= maxZoom; z++) res.push(180 * M_PER_DEG / Math.pow(2, z) / 256);
    return new ol.tilegrid.TileGrid({ extent: EQC.getExtent(), origin: [-180 * M_PER_DEG, 90 * M_PER_DEG],
                                      resolutions: res, tileSize: 256 });
  }
  function tileSource(template, maxZoom, attribution, crossOrigin) {
    return new ol.source.TileImage({
      projection: EQC, tileGrid: grid(maxZoom), attributions: attribution, wrapX: true, crossOrigin: crossOrigin,
      tileUrlFunction: function (coord) {
        var z = coord[0], x = coord[1], y = coord[2], n = Math.pow(2, z + 1);
        if (y < 0 || y >= n / 2) return undefined;
        x = ((x % n) + n) % n;
        return template.replace("{z}", z).replace("{x}", x).replace("{y}", y);
      },
    });
  }
  // 배경은 WebGL 타일이다 — 영상 보정(밝기·대비·감마·채도)을 GPU 셰이더로 건다(042). 셰이더가 영상을 읽으려면
  // CORS 로 받아야 한다(Trek 은 `*`)
  function baseSource(key) { var b = BASES[key]; return tileSource(b.url, b.max, b.credit, "anonymous"); }
  function baseLayer(className, key) {
    return new ol.layer.WebGLTile({
      className: className, source: baseSource(key),
      style: { variables: { exposure: 0, contrast: 0, gamma: 1, saturation: 0 },
               exposure: ["var", "exposure"], contrast: ["var", "contrast"],
               gamma: ["var", "gamma"], saturation: ["var", "saturation"] },
    });
  }
  // 구처럼 두 겹 — 밑의 WAC 는 고해상일 때만, 고른 배경은 `min` 줌부터 (평면의 줌은 타일 줌과 같다)
  var oUnder = baseLayer("moon-base-under", "wac");
  var oBase = baseLayer("moon-base", look.base);
  function placeBase() {
    var b = BASES[look.base];
    oUnder.setVisible(!!b.under);
    oBase.setMinZoom(b.min ? b.min - 0.5 : -Infinity);
  }
  placeBase();
  var SHADE = BASES.lola;
  var oShade = new ol.layer.Tile({ className: "moon-shade", visible: false, opacity: 0.7,
                                   source: tileSource(SHADE.url, SHADE.max, SHADE.credit) });
  var oGeo = {};
  GEO_NAMES.forEach(function (name) {
    oGeo[name] = new ol.layer.Tile({ source: tileSource(geoUrl(name), GEO_MAX, creditOf(name)),
                                     visible: false });
  });
  var oPoints = new ol.layer.Group({ layers: [] });
  var flat = new ol.Map({
    target: "map",
    layers: [oUnder, oBase, oShade].concat(GEO_NAMES.map(function (n) { return oGeo[n]; }), [oPoints]),
    view: new ol.View({ projection: EQC, center: [0, 0], resolution: 500, maxResolution: 180 * M_PER_DEG / 256,
                        constrainResolution: false }),
    controls: ol.control.defaults.defaults({ attributionOptions: { collapsible: true } }).extend([
      new ol.control.ScaleLine({ target: $("scalebar"), bar: true, steps: 4, text: true, minWidth: 110 }),
    ]),
  });

  // ══ 구 ⇄ 평면 ═════════════════════════════════════════════════════
  //
  // 넘는 높이를 둘로 둔다(되돌이). 구에서 250 km 밑으로 곧장 내려다보면 평면으로, 평면에서 400 km
  // 높이만큼 멀어지면 구로. 둘이 같으면 문턱에서 오락가락한다
  var TO_FLAT_H = 250000, TO_GLOBE_H = 400000;
  var POLE_LIMIT = 75;                    // 이 위도 너머는 평면이 늘어나 구에 머문다
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
    var c = MOON.cartesianToCartographic(viewer.camera.positionWC);
    return c ? { lon: Cesium.Math.toDegrees(c.longitude), lat: Cesium.Math.toDegrees(c.latitude), h: c.height } : null;
  }
  function flyGlobe(lon, lat, h, duration) {
    var dest = Cesium.Cartesian3.fromDegrees(lon, lat, h, MOON);
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
      var view = flat.getView();
      view.setCenter(fromLL([c.lon, c.lat]));
      view.setResolution(Math.min(heightToRes(c.h), heightToRes(TO_GLOBE_H) * 0.9));
      view.setRotation(0);
      mode = "flat";
      wrap.className = "moon-flat";
      // 숨은 구는 그리기를 멈춘다 — 안 보이는데 GPU 를 먹고, 평면의 WebGL 배경과 다툰다 (042)
      viewer.useDefaultRenderLoop = false;
      flat.updateSize();
    } else {
      var v = flat.getView(), ll = toLL(v.getCenter());
      flyGlobe(ll[0], ll[1], (at && at.h) || resToHeight(v.getResolution()));
      mode = "globe";
      viewer.useDefaultRenderLoop = true;
      wrap.className = "moon-globe";
    }
    save("gsm.moon.mode", mode);
  }

  viewer.camera.moveEnd.addEventListener(function () {
    var c = cameraLL();
    if (!c) return;
    save("gsm.moon.view", JSON.stringify({
      lon: +c.lon.toFixed(5), lat: +c.lat.toFixed(5), h: Math.round(c.h),
      heading: +viewer.camera.heading.toFixed(4), pitch: +viewer.camera.pitch.toFixed(4),
    }));
    if (mode !== "globe") return;
    if (c.h > TO_FLAT_H) { autoFlat = true; return; }
    var straight = viewer.camera.pitch < Cesium.Math.toRadians(-80);
    if (autoFlat && straight && Math.abs(c.lat) <= POLE_LIMIT && !drawing()) setMode("flat", c);
  });
  flat.on("moveend", function () {
    if (mode !== "flat") return;
    var v = flat.getView(), ll = toLL(v.getCenter());
    save("gsm.moon.flat", JSON.stringify({ lon: +ll[0].toFixed(5), lat: +ll[1].toFixed(5), res: Math.round(v.getResolution()) }));
    if (drawing()) return;                // 그리던 선이 끊기지 않게 (041)
    if (v.getResolution() > heightToRes(TO_GLOBE_H) || Math.abs(ll[1]) > POLE_LIMIT + 3) setMode("globe");
  });

  $("tool-mode").addEventListener("click", function () {
    if (mode === "globe") {
      var c = cameraLL();
      if (!c) return;
      // 멀리서 누르면 문턱 높이까지 내려와 평면으로. 극이면 평면이 되는 위도까지 끌어온다
      setMode("flat", { lon: c.lon, lat: Math.max(-POLE_LIMIT, Math.min(POLE_LIMIT, c.lat)), h: Math.min(c.h, TO_FLAT_H) });
    } else {
      autoFlat = false;
      var res = flat.getView().getResolution();
      setMode("globe", { h: Math.max(resToHeight(res), TO_FLAT_H * 1.4) });
    }
  });
  $("tool-home").addEventListener("click", function () {
    if (mode === "flat") setMode("globe", { h: 5200000 });
    flyGlobe(0, 0, 5200000, 1.5);
  });
  $("tool-top").addEventListener("click", function () {
    var c = cameraLL();
    if (c) flyGlobe(c.lon, c.lat, c.h, 0.8);
  });

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
    save("gsm.moon.base", look.base);
    var layers = viewer.imageryLayers;
    layers.remove(cBase, true);
    cBase = cesiumBase(look.base);
    layers.add(cBase, layers.indexOf(cUnder) + 1);
    cUnder.show = !!BASES[look.base].under;
    oBase.setSource(baseSource(look.base));
    placeBase();
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
  // "음영 겹치기" 는 WAC 영상 위에 LOLA 음영을 얹어 지형의 그늘을 살린다. 평면은 곱하기(multiply)로 섞고
  // (Lutz 가 색 지질도를 음영에 곱한 것과 같은 수, CP 94), 구는 섞는 법이 없어 반투명으로 얹는다
  var TUNE_DEFAULT = { bright: 100, contrast: 100, gamma: 100, sat: 100, shade: false };
  var PRESETS = {
    crisp: { bright: 105, contrast: 160, gamma: 90, sat: 100, shade: false },
    relief: { bright: 110, contrast: 130, gamma: 110, sat: 100, shade: true },
  };
  var tune = (function () {
    try { return Object.assign({}, TUNE_DEFAULT, JSON.parse(saved("gsm.moon.tune", "{}")) || {}); }
    catch (e) { return Object.assign({}, TUNE_DEFAULT); }
  })();
  var cShade = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
    url: SHADE.url, tilingScheme: scheme(), maximumLevel: SHADE.max, credit: SHADE.credit,
  }), viewer.imageryLayers.indexOf(cBase) + 1);
  cShade.alpha = 0.4;
  var TUNES = ["bright", "contrast", "gamma", "sat"];
  function tuneText(key, v) { return key === "gamma" ? (v / 100).toFixed(2) : v + "%"; }
  function applyTune() {
    // 밑의 WAC 에도 같게 건다 — 고해상의 틈으로 비치는 WAC 가 따로 놀지 않게
    [cUnder, cBase].forEach(function (base) {
      base.brightness = tune.bright / 100;
      base.contrast = tune.contrast / 100;
      base.gamma = tune.gamma / 100;
      base.saturation = tune.sat / 100;
    });
    // 음영을 음영 위에 겹칠 까닭은 없다 — 배경이 LOLA 음영이면 끈다
    var shade = tune.shade && look.base !== "lola";
    cShade.show = shade;
    oShade.setVisible(shade);
    [oUnder, oBase].forEach(function (layer) {
      layer.updateStyleVariables({ exposure: tune.bright / 100 - 1, contrast: tune.contrast / 100 - 1,
                                   gamma: tune.gamma / 100, saturation: tune.sat / 100 - 1 });
    });
    TUNES.forEach(function (k) {
      $("tune-" + k).value = tune[k];
      $("tune-" + k + "-num").textContent = tuneText(k, tune[k]);
    });
    $("tune-shade").checked = tune.shade;
    var changed = TUNES.some(function (k) { return tune[k] !== TUNE_DEFAULT[k]; }) || tune.shade;
    $("tune-state").textContent = changed ? T("고침") : "";
    save("gsm.moon.tune", JSON.stringify(tune));
  }
  TUNES.forEach(function (k) {
    $("tune-" + k).addEventListener("input", function () { tune[k] = +this.value; applyTune(); });
  });
  $("tune-shade").addEventListener("change", function () { tune.shade = this.checked; applyTune(); });
  $("tune-reset").addEventListener("click", function () { tune = Object.assign({}, TUNE_DEFAULT); applyTune(); });
  document.querySelectorAll("#tune [data-preset]").forEach(function (b) {
    b.addEventListener("click", function () { tune = Object.assign({}, PRESETS[b.dataset.preset]); applyTune(); });
  });
  applyTune();

  // ── 지질 레이어 — 2D 처럼 목록에서 켜고, 켠 것은 카드로 쌓는다 ──
  //
  // 쌓는 차례는 구와 평면이 같다. 구는 배경(0 번) 위로 아래 것부터 `raiseToTop`, 평면은 `zIndex`
  function applyStack() {
    GEO_NAMES.forEach(function (name) {
      var e = entryOf(name);
      cGeo[name].show = !!e;
      oGeo[name].setVisible(!!e);
      if (e) { cGeo[name].alpha = e.opacity; oGeo[name].setOpacity(e.opacity); }
    });
    active.slice().reverse().forEach(function (e, i) {
      viewer.imageryLayers.raiseToTop(cGeo[e.name]);
      oGeo[e.name].setZIndex(i + 1);
    });
    // 점묶음은 늘 지질 위다
    oPoints.setZIndex(100);
    syncLegend();
  }
  function addLayer(name) {
    if (isOn(name)) return;
    active.unshift({ name: name, opacity: /units$/.test(name) ? 0.6 : 1 });
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
      g.layers.forEach(function (l) {
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
        details.appendChild(row);
      });
      host.appendChild(details);
    });
  }

  // 지형 (구에서만)
  var terrainBox = $("moon-terrain"), exag = $("moon-exag");
  terrainBox.checked = look.terrain;
  exag.disabled = !look.terrain;
  terrainBox.addEventListener("change", function () {
    look.terrain = terrainBox.checked;
    scene.terrainProvider = look.terrain ? lolaTerrain : flatTerrain;
    exag.disabled = !look.terrain;
    save("gsm.moon.terrain", look.terrain ? "on" : "off");
  });
  exag.value = look.exag;
  function applyExag() {
    look.exag = +exag.value;
    scene.verticalExaggeration = look.exag / 10;
    $("moon-exag-num").textContent = "×" + (look.exag / 10).toFixed(1);
    save("gsm.moon.exag", look.exag);
  }
  exag.addEventListener("input", applyExag);
  applyExag();

  // ══ 좌표 ══════════════════════════════════════════════════════════
  function fmt(ll) {
    return T("달 위도 {lat}° · 경도 {lon}°", { lat: ll[1].toFixed(4), lon: ll[0].toFixed(4) });
  }
  function globeLL(position) {
    var ray = viewer.camera.getPickRay(position);
    var cartesian = ray && scene.globe.pick(ray, scene);
    if (!cartesian) cartesian = viewer.camera.pickEllipsoid(position, MOON);
    if (!cartesian) return null;
    var c = MOON.cartesianToCartographic(cartesian);
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
  // 첫 줄은 누른 자리의 달 위경도 — 2D 처럼 누르면 "위도, 경도" 로 복사한다(아래 `popupBody` 의 click, 041)
  function coordHead(ll) {
    var lat = ll[1].toFixed(6), lon = ll[0].toFixed(6);
    return '<button type="button" class="popup-coord" title="' + esc(T("눌러서 복사한다")) + '" data-copy="' +
           lat + ", " + lon + '"><span class="k">' + esc(T("달 위도")) + '</span><span class="v">' + lat +
           '</span><span class="k">' + esc(T("달 경도")) + '</span><span class="v">' + lon +
           '</span><span class="copy">' + esc(T("복사")) + "</span></button>";
  }
  // 켠 레이어 가운데 읽을 수 있는 것(통합·원도)을 위에서부터 다 묻는다 — 둘을 켜 두면 견줘 읽는다
  function askUnit(ll, pixel) {
    markAt(ll);
    var head = coordHead(ll);
    var layers = active.filter(function (e) { return LAYER[e.name].info; }).map(function (e) { return LAYER[e.name]; });
    if (!layers.length) { showPopup(head, pixel); return; }
    var mine = ++asked;
    showPopup(head + '<p class="none">' + esc(T("읽는 중")) + "</p>", pixel);
    Promise.all(layers.map(function (l) {
      var url = BASE + "moon/info/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4) +
                (l.info === "units" ? "" : "&layer=" + l.info);
      return fetch(url).then(function (r) { return r.json(); }).catch(function () { return { error: true }; });
    })).then(function (all) {
      if (mine !== asked) return;
      var html = head;
      all.forEach(function (data, i) {
        html += "<h3>" + esc(T(layers[i].title)) + "</h3>";
        if (data.error) { html += '<p class="none">' + esc(T("속성을 받지 못했다")) + "</p>"; return; }
        if (!data.rows || !data.rows.length) {
          html += '<p class="none">' + esc(data.note || T("여기에는 지질 단위가 없다")) + "</p>";
          return;
        }
        var sw = layers[i].info === "units" ? swatches[data.unit] : null;
        var chip = sw ? '<img class="swatch-img" src="' + sw + '" alt="">'
                 : data.color ? '<span class="swatch-img" style="display:inline-block;background:' + esc(data.color) + '"></span>' : "";
        var unitRow = data.rows.map(function (r) { return r[1]; }).indexOf(data.unit);
        html += "<table>" + data.rows.map(function (row, k) {
          return "<tr><th>" + esc(row[0]) + "</th><td>" + (k === unitRow ? chip : "") + esc(row[1]) + "</td></tr>";
        }).join("") + "</table>";
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
    showPopup((ll ? coordHead(ll) : "") + "<h3>" + esc(title) + '</h3><p class="from"><span class="swatch" style="background:' +
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
      if (pos) { var c = MOON.cartesianToCartographic(pos); ll = [Cesium.Math.toDegrees(c.longitude), Cesium.Math.toDegrees(c.latitude)]; }
      showFeature(entity.gsmProps, entity.gsmSet, ll, px);
      return;
    }
    var at = globeLL(click.position);
    if (at) askUnit(at, px);
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
    askUnit(wrapLon(toLL(e.coordinate)), e.pixel);
  });

  // ══ 범례 — 오른쪽 아래, 펼쳐 둔다 ═══════════════════════════════
  //
  // 켠 레이어마다 칸 하나 — 통합 지질도는 시대별 49 단위, 원도는 29 갈래와 구조선. 켠 차례(위가 앞)대로
  var swatches = {};
  var legends = {};                // 갈래 → 그린 HTML (한 번 받는다)
  var dock = $("legend-dock");
  dock.open = saved("gsm.moon.legend", "open") !== "closed";
  dock.addEventListener("toggle", function () { save("gsm.moon.legend", dock.open ? "open" : "closed"); });
  function legendHtml(kind) {
    if (legends[kind] !== undefined) return Promise.resolve(legends[kind]);
    var url = BASE + "moon/legend/" + (kind === "units" ? "" : "?layer=orig");
    return fetch(url).then(function (r) { return r.json(); }).then(function (data) {
      var html = "";
      if (kind === "units") {
        // 상류의 범례 차례는 시대가 섞여 있다(에라토스테네스기 바다 `Em` 이 임브리움기 크레이터 뒤에 온다).
        // 처음 나온 차례대로 시대를 모아 한 번씩만 머리를 단다
        var ages = [], byAge = {};
        (data.items || []).forEach(function (item) {
          if (item.unit) swatches[item.unit] = item.image;
          var age = item.age || "";
          if (!byAge[age]) { byAge[age] = []; ages.push(age); }
          byAge[age].push(item);
        });
        ages.forEach(function (age) {
          if (age) html += '<li class="age">' + esc(age) + "</li>";
          byAge[age].forEach(function (item) {
            html += '<li><img src="' + esc(item.image) + '" alt="">' + esc(item.label) + "</li>";
          });
        });
      } else if (kind === "orig") {
        (data.units || []).forEach(function (c) {
          html += '<li><span class="chip" style="background:' + esc(c.color) + '"></span>' + esc(c.label) + "</li>";
        });
      } else {
        (data.lines || []).forEach(function (c) {
          html += '<li><span class="chip line' + (c.dash ? " dash" : "") + '" style="border-color:' + esc(c.color) +
                  '"></span>' + esc(c.label) + "</li>";
        });
      }
      legends[kind] = html;
      return html;
    }).catch(function () { return '<li class="empty">' + esc(T("범례를 받지 못했다")) + "</li>"; });
  }
  var legendAsked = 0;
  function syncLegend() {
    var layers = active.filter(function (e) { return LAYER[e.name].legend; }).map(function (e) { return LAYER[e.name]; });
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
  // 팝업의 색 조각이 쓰므로 통합판 범례는 처음에 받아 둔다
  legendHtml("units");

  // ══ 내 자료 — 달 점묶음 (037) ═════════════════════════════════════
  //
  // 지구의 점묶음과 같은 틀(`PointSet`)이고 `body: "moon"` 만 다르다. 구에는 Cesium 의 점·선·면으로,
  // 평면에는 OpenLayers 의 벡터 레이어로 같은 GeoJSON 을 그린다
  var pointsets = JSON.parse(($("pointset-data") || {}).textContent || "[]");
  var cSets = {}, oSets = {}, extents = {};
  var PS_OFF = "gsm.moon.pointsets.off";
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
  // 점(창어 4 호)이 달을 뚫고 앞면에 비친다. 1 500 km 는 달 반지름보다 짧다
  var NO_DEPTH = 1500000;
  function ringPositions(ring) {
    var flatArr = [];
    ring.forEach(function (c) { flatArr.push(c[0], c[1]); });
    return Cesium.Cartesian3.fromDegreesArray(flatArr, MOON);
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
        position: Cesium.Cartesian3.fromDegrees(g.coordinates[0], g.coordinates[1], 0, MOON),
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
  function loadSet(ps) {
    if (loading[ps.id]) return loading[ps.id];
    loading[ps.id] = fetch(BASE + "pointsets/" + ps.id + "/geojson/").then(function (r) { return r.json(); }).then(function (data) {
      var feats = data.features || [];
      extents[ps.id] = extentOf(feats);
      var source = new Cesium.CustomDataSource("ps-" + ps.id);
      feats.forEach(function (f) { addEntity(source, ps, f); });
      source.show = ps.visible;
      viewer.dataSources.add(source);
      cSets[ps.id] = source;
      var layer = new ol.layer.Vector({
        source: new ol.source.Vector({ features: new ol.format.GeoJSON().readFeatures(data,
                                         { dataProjection: LL, featureProjection: EQC }) }),
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
    if (mode === "flat" && Math.abs(lat) <= POLE_LIMIT && h < TO_GLOBE_H) {
      flat.getView().animate({ center: fromLL([lon, lat]), resolution: heightToRes(h), duration: 600 });
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
      var elev = iconButton("⛰", T("표고 채우기 — LOLA 표고에서 점마다 높이를 읽는다 (달 기준구 1737.4 km)"),
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
  renderSets();
  renderCatalog();
  renderActive();
  applyStack();

  // 올리기 — 2D 의 불러오기와 같은 꼴. 몸만 달로 적는다
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
    data.set("body", "moon");
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

  // ══ 좌표·지명으로 이동 — 좌표 막대 ════════════════════════════════
  var gotoForm = $("goto-form"), gotoInput = $("goto-input"), results = $("search-results");
  var found = [], picked = -1, findTimer = null, findAsked = 0;
  function parseLatLon(text) {
    var m = /^\s*(-?\d+(?:\.\d+)?)\s*[, ]\s*(-?\d+(?:\.\d+)?)\s*$/.exec(text);
    if (!m) return null;
    var lat = +m[1], lon = +m[2];
    return Math.abs(lat) <= 90 && Math.abs(lon) <= 360 ? { lat: lat, lon: lon > 180 ? lon - 360 : lon } : null;
  }
  function renderFound() {
    if (!found.length) {
      results.innerHTML = '<li class="note">' + esc(T("찾은 것이 없다")) + "</li>";
    } else {
      results.innerHTML = found.map(function (p, i) {
        return '<li data-i="' + i + '"' + (i === picked ? ' class="on"' : "") + '><span class="kind">' + esc(p.kind) +
               '</span><span class="title">' + esc(p.name) + '</span><span class="sub">' +
               p.lat.toFixed(3) + ", " + p.lon.toFixed(3) + "</span></li>";
      }).join("") + '<li class="note src">IAU Gazetteer of Planetary Nomenclature · NASA Moon Trek</li>';
    }
    results.hidden = false;
    results.querySelectorAll("li[data-i]").forEach(function (li) {
      li.addEventListener("mousedown", function (e) { e.preventDefault(); choose(found[+li.dataset.i]); });
    });
  }
  function choose(place) {
    results.hidden = true;
    gotoInput.value = place.name;
    // 착륙지는 가까이, 크레이터·바다는 조금 멀리
    goTo(place.lon, place.lat, /Landing|Impact/.test(place.kind) ? 40000 : 200000);
  }
  gotoInput.addEventListener("input", function () {
    clearTimeout(findTimer);
    var q = gotoInput.value.trim();
    if (!q || parseLatLon(q)) { results.hidden = true; return; }
    findTimer = setTimeout(function () {
      var mine = ++findAsked;
      fetch(BASE + "moon/places/?q=" + encodeURIComponent(q)).then(function (r) { return r.json(); }).then(function (data) {
        if (mine !== findAsked) return;
        found = data.results || [];
        picked = found.length ? 0 : -1;
        renderFound();
      });
    }, 200);
  });
  gotoInput.addEventListener("keydown", function (e) {
    if (results.hidden || !found.length) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      picked = (picked + (e.key === "ArrowDown" ? 1 : found.length - 1)) % found.length;
      renderFound();
    } else if (e.key === "Escape") results.hidden = true;
  });
  gotoInput.addEventListener("blur", function () { setTimeout(function () { results.hidden = true; }, 150); });
  gotoForm.addEventListener("submit", function (e) {
    e.preventDefault();
    var ll = parseLatLon(gotoInput.value);
    if (ll) { results.hidden = true; goTo(ll.lon, ll.lat, 60000); return; }
    if (found.length) choose(found[Math.max(0, picked)]);
  });

  // ══ 자전축 — 구에서 방향을 잡는 헛선 (041) ═══════════════════════
  //
  // 구를 돌리고 기울이다 보면 어느 쪽이 북인지 놓친다. 달 고정 좌표의 Z 축이 곧 자전축이라, 극을
  // 뚫고 반지름의 0.45 배씩 밖으로 뻗은 선을 긋고 끝에 북극점·남극점을 적는다. 달 속을 지나는 토막은
  // 깊이 검사로 가려진다. 평면은 늘 북쪽이 위라 구에서만 보인다. 켜고 끈 것을 기억한다
  var AXIS_OUT = R * 1.45;
  var axisOn = saved("gsm.moon.axis", "on") !== "off";
  var axisEntities = [
    viewer.entities.add({
      polyline: { positions: [new Cesium.Cartesian3(0, 0, -AXIS_OUT), new Cesium.Cartesian3(0, 0, AXIS_OUT)],
                  arcType: Cesium.ArcType.NONE, width: 2,
                  material: new Cesium.PolylineDashMaterialProperty({ color: Cesium.Color.WHITE.withAlpha(0.8), dashLength: 18 }) },
    }),
  ].concat([[1, T("북극점")], [-1, T("남극점")]].map(function (end) {
    return viewer.entities.add({
      position: new Cesium.Cartesian3(0, 0, end[0] * AXIS_OUT),
      point: { pixelSize: 6, color: Cesium.Color.WHITE },
      label: { text: end[1], font: "600 12px system-ui, sans-serif", fillColor: Cesium.Color.WHITE,
               outlineColor: Cesium.Color.BLACK, outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE,
               pixelOffset: new Cesium.Cartesian2(0, end[0] > 0 ? -14 : 14) },
    });
  }));
  function applyAxis() {
    axisEntities.forEach(function (e) { e.show = axisOn; });
    $("tool-axis").classList.toggle("on", axisOn);
    $("tool-axis").setAttribute("aria-pressed", axisOn ? "true" : "false");
  }
  $("tool-axis").addEventListener("click", function () {
    axisOn = !axisOn;
    save("gsm.moon.axis", axisOn ? "on" : "off");
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
    show: false, position: Cesium.Cartesian3.fromDegrees(0, 0, 0, MOON),
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
    if (ll) markC.position = Cesium.Cartesian3.fromDegrees(ll[0], ll[1], 0, MOON);
  }

  // ══ 도구 — 점 찍기·거리·넓이·범위 (041) ═══════════════════════════
  //
  // 2D 의 그리기 도구와 같은 넷이다. **찍고 잰 것은 달 경위도로 한 곳에 들고, 구와 평면이 저마다
  // 그린다** — 켠 레이어·점묶음처럼 넘어가도 그대로 남는다. 그리던 것(끝내지 않은 선)만 넘어갈 때
  // 버리므로, 그리는 동안은 저절로 넘어가지 않는다(`drawing()`).
  //
  // 길이·넓이는 **달의 구면**(반지름 1737.4 km)으로 잰다. 평면의 가로는 위도만큼 늘어나 있어 평면
  // 좌표로 재면 틀린다. 넓이는 OpenLayers 의 `ol.sphere.getArea` 와 같은 식이고 반지름만 달의 것이다
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
  // 경도를 앞 꼭짓점에서 180° 안쪽으로 — 날짜변경선(±180°)을 건너도 선이 달을 한 바퀴 돌지 않게
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
      add({ position: Cesium.Cartesian3.fromDegrees(t.lon, t.lat, 0, MOON),
            point: { pixelSize: 10, color: WHITE, outlineColor: BLACK, outlineWidth: 2,
                     heightReference: Cesium.HeightReference.CLAMP_TO_GROUND, disableDepthTestDistance: NO_DEPTH },
            label: cLabel(String(t.no), -15) });
      drawSource.addFeature(new ol.Feature({ geometry: new ol.geom.Point(fromLL([t.lon, t.lat])), kind: "temp", no: t.no }));
    });
    ranges.forEach(function (r) {
      var ring = rangeRing(r), label = T("범위 {n}", { n: r.no });
      add({ polygon: { hierarchy: positions(ring), material: WHITE.withAlpha(0.1) } });
      add({ polyline: { positions: positions(ring), width: 2, clampToGround: true, material: Cesium.Color.fromCssColorString("#e4e4e4") } });
      add({ position: Cesium.Cartesian3.fromDegrees((r.w + r.e) / 2, (r.s + r.n) / 2, 0, MOON), label: cLabel(label) });
      drawSource.addFeature(new ol.Feature({ geometry: new ol.geom.Polygon([eqc(ring)]), kind: "range", label: label }));
    });
    if (measured) {
      var got = measureOf(measured), c = measured.coords;
      var line = measured.kind === "area" ? c.concat([c[0]]) : c;
      if (measured.kind === "area") add({ polygon: { hierarchy: positions(line), material: WHITE.withAlpha(0.14) } });
      add({ polyline: { positions: positions(line), width: 2.5, clampToGround: true, material: dash() } });
      var at = measured.kind === "area" ? centroid(c) : c[c.length - 1];
      add({ position: Cesium.Cartesian3.fromDegrees(at[0], at[1], 0, MOON), label: cLabel(got.text, measured.kind === "area" ? 0 : -16) });
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
    if (mode === "flat") return resToHeight(flat.getView().getResolution());
    var c = cameraLL();
    return c ? Math.min(c.h, 200000) : 200000;
  }
  function pixelOf(ll) {
    if (mode === "flat") return flat.getPixelFromCoordinate(fromLL(ll));
    var p = scene.cartesianToCanvasCoordinates(Cesium.Cartesian3.fromDegrees(ll[0], ll[1], 0, MOON));
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

  // 점묶음으로 저장 — 2D 와 같은 길(`pointsets/create/`)이고 몸만 달이다. 좌표는 ±180° 로 되돌려 싣는다
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
        name: name, color: "#f2f2f2", body: "moon", shapes: shapes,
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

  // ══ 처음 자리 — 기억한 것. 처음이면 앞면 한가운데를 멀리서 ═══════
  // 맨 끝에 둔다 — 평면으로 여는 길이 팝업·목록을 다 만든 뒤라야 한다
  try {
    var v = JSON.parse(saved("gsm.moon.view", "null"));
    if (v && isFinite(v.lon) && isFinite(v.lat) && isFinite(v.h)) {
      viewer.camera.setView({ destination: Cesium.Cartesian3.fromDegrees(v.lon, v.lat, v.h, MOON),
                              orientation: { heading: v.heading || 0, pitch: isFinite(v.pitch) ? v.pitch : -Math.PI / 2, roll: 0 } });
    } else flyGlobe(0, 0, 5200000);
    var f = JSON.parse(saved("gsm.moon.flat", "null"));
    if (saved("gsm.moon.mode", "globe") === "flat" && f && isFinite(f.lon) && isFinite(f.res)) {
      setMode("flat", { lon: f.lon, lat: f.lat, h: resToHeight(f.res) });
    }
  } catch (e) { flyGlobe(0, 0, 5200000); }
})();
