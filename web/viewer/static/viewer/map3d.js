/* 대돌여지도 3D — 실험 (devlog 015).
 *
 * VWorld 3D 엔진이 아니라 **MapLibre + 공개 표고 타일**로 짓는다. VWorld 3D 는
 * 지형을 받아 오는 창구(XDServer `Layer=dem`)가 닫혀 있다(004, 2026-09-27 에도).
 * 표고는 AWS Terrain Tiles(Terrarium 인코딩, 열쇠 없음)이고, 지질도는 2D 와
 * 같은 서버 중계(`wms/`)를 탄다 — 인증키도 캐시도 그대로다.
 */
(function () {
  "use strict";

  var BASE = location.pathname.replace(/3d\/?$/, "");
  var vworldKey = JSON.parse(document.getElementById("vworld-key").textContent || '""');

  // 영어판 — 2D(`map.js`)와 같은 꼴이다. 실험 화면이 본 화면의 속을 끌어다 쓰지 않게 따로 둔다
  var LANG = document.documentElement.lang === "en" ? "en" : "ko";
  var I18N = JSON.parse((document.getElementById("i18n-data") || {}).textContent || "{}");
  function T(text, vars) {
    var out = (LANG === "en" && I18N[text]) || text;
    if (vars) out = out.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; });
    return out;
  }
  var DEM = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png";

  function wmsTiles(layer) {
    return [BASE + "wms/?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&FORMAT=image/png" +
            "&TRANSPARENT=true&STYLES=&CRS=EPSG:3857&WIDTH=512&HEIGHT=512" +
            "&LAYERS=" + encodeURIComponent(layer) + "&BBOX={bbox-epsg-3857}"];
  }

  /** 2D 에서 보던 자리. 같은 브라우저 저장소를 읽는다. 없으면 설악산. */
  function startView() {
    var q = new URLSearchParams(location.search);
    if (q.get("lat") && q.get("lon")) {
      return { center: [+q.get("lon"), +q.get("lat")], zoom: +(q.get("z") || 12) };
    }
    try {
      var v = JSON.parse(localStorage.getItem("gsm.view") || "null");
      if (v && isFinite(v.lon)) return { center: [v.lon, v.lat], zoom: Math.max(8, v.zoom) };
    } catch (e) { /* 사생활 모드 */ }
    return { center: [128.465, 38.119], zoom: 12 };
  }

  var start = startView();
  var select = document.getElementById("layer3d");
  select.value = "L_250K_Geology_Map";

  var sources = {
    dem: { type: "raster-dem", tiles: [DEM], encoding: "terrarium", tileSize: 256, maxzoom: 15,
           attribution: "Terrain: Mapzen/AWS Terrain Tiles" },
    shade: { type: "raster-dem", tiles: [DEM], encoding: "terrarium", tileSize: 256, maxzoom: 15 },
    kigam: { type: "raster", tiles: wmsTiles(select.value), tileSize: 512,
             attribution: "© 한국지질자원연구원" },
  };
  var layers = [{ id: "bg", type: "background", paint: { "background-color": "#e8e0d2" } }];
  if (vworldKey) {
    sources.base = { type: "raster", tileSize: 256, maxzoom: 19, attribution: "© VWorld",
      tiles: ["https://api.vworld.kr/req/wmts/1.0.0/" + encodeURIComponent(vworldKey) + "/white/{z}/{y}/{x}.png"] };
    layers.push({ id: "base", type: "raster", source: "base" });
  }
  layers.push({ id: "shade", type: "hillshade", source: "shade",
                paint: { "hillshade-exaggeration": 0.5, "hillshade-shadow-color": "#3f2712" } });
  layers.push({ id: "kigam", type: "raster", source: "kigam", paint: { "raster-opacity": 0.7 } });

  // 이름표의 글꼴 조각 — 로마자·숫자(0–511)만 담았다(`vendor/maplibre/glyphs/`, OFL).
  // 한글·한자는 조각 없이 브라우저 글꼴이 그린다(`localIdeographFontFamily`). P02 §7
  var GLYPHS = JSON.parse((document.getElementById("glyphs-url") || {}).textContent || '""');

  var map = new maplibregl.Map({
    container: "map3d",
    style: { version: 8, sources: sources, layers: layers,
             glyphs: GLYPHS ? location.origin + GLYPHS + "{fontstack}/{range}.pbf" : undefined },
    localIdeographFontFamily: "'Noto Sans KR', 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif",
    center: start.center, zoom: start.zoom, pitch: 60, bearing: -20, maxPitch: 80,
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new maplibregl.ScaleControl(), "bottom-left");
  map.on("load", function () {
    map.setTerrain({ source: "dem", exaggeration: 1.5 });
    renderPointSets();
    window.__gsm3dReady = true;
  });
  window.__gsm3d = map;

  select.addEventListener("change", function () {
    map.getSource("kigam").setTiles(wmsTiles(select.value));
  });
  document.getElementById("opacity3d").addEventListener("input", function () {
    map.setPaintProperty("kigam", "raster-opacity", this.value / 100);
    document.getElementById("op-num").textContent = this.value + "%";
  });
  document.getElementById("exag3d").addEventListener("input", function () {
    var x = this.value / 10;
    map.setTerrain({ source: "dem", exaggeration: x });
    document.getElementById("ex-num").textContent = "×" + x.toFixed(1);
  });
  document.getElementById("shade3d").addEventListener("change", function () {
    map.setLayoutProperty("shade", "visibility", this.checked ? "visible" : "none");
  });
  // 2D 로 돌아갈 때 지금 자리를 가지고 간다
  map.on("moveend", function () {
    var c = map.getCenter();
    try {
      localStorage.setItem("gsm.view", JSON.stringify({ lon: +c.lng.toFixed(5), lat: +c.lat.toFixed(5),
                                                        zoom: +map.getZoom().toFixed(2) }));
    } catch (e) { /* 사생활 모드 */ }
  });

  // ── 내 자료(점묶음) — P02 ────────────────────────────────────────
  //
  // 서버의 `pointsets/<번호>/geojson/` 을 그대로 얹는다. 점은 둥근 점으로 지형 위에
  // 앉히고(세우지 않는다), 선·면은 지형 표면에 입힌다. 켜고 끈 것은 2D 와 같은 열쇠
  // (`gsm.pointsets.off`)에 둔다. **켠 것만 받는다** — 끈 점묶음은 소스도 만들지 않는다.

  var pointsets = JSON.parse((document.getElementById("pointset-data") || {}).textContent || "[]");
  var PS_OFF_KEY = "gsm.pointsets.off";
  //: 켠 점이 이보다 많으면 패널에 한 줄 띄운다. 막지는 않는다
  var MANY_POINTS = 20000;
  var loaded = {};            // 번호 → 받은 GeoJSON (범위 맞추기에 쓴다)

  function offIds() {
    try { return JSON.parse(localStorage.getItem(PS_OFF_KEY) || "[]") || []; } catch (e) { return []; }
  }
  function setOff(id, off) {
    var ids = offIds().filter(function (x) { return x !== id; });
    if (off) ids.push(id);
    try { localStorage.setItem(PS_OFF_KEY, JSON.stringify(ids)); } catch (e) { /* 사생활 모드 */ }
  }
  function isOn(ps) { return offIds().indexOf(ps.id) < 0; }

  //: 이름표를 다는 줌 — 2D 의 `LABEL_MIN_ZOOM` 과 같다. 멀리서는 글자가 점을 덮는다
  var LABEL_MIN_ZOOM = 11;

  function layerIds(ps) {
    var p = "ps-" + ps.id + "-";
    var ids = [p + "fill", p + "edge", p + "line", p + "point"];
    return GLYPHS ? ids.concat([p + "label", p + "lname"]) : ids;
  }

  function addPointSet(ps) {
    var id = "ps-" + ps.id;
    if (map.getSource(id)) {
      layerIds(ps).forEach(function (l) { map.setLayoutProperty(l, "visibility", "visible"); });
      return;
    }
    var url = BASE + "pointsets/" + ps.id + "/geojson/";
    map.addSource(id, { type: "geojson", data: url });
    fetch(url).then(function (r) { return r.json(); }).then(function (d) { loaded[ps.id] = d; })
      .catch(function () { /* 범위 맞추기만 못 한다 */ });
    var polygon = ["match", ["geometry-type"], ["Polygon", "MultiPolygon"], true, false];
    var line = ["match", ["geometry-type"], ["LineString", "MultiLineString"], true, false];
    map.addLayer({ id: id + "-fill", type: "fill", source: id, filter: polygon,
                   paint: { "fill-color": ps.color, "fill-opacity": 0.25 } });
    map.addLayer({ id: id + "-edge", type: "line", source: id, filter: polygon,
                   paint: { "line-color": ps.color, "line-width": 2 } });
    map.addLayer({ id: id + "-line", type: "line", source: id, filter: line,
                   layout: { "line-join": "round", "line-cap": "round" },
                   paint: { "line-color": ps.color, "line-width": 3 } });
    // 2D 의 점과 같게 — 점묶음 색, 흰 테 1.5 px. 늘 정면을 본다(`viewport`)
    map.addLayer({ id: id + "-point", type: "circle", source: id,
                   filter: ["==", ["geometry-type"], "Point"],
                   paint: { "circle-radius": 5, "circle-color": ps.color,
                            "circle-stroke-color": "#fff", "circle-stroke-width": 1.5,
                            "circle-pitch-alignment": "viewport" } });
    if (!GLYPHS) return;
    // 이름표 — 점·면은 곁에, 선은 선을 따라. 2D 와 같은 먹색에 흰 테
    var text = { "text-color": "#1f1409", "text-halo-color": "#ffffff", "text-halo-width": 1.5 };
    map.addLayer({ id: id + "-label", type: "symbol", source: id, minzoom: LABEL_MIN_ZOOM,
                   filter: ["all", ["has", "이름표"], ["!", line]],
                   layout: { "text-field": ["to-string", ["get", "이름표"]], "text-font": ["Noto Sans Regular"],
                             "text-size": 12, "text-anchor": "left", "text-offset": [0.8, 0],
                             "text-optional": true },
                   paint: text });
    map.addLayer({ id: id + "-lname", type: "symbol", source: id, minzoom: LABEL_MIN_ZOOM,
                   filter: ["all", ["has", "이름표"], line],
                   layout: { "text-field": ["to-string", ["get", "이름표"]], "text-font": ["Noto Sans Regular"],
                             "text-size": 12, "symbol-placement": "line" },
                   paint: text });
  }

  function hidePointSet(ps) {
    if (!map.getSource("ps-" + ps.id)) return;
    layerIds(ps).forEach(function (l) { map.setLayoutProperty(l, "visibility", "none"); });
  }

  /** 받은 GeoJSON 의 위경도 범위 `[[서, 남], [동, 북]]`. 비었으면 null. */
  function boundsOf(data) {
    var b = [Infinity, Infinity, -Infinity, -Infinity];
    function walk(c) {
      if (typeof c[0] === "number") {
        b[0] = Math.min(b[0], c[0]); b[1] = Math.min(b[1], c[1]);
        b[2] = Math.max(b[2], c[0]); b[3] = Math.max(b[3], c[1]);
      } else c.forEach(walk);
    }
    (data.features || []).forEach(function (f) { if (f.geometry) walk(f.geometry.coordinates); });
    return isFinite(b[0]) ? [[b[0], b[1]], [b[2], b[3]]] : null;
  }

  function fitPointSet(ps) {
    var go = function (d) {
      var b = boundsOf(d);
      if (b) map.fitBounds(b, { padding: 60, maxZoom: 14, duration: 600 });
    };
    if (loaded[ps.id]) return go(loaded[ps.id]);
    fetch(BASE + "pointsets/" + ps.id + "/geojson/").then(function (r) { return r.json(); })
      .then(function (d) { loaded[ps.id] = d; go(d); });
  }

  function countText(ps) {
    var bits = [T("{n}점", { n: ps.count || 0 })];
    if (ps.lines) bits.push(T("선 {n}", { n: ps.lines }));
    if (ps.polygons) bits.push(T("면 {n}", { n: ps.polygons }));
    if (!ps.count && (ps.lines || ps.polygons)) bits.shift();
    return bits.join(" · ");
  }

  function renderPointSets() {
    var host = document.getElementById("ps3d");
    if (!host) return;
    host.innerHTML = "";
    if (!pointsets.length) {
      var empty = document.createElement("li");
      empty.className = "empty";
      empty.textContent = T("올린 점묶음이 없다 — 2D 에서 올린다");
      host.appendChild(empty);
    }
    var shown = 0;
    pointsets.forEach(function (ps) {
      var on = isOn(ps);
      if (on) { addPointSet(ps); shown += ps.count || 0; } else hidePointSet(ps);
      var li = document.createElement("li");
      var box = document.createElement("input");
      box.type = "checkbox";
      box.checked = on;
      box.addEventListener("change", function () {
        setOff(ps.id, !box.checked);
        renderPointSets();
      });
      var swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = ps.color;
      var name = document.createElement("span");
      name.className = "ps-name";
      name.textContent = ps.name;
      name.title = ps.name + " — " + countText(ps);
      var count = document.createElement("span");
      count.className = "ps-count";
      count.textContent = countText(ps);
      var fit = document.createElement("button");
      fit.type = "button";
      fit.textContent = "⊙";
      fit.title = T("이 자료로 범위를 맞춘다");
      fit.addEventListener("click", function () { fitPointSet(ps); });
      li.append(box, swatch, name, count, fit);
      host.appendChild(li);
    });
    var warn = document.getElementById("ps3d-warn");
    if (warn) {
      warn.hidden = shown <= MANY_POINTS;
      warn.textContent = T("켠 점이 {n}개다 — 지형과 함께 그리면 느릴 수 있다", { n: shown.toLocaleString() });
    }
  }

  // 2D 창에서 켜고 끄면 따라간다
  window.addEventListener("storage", function (e) {
    if (e.key === PS_OFF_KEY && map.isStyleLoaded()) renderPointSets();
  });

  // ── 누르면 속성 — 2D 팝업과 같은 꼴: 머리는 점묶음 이름, 밑에 이름표, 표는 딸린 속성

  function esc(text) {
    return String(text).replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function psLayers() {
    var ids = [];
    pointsets.forEach(function (ps) {
      if (map.getSource("ps-" + ps.id)) ids = ids.concat(layerIds(ps));
    });
    return ids;
  }

  map.on("click", function (e) {
    var layers = psLayers();
    if (!layers.length) return;
    var pad = 4;
    var hits = map.queryRenderedFeatures([[e.point.x - pad, e.point.y - pad], [e.point.x + pad, e.point.y + pad]],
                                         { layers: layers });
    if (!hits.length) return;
    var f = hits[0];
    var psId = +String(f.layer.id).split("-")[1];
    var ps = pointsets.filter(function (x) { return x.id === psId; })[0] || {};
    var props = f.properties || {};
    var html = '<div class="popup3d"><h3>' + esc(ps.name || T("내 자료")) + "</h3>";
    if (props["이름표"]) html += '<p class="label">' + esc(props["이름표"]) + "</p>";
    var rows = Object.keys(props).filter(function (k) { return k !== "이름표"; });
    if (rows.length) {
      html += "<table>" + rows.map(function (k) {
        return "<tr><th>" + esc(T(k)) + "</th><td>" + esc(props[k]) + "</td></tr>";
      }).join("") + "</table>";
    }
    html += "</div>";
    new maplibregl.Popup({ maxWidth: "320px" }).setLngLat(e.lngLat).setHTML(html).addTo(map);
  });
  map.on("mousemove", function (e) {
    var layers = psLayers();
    var hit = layers.length && map.queryRenderedFeatures(e.point, { layers: layers }).length;
    map.getCanvas().style.cursor = hit ? "pointer" : "";
  });
})();
