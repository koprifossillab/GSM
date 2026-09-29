/* 대돌여지도 · 달 (devlog 036, P05).
 *
 * 둥근 달에 들어가서 본다. 평면(OpenLayers)은 달의 극을 띠로 늘이고, MapLibre 의 구는
 * 메르카토르 타일이라 남위 85° 안쪽이 빈다 — 달에서 가장 보고 싶은 자리다. 그래서 달 타원체를
 * 가진 **CesiumJS** 로 그린다. 격자는 모두 경위도다 — Cesium 의 `GeographicTilingScheme`
 * (줌 0 이 가로 2 장·세로 1 장)과 Trek 의 격자가 같다.
 *
 * - 영상 배경(LRO WAC·LOLA 음영)은 브라우저가 Trek 을 곧장 부른다 (EOX 와 같다)
 * - 지질도·표고·속성·범례·지명은 서버의 문(`trek.py`)을 거친다 — 캐시와 호출 세기가 거기 있다
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

  var MOON = Cesium.Ellipsoid.MOON;
  // 타원체를 넘기지 않는 곳(카메라 기본 범위·좌표 풀이)이 지구로 여기지 않게 기본값부터 바꾼다
  Cesium.Ellipsoid.default = MOON;
  function scheme() { return new Cesium.GeographicTilingScheme({ ellipsoid: MOON }); }

  // ── 영상 배경 — 브라우저가 Trek 을 곧장 ──
  // 줌 끝은 2026-09-29 에 한 장씩 받아 보았다 — WAC 는 8, LOLA 음영은 6 (7 은 404)
  var TREK = "https://trek.nasa.gov/tiles/Moon/EQ/";
  var BASES = {
    wac: { url: TREK + "LRO_WAC_Mosaic_Global_303ppd_v02/1.0.0/default/default028mm/{z}/{y}/{x}.jpg",
           max: 8, credit: "LRO LROC WAC · NASA/GSFC/Arizona State University" },
    lola: { url: TREK + "LRO_LOLA_Shade_Global_256ppd_v06/1.0.0/default/default028mm/{z}/{y}/{x}.png",
            max: 6, credit: "LRO LOLA · NASA/GSFC" },
  };
  function baseLayer(key) {
    var b = BASES[key] || BASES.wac;
    return new Cesium.ImageryLayer(new Cesium.UrlTemplateImageryProvider({
      url: b.url, tilingScheme: scheme(), maximumLevel: b.max, credit: b.credit,
    }));
  }

  // ── 지형 — LOLA 표고, 서버가 65×65 Terrarium 으로 옮겨 준다 ──
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

  var terrainOn = saved("gsm.moon.terrain", "on") !== "off";
  var viewer = new Cesium.Viewer("moon", {
    globe: new Cesium.Globe(MOON),
    baseLayer: baseLayer(saved("gsm.moon.base", "wac")),
    terrainProvider: terrainOn ? lolaTerrain : flatTerrain,
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
  window.__gsmMoon = viewer;

  // ── 자리 — 기억한다. 처음이면 앞면 한가운데를 멀리서 ──
  function startView() {
    try {
      var v = JSON.parse(saved("gsm.moon.view", "null"));
      if (v && isFinite(v.lon) && isFinite(v.lat) && isFinite(v.h)) {
        return { destination: Cesium.Cartesian3.fromDegrees(v.lon, v.lat, v.h, MOON),
                 orientation: { heading: v.heading || 0, pitch: isFinite(v.pitch) ? v.pitch : -Math.PI / 2, roll: 0 } };
      }
    } catch (e) { /* 깨진 값 */ }
    return { destination: Cesium.Cartesian3.fromDegrees(0, 0, 5200000, MOON) };
  }
  viewer.camera.setView(startView());
  viewer.camera.moveEnd.addEventListener(function () {
    var c = MOON.cartesianToCartographic(viewer.camera.positionWC);
    if (!c) return;
    save("gsm.moon.view", JSON.stringify({
      lon: +Cesium.Math.toDegrees(c.longitude).toFixed(5), lat: +Cesium.Math.toDegrees(c.latitude).toFixed(5),
      h: Math.round(c.height), heading: +viewer.camera.heading.toFixed(4), pitch: +viewer.camera.pitch.toFixed(4),
    }));
  });

  // ── 배경 ──
  document.querySelectorAll('input[name="moon-base"]').forEach(function (input) {
    input.checked = input.value === saved("gsm.moon.base", "wac");
    input.addEventListener("change", function () {
      var layers = viewer.imageryLayers;
      layers.remove(layers.get(0), true);
      layers.add(baseLayer(input.value), 0);
      save("gsm.moon.base", input.value);
    });
  });

  // ── 지질도 — 서버의 문을 거친다 ──
  var CREDIT = "Unified Geologic Map of the Moon 1:5M (Fortezzo et al., 2020, USGS) via NASA Moon Trek";
  var GEO = {};
  ["units", "contacts", "linear"].forEach(function (name) {
    var layer = viewer.imageryLayers.addImageryProvider(new Cesium.UrlTemplateImageryProvider({
      url: BASE + "moon/tiles/" + name + "/{z}/{x}/{y}.png",
      tilingScheme: scheme(), maximumLevel: 12, hasAlphaChannel: true,
      credit: name === "units" ? CREDIT : undefined,
    }));
    var box = document.getElementById("moon-geo-" + name);
    layer.show = box.checked = saved("gsm.moon.geo." + name, name === "units" ? "on" : "off") === "on";
    box.addEventListener("change", function () {
      layer.show = box.checked;
      save("gsm.moon.geo." + name, box.checked ? "on" : "off");
    });
    GEO[name] = layer;
  });
  var opacity = document.getElementById("moon-op");
  opacity.value = saved("gsm.moon.opacity", "60");
  function applyOpacity() {
    GEO.units.alpha = opacity.value / 100;
    document.getElementById("moon-op-num").textContent = opacity.value + "%";
    save("gsm.moon.opacity", opacity.value);
  }
  opacity.addEventListener("input", applyOpacity);
  applyOpacity();

  // ── 지형 ──
  var terrainBox = document.getElementById("moon-terrain");
  var exag = document.getElementById("moon-exag");
  terrainBox.checked = terrainOn;
  terrainBox.addEventListener("change", function () {
    scene.terrainProvider = terrainBox.checked ? lolaTerrain : flatTerrain;
    exag.disabled = !terrainBox.checked;
    save("gsm.moon.terrain", terrainBox.checked ? "on" : "off");
  });
  exag.disabled = !terrainOn;
  exag.value = saved("gsm.moon.exag", "20");
  function applyExag() {
    scene.verticalExaggeration = exag.value / 10;
    document.getElementById("moon-exag-num").textContent = "×" + (exag.value / 10).toFixed(1);
    save("gsm.moon.exag", exag.value);
  }
  exag.addEventListener("input", applyExag);
  applyExag();

  // ── 좌표 ──
  function lonLatAt(position) {
    var ray = viewer.camera.getPickRay(position);
    var cartesian = ray && scene.globe.pick(ray, scene);
    if (!cartesian) cartesian = viewer.camera.pickEllipsoid(position, MOON);
    if (!cartesian) return null;
    var c = MOON.cartesianToCartographic(cartesian);
    return [Cesium.Math.toDegrees(c.longitude), Cesium.Math.toDegrees(c.latitude)];
  }
  function fmt(ll) {
    return T("달 위도 {lat}° · 경도 {lon}°", { lat: ll[1].toFixed(3), lon: ll[0].toFixed(3) });
  }
  var readout = document.getElementById("readout");
  var handler = new Cesium.ScreenSpaceEventHandler(scene.canvas);
  handler.setInputAction(function (movement) {
    var ll = lonLatAt(movement.endPosition);
    readout.hidden = !ll;
    if (ll) readout.textContent = fmt(ll);
  }, Cesium.ScreenSpaceEventType.MOUSE_MOVE);

  // ── 속성 ──
  var attrs = document.getElementById("attrs");
  var asked = 0;
  function showAttrs(html) {
    attrs.innerHTML = '<button type="button" class="close" aria-label="' + esc(T("닫기")) + '">×</button>' + html;
    attrs.hidden = false;
    attrs.querySelector(".close").addEventListener("click", function () { attrs.hidden = true; });
  }
  handler.setInputAction(function (click) {
    var ll = lonLatAt(click.position);
    if (!ll) return;
    var head = "<h3>" + esc(fmt(ll)) + "</h3>";
    if (!GEO.units.show) { showAttrs(head); return; }
    var mine = ++asked;
    showAttrs(head + "<p>" + esc(T("읽는 중")) + "</p>");
    fetch(BASE + "moon/info/?lon=" + ll[0].toFixed(4) + "&lat=" + ll[1].toFixed(4))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (mine !== asked) return;
        if (data.error) throw new Error(data.error);
        if (!data.rows.length) { showAttrs(head + "<p>" + esc(T("여기에는 지질 단위가 없다")) + "</p>"); return; }
        var sw = swatches[data.unit];
        showAttrs(head + "<table>" + data.rows.map(function (row, i) {
          var mark = i === 0 && sw ? '<img class="swatch" src="' + sw + '" alt="">' : "";
          return "<tr><th>" + esc(row[0]) + "</th><td>" + mark + esc(row[1]) + "</td></tr>";
        }).join("") + "</table>");
      })
      .catch(function () {
        if (mine === asked) showAttrs(head + "<p>" + esc(T("속성을 받지 못했다")) + "</p>");
      });
  }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

  // ── 범례 ──
  // 상류가 "Copernican Crater (Cc)" 처럼 이름 끝에 기호를 단다. 기호로 팝업의 색 조각도 찾는다
  var swatches = {};
  // 팝업의 색 조각에도 쓰므로 처음에 한 번 받는다 — 서버가 캐시에서 준다
  (function loadLegend() {
    var list = document.getElementById("moon-legend-list");
    fetch(BASE + "moon/legend/").then(function (r) { return r.json(); }).then(function (data) {
      list.innerHTML = (data.items || []).map(function (item) {
        var m = /\(([^)]+)\)\s*$/.exec(item.label);
        if (m) swatches[m[1]] = item.image;
        return '<li><img src="' + esc(item.image) + '" alt="">' + esc(item.label) + "</li>";
      }).join("") || "<li>" + esc(T("범례를 받지 못했다")) + "</li>";
    }).catch(function () {
      list.innerHTML = "<li>" + esc(T("범례를 받지 못했다")) + "</li>";
    });
  })();

  // ── 지명 찾기 ──
  var findInput = document.getElementById("moon-find");
  var findList = document.getElementById("moon-find-list");
  var findTimer = null, findAsked = 0;
  findInput.addEventListener("input", function () {
    clearTimeout(findTimer);
    findTimer = setTimeout(find, 200);
  });
  findInput.addEventListener("keydown", function (e) {
    if (e.key === "Enter") {
      var first = findList.querySelector("button");
      if (first) first.click();
    }
  });
  function find() {
    var q = findInput.value.trim();
    if (!q) { findList.innerHTML = ""; return; }
    var mine = ++findAsked;
    fetch(BASE + "moon/places/?q=" + encodeURIComponent(q)).then(function (r) { return r.json(); }).then(function (data) {
      if (mine !== findAsked) return;
      var rows = data.results || [];
      findList.innerHTML = rows.length ? rows.map(function (p, i) {
        return '<li><button type="button" data-i="' + i + '">' + esc(p.name) +
               ' <span>' + esc(p.kind) + "</span></button></li>";
      }).join("") : '<li class="none">' + esc(T("찾은 것이 없다")) + "</li>";
      findList.querySelectorAll("button").forEach(function (button) {
        button.addEventListener("click", function () { flyTo(rows[+button.dataset.i]); });
      });
    });
  }
  function flyTo(place) {
    findList.innerHTML = "";
    findInput.value = place.name;
    // 착륙지는 가까이, 크레이터·바다는 조금 멀리
    var h = /Landing|Impact/.test(place.kind) ? 60000 : 400000;
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(place.lon, place.lat, h, MOON),
                          orientation: { heading: 0, pitch: -Math.PI / 2, roll: 0 }, duration: 2 });
  }

  document.getElementById("moon-home").addEventListener("click", function () {
    viewer.camera.flyTo({ destination: Cesium.Cartesian3.fromDegrees(0, 0, 5200000, MOON),
                          orientation: { heading: 0, pitch: -Math.PI / 2, roll: 0 }, duration: 1.5 });
  });
})();
