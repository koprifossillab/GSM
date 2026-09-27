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

  var map = new maplibregl.Map({
    container: "map3d",
    style: { version: 8, sources: sources, layers: layers },
    center: start.center, zoom: start.zoom, pitch: 60, bearing: -20, maxPitch: 80,
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: true }), "top-right");
  map.addControl(new maplibregl.ScaleControl(), "bottom-left");
  map.on("load", function () {
    map.setTerrain({ source: "dem", exaggeration: 1.5 });
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
})();
