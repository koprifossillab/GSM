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
  // 줌 끝은 2026-09-29 에 한 장씩 받아 보았다 — WAC 는 8, LOLA 음영은 6 (7 은 404)
  var BASES = {
    wac: { url: TREK + "LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{z}/{y}/{x}.jpg",
           max: 8, credit: "LRO LROC WAC · NASA/GSFC/Arizona State University" },
    lola: { url: TREK + "LRO_LOLA_Shade_Global_256ppd_v06/1.0.0/default/default028mm/{z}/{y}/{x}.png",
            max: 6, credit: "LRO LOLA · NASA/GSFC" },
  };
  // 지질 레이어 목록 — 2D 의 카탈로그처럼 골라 켜면 "켠 지질 레이어" 로 올라온다(오버레이).
  // 레이어군을 더하면(원소·광물 …) 목록에 저절로 선다. 이름은 서버 `trek.LAYERS` 의 열쇠다
  var CATALOG = [
    { group: "달 지질 (USGS 1:500만, 2020)", layers: [
      { name: "units", title: "지질 단위", legend: true },
      { name: "contacts", title: "지질 경계" },
      { name: "linear", title: "선 구조 (능선·열구·단층)" },
    ] },
  ];
  var LAYER = {};
  CATALOG.forEach(function (g) { g.layers.forEach(function (l) { LAYER[l.name] = l; }); });
  var GEO_NAMES = Object.keys(LAYER);
  var GEO_MAX = 12;
  function geoUrl(name) { return BASE + "moon/tiles/" + name + "/{z}/{x}/{y}.png"; }
  var GEO_CREDIT = "Unified Geologic Map of the Moon 1:5M (Fortezzo et al., 2020, USGS) via NASA Moon Trek";

  // ── 켠 것 — 구와 평면이 함께 쓴다. 이 브라우저에 기억한다 ──
  var look = {
    base: saved("gsm.moon.base", "wac"),
    terrain: saved("gsm.moon.terrain", "on") !== "off",
    exag: +saved("gsm.moon.exag", "20"),
  };
  if (!BASES[look.base]) look.base = "wac";
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
  function cesiumBase(key) {
    var b = BASES[key];
    return new Cesium.ImageryLayer(new Cesium.UrlTemplateImageryProvider({
      url: b.url, tilingScheme: scheme(), maximumLevel: b.max, credit: b.credit,
    }));
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

  var viewer = new Cesium.Viewer("globe", {
    globe: new Cesium.Globe(MOON),
    baseLayer: cesiumBase(look.base),
    terrainProvider: look.terrain ? lolaTerrain : flatTerrain,
    // 달에는 대기가 없다. 지구 전용 단추(주소 찾기·지도 고르개·시간 막대)도 뺀다
    skyAtmosphere: false,
    baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false,
    navigationHelpButton: false, animation: false, timeline: false, fullscreenButton: false,
    infoBox: false, selectionIndicator: false,
  });
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
      credit: name === "units" ? GEO_CREDIT : undefined,
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
  function tileSource(template, maxZoom, attribution) {
    return new ol.source.TileImage({
      projection: EQC, tileGrid: grid(maxZoom), attributions: attribution, wrapX: true,
      tileUrlFunction: function (coord) {
        var z = coord[0], x = coord[1], y = coord[2], n = Math.pow(2, z + 1);
        if (y < 0 || y >= n / 2) return undefined;
        x = ((x % n) + n) % n;
        return template.replace("{z}", z).replace("{x}", x).replace("{y}", y);
      },
    });
  }
  var oBase = new ol.layer.Tile({ source: tileSource(BASES[look.base].url, BASES[look.base].max, BASES[look.base].credit) });
  var oGeo = {};
  GEO_NAMES.forEach(function (name) {
    oGeo[name] = new ol.layer.Tile({ source: tileSource(geoUrl(name), GEO_MAX, name === "units" ? GEO_CREDIT : undefined),
                                     visible: false });
  });
  var oPoints = new ol.layer.Group({ layers: [] });
  var flat = new ol.Map({
    target: "map",
    layers: [oBase].concat(GEO_NAMES.map(function (n) { return oGeo[n]; }), [oPoints]),
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
    if (next === "flat") {
      var c = at || cameraLL();
      if (!c) return;
      var view = flat.getView();
      view.setCenter(fromLL([c.lon, c.lat]));
      view.setResolution(Math.min(heightToRes(c.h), heightToRes(TO_GLOBE_H) * 0.9));
      view.setRotation(0);
      mode = "flat";
      wrap.className = "moon-flat";
      flat.updateSize();
    } else {
      var v = flat.getView(), ll = toLL(v.getCenter());
      flyGlobe(ll[0], ll[1], (at && at.h) || resToHeight(v.getResolution()));
      mode = "globe";
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
    if (autoFlat && straight && Math.abs(c.lat) <= POLE_LIMIT) setMode("flat", c);
  });
  flat.on("moveend", function () {
    if (mode !== "flat") return;
    var v = flat.getView(), ll = toLL(v.getCenter());
    save("gsm.moon.flat", JSON.stringify({ lon: +ll[0].toFixed(5), lat: +ll[1].toFixed(5), res: Math.round(v.getResolution()) }));
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
    layers.remove(layers.get(0), true);
    layers.add(cesiumBase(look.base), 0);
    var b = BASES[look.base];
    oBase.setSource(tileSource(b.url, b.max, b.credit));
  });

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
    active.unshift({ name: name, opacity: name === "units" ? 0.6 : 1 });
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
      src.textContent = "USGS · NASA Moon Trek";
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
  function closePopup() { popup.classList.remove("on"); ++asked; }
  $("popup-close").addEventListener("click", closePopup);
  function showPopup(html, pixel) {
    popupBody.innerHTML = html;
    popup.classList.add("on");
    var w = wrap.clientWidth, h = wrap.clientHeight;
    var pw = popup.offsetWidth, ph = popup.offsetHeight;
    var left = Math.min(Math.max(8, pixel[0] + 14), w - pw - 8);
    var top = Math.min(Math.max(8, pixel[1] - ph / 2), h - ph - 64);
    popup.style.left = left + "px";
    popup.style.top = Math.max(8, top) + "px";
  }
  function coordHead(ll) {
    return '<div class="popup-coord"><span class="k">' + esc(T("달 위경도")) + '</span><span class="v">' +
           ll[1].toFixed(5) + ", " + ll[0].toFixed(5) + "</span></div>";
  }
  function askUnit(ll, pixel) {
    var head = coordHead(ll);
    if (!isOn("units")) { showPopup(head, pixel); return; }
    var mine = ++asked;
    showPopup(head + '<p class="none">' + esc(T("읽는 중")) + "</p>", pixel);
    fetch(BASE + "moon/info/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (mine !== asked) return;
        if (data.error) throw new Error(data.error);
        if (!data.rows.length) { showPopup(head + '<p class="none">' + esc(T("여기에는 지질 단위가 없다")) + "</p>", pixel); return; }
        var sw = swatches[data.unit];
        showPopup(head + "<h3>" + esc(T("지질 단위")) + "</h3><table>" + data.rows.map(function (row, i) {
          var mark = i === 0 && sw ? '<img class="swatch-img" src="' + sw + '" alt="">' : "";
          return "<tr><th>" + esc(row[0]) + "</th><td>" + mark + esc(row[1]) + "</td></tr>";
        }).join("") + "</table>", pixel);
      })
      .catch(function () {
        if (mine === asked) showPopup(head + '<p class="none">' + esc(T("속성을 받지 못했다")) + "</p>", pixel);
      });
  }
  // 점묶음의 점·모양 — 2D 의 팝업과 같이 딸린 속성을 받은 차례 그대로
  function showFeature(props, ps, ll, pixel) {
    ++asked;
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

  // ══ 범례 — 오른쪽 아래, 펼쳐 둔다. 시대별로 묶는다 ═══════════════
  var swatches = {};
  var dock = $("legend-dock");
  dock.open = saved("gsm.moon.legend", "open") !== "closed";
  dock.addEventListener("toggle", function () { save("gsm.moon.legend", dock.open ? "open" : "closed"); });
  function syncLegend() { dock.hidden = !isOn("units"); }
  fetch(BASE + "moon/legend/").then(function (r) { return r.json(); }).then(function (data) {
    // 상류의 범례 차례는 시대가 섞여 있다(에라토스테네스기 바다 `Em` 이 임브리움기 크레이터 뒤에 온다).
    // 처음 나온 차례대로 시대를 모아 한 번씩만 머리를 단다
    var list = $("legend-list"), html = "", ages = [], byAge = {};
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
    list.innerHTML = html || '<li class="empty">' + esc(T("범례를 받지 못했다")) + "</li>";
  }).catch(function () {
    $("legend-list").innerHTML = '<li class="empty">' + esc(T("범례를 받지 못했다")) + "</li>";
  });

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
