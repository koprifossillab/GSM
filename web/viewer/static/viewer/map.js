/* 대돌여지도 — 지도 화면.
 *
 * 서버가 아는 것과 여기가 아는 것을 갈라 둔다.
 *   - 인증키는 여기 오지 않는다. 타일은 언제나 ./wms/ 를 부른다
 *   - 좌표 표시는 여기서 한다. 마우스가 움직일 때마다 서버를 부를 수 없다
 *   - 좌표 입력칸이 받는 도분초 해석은 서버에 둔다 (./coords/parse/).
 *     까다로운 쪽이라 파이썬에서 시험하는 편이 낫다
 */
(function () {
  "use strict";

  var BASE = location.pathname.replace(/\/+$/, "") + "/";
  var vworldKey = JSON.parse(document.getElementById("vworld-key").textContent || '""');
  var catalog = JSON.parse(document.getElementById("catalog-data").textContent || "[]");
  var pointsets = JSON.parse(document.getElementById("pointset-data").textContent || "[]");

  //: 레이어를 켤 때의 투명도. 배경지도를 깔고 보는 것이 예사이므로
  //  처음부터 밑이 비치게 둔다. 100% 로 두면 배경을 덮어서, 사람이
  //  슬라이더를 찾아 내려야 배경이 보인다.
  var DEFAULT_OPACITY = 0.5;

  //: 5만 지질도 도폭 하나가 덮는 범위. 경도 15분 × 위도 10분이다.
  //  좌표를 찍어 이동할 때 이만큼이 화면에 들어오게 맞춘다 — "도폭 한 장"
  //  이 이 축척을 쓰는 사람의 눈금이라, 줌 단계 숫자보다 뜻이 분명하다.
  var SHEET_LON = 15 / 60;
  var SHEET_LAT = 10 / 60;

  var map, popupOverlay, pointLayerGroup;
  var tempSource, tempLayer, measureSource, measureLayer, foundSource, foundLayer;
  var mode = "info", drawInteraction = null, tempSeq = 0;
  var active = [];        // 켠 레이어. 앞이 위다 (화면에서 앞에 그려진다)
  var byName = {};        // 레이어명 -> 카탈로그 행
  var pointLayers = {};   // 점묶음 id -> ol 레이어
  var useDms = false;

  catalog.forEach(function (group) {
    group.layers.forEach(function (layer) { byName[layer.name] = layer; });
  });

  // ── 지도 ────────────────────────────────────────────────────────

  function wmsSource(name) {
    return new ol.source.TileWMS({
      url: BASE + "wms",
      params: { LAYERS: name, TILED: true, FORMAT: "image/png", TRANSPARENT: true },
      transition: 0,
      // 상류 부하를 줄인다. 타일 하나가 작을수록 요청이 는다.
      tileGrid: ol.tilegrid.createXYZ({ tileSize: 512 }),
    });
  }

  /** 배경지도.
   *
   *  **기본은 "없음" 이다.** 처음에는 OpenStreetMap 을 깔았는데, 기관 망의
   *  바깥 IP 가 OSM 정책 위반으로 막혀 있어 타일 자리마다
   *  `403 Access blocked` 그림이 깔렸다 (2026-09-23).
   *
   *  우리 서버로 중계하면 화면은 살지만 그것이야말로 OSM 이 막는 행동이고,
   *  이번엔 서버 IP 가 막힌다. 그래서 중계하지 않고 **고르게** 했다.
   *
   *  배경이 없어도 읽힌다 — 지질도 자체가 지명·행정경계·수계를 그려 준다.
   *  종이 지질도가 그렇게 생겼다.
   */
  // OpenStreetMap 은 고르개에서 뺐다. 기관 망의 바깥 IP 가 OSM 정책 위반으로
  // 막혀 있어(devlog 003) 고를 수 있게 두면 `403 Access blocked` 타일만
  // 깔린다. 고쳐지지 않는 것을 목록에 두는 것은 고르개가 아니라 함정이다.
  var BASEMAPS = {
    none: { title: "없음 (바탕만)", make: null },
  };

  // VWorld 는 열쇠가 있을 때만 고르개에 오른다.
  //
  // **브라우저가 곧장 부른다.** 상류 지질도와 다른 점이다 — VWorld 는
  // 브라우저가 직접 부르는 것을 전제로 하고 열쇠에 도메인 제한을 걸어
  // 지킨다. 서버가 중계하면 그 제한이 뜻을 잃고 타일을 전부 우리가 짊어진다.
  //
  // WMTS 의 자리 차례가 **z/y/x** 다. z/x/y 로 적으면 엉뚱한 곳이 그려진다.
  if (vworldKey) {
    BASEMAPS.vworld = {
      title: "VWorld 배경지도",
      note: "국토지리정보원",
      make: function () {
        return new ol.layer.Tile({
          opacity: 0.85,
          source: new ol.source.XYZ({
            url: "https://api.vworld.kr/req/wmts/1.0.0/" + encodeURIComponent(vworldKey)
                 + "/Base/{z}/{y}/{x}.png",
            crossOrigin: "anonymous",
            maxZoom: 19,
            attributions: '© <a href="https://www.vworld.kr/" target="_blank" rel="noopener">VWorld</a>',
          }),
        });
      },
    };
    // 위성 사진과 지명은 **따로 오는 레이어다**(`Satellite`·`Hybrid`).
    // 그래서 지명만 끌 수 있다 — 지질 경계를 볼 때 글자가 방해가 된다.
    // 일반 배경지도(`Base`)는 지명이 그림에 박혀 있어 끄지 못한다.
    BASEMAPS.vworld_hybrid = {
      title: "VWorld 위성",
      note: "국토지리정보원. 지명을 끄고 켤 수 있다",
      labels: true,
      make: function () {
        var labels = new ol.layer.Tile({
          source: new ol.source.XYZ({
            url: "https://api.vworld.kr/req/wmts/1.0.0/" + encodeURIComponent(vworldKey)
                 + "/Hybrid/{z}/{y}/{x}.png",
            crossOrigin: "anonymous", maxZoom: 19,
          }),
          visible: labelsOn(),
        });
        labels.set("gsmLabels", true);
        return new ol.layer.Group({ layers: [
          new ol.layer.Tile({ source: new ol.source.XYZ({
            url: "https://api.vworld.kr/req/wmts/1.0.0/" + encodeURIComponent(vworldKey)
                 + "/Satellite/{z}/{y}/{x}.jpeg",
            crossOrigin: "anonymous", maxZoom: 19,
            attributions: '© <a href="https://www.vworld.kr/" target="_blank" rel="noopener">VWorld</a>',
          })}),
          labels,
        ]});
      },
    };
  }
  var baseLayer = null;

  function setBasemap(key) {
    if (baseLayer) {
      map.removeLayer(baseLayer);
      baseLayer = null;
    }
    var spec = BASEMAPS[key];
    if (spec && spec.make) {
      baseLayer = spec.make();
      baseLayer.setZIndex(0);
      map.getLayers().insertAt(0, baseLayer);
    }
    try { localStorage.setItem("gsm.basemap", key); } catch (e) { /* 사생활 모드 */ }
  }

  function labelsOn() {
    try {
      return localStorage.getItem("gsm.basemapLabels") !== "0";
    } catch (e) { return true; }
  }

  /** 배경지도의 지명 겹을 켜고 끈다. 겹이 없는 배경이면 아무 일도 안 한다. */
  function setLabels(on) {
    try { localStorage.setItem("gsm.basemapLabels", on ? "1" : "0"); } catch (e) { /* 사생활 모드 */ }
    if (!baseLayer || !baseLayer.getLayers) return;
    baseLayer.getLayers().forEach(function (l) {
      if (l.get("gsmLabels")) l.setVisible(on);
    });
  }

  function savedBasemap() {
    try {
      var key = localStorage.getItem("gsm.basemap");
      if (key && BASEMAPS[key]) return key;
    } catch (e) { /* 사생활 모드 */ }
    // 열쇠가 있으면 위성+지명으로 시작한다. 지질을 지형·시설과 견주어
    // 보는 것이 예사라 빈 바탕보다 낫다.
    if (BASEMAPS.vworld_hybrid) return "vworld_hybrid";
    return "none";
  }

  function initMap() {
    pointLayerGroup = new ol.layer.Group({ layers: [] });

    // 재는 것과 찍은 점. **어느 것도 저장하지 않는다** — 새로 고치면 사라진다.
    // 점묶음(`PointSet`)과 다른 자리다. 저쪽은 올린 자료라 남고, 이쪽은
    // 지금 보면서 재는 것이라 남을 까닭이 없다.
    measureSource = new ol.source.Vector();
    measureLayer = new ol.layer.Vector({ source: measureSource, style: measureStyle });
    tempSource = new ol.source.Vector();
    tempLayer = new ol.layer.Vector({ source: tempSource, style: tempStyle });
    // 좌표를 찍어 찾아간 자리. 한 번에 하나만 둔다.
    foundSource = new ol.source.Vector();
    foundLayer = new ol.layer.Vector({ source: foundSource, style: foundStyle });

    map = new ol.Map({
      target: "map",
      layers: [pointLayerGroup, measureLayer, tempLayer, foundLayer],
      view: new ol.View({
        // 남한 전체가 들어오는 자리
        center: ol.proj.fromLonLat([127.8, 36.2]),
        zoom: 7,
        minZoom: 5,
        maxZoom: 19,
      }),
      // 축척 막대는 제 자리(왼쪽 아래)에 두면 좌표 막대가 덮는다.
      // 그래서 좌표 막대 바로 위의 칸에 붙인다.
      controls: ol.control.defaults.defaults({ attributionOptions: { collapsible: true } })
        .extend([
          new ol.control.ScaleLine({ target: document.getElementById("scalebar"), bar: true, steps: 2, text: true, minWidth: 130 }),
        ]),
    });

    popupOverlay = new ol.Overlay({
      element: document.getElementById("popup"),
      autoPan: { animation: { duration: 200 } },
      offset: [0, -8],
      positioning: "bottom-center",
    });
    map.addOverlay(popupOverlay);

    map.on("pointermove", onMove);
    map.on("singleclick", onClick);
  }

  /** 켠 레이어를 화면 순서에 맞춰 다시 쌓는다.
   *  `active[0]` 이 맨 앞이므로 OpenLayers 에는 거꾸로 넣는다. */
  function restack() {
    map.getLayers().getArray().slice().forEach(function (l) {
      if (l.get("gsm")) map.removeLayer(l);
    });
    // 배경지도는 있으면 z=0 에 있다. 켠 레이어는 그 위에 쌓는다.
    var baseCount = baseLayer ? 1 : 0;
    active.slice().reverse().forEach(function (entry, index) {
      entry.layer.setZIndex(baseCount + index);
      entry.layer.set("gsm", true);
      map.getLayers().insertAt(baseCount + index, entry.layer);
    });
    pointLayerGroup.setZIndex(500);
    measureLayer.setZIndex(600);
    tempLayer.setZIndex(700);
    foundLayer.setZIndex(800);
    renderActive();
  }

  function addLayer(name) {
    if (active.some(function (e) { return e.name === name; })) return;
    var row = byName[name];
    if (!row) return;
    active.unshift({
      name: name,
      title: row.title,
      opacity: DEFAULT_OPACITY,
      legendOpen: false,
      layer: new ol.layer.Tile({ source: wmsSource(name), opacity: DEFAULT_OPACITY }),
    });
    restack();
  }

  function removeLayer(name) {
    var index = active.findIndex(function (e) { return e.name === name; });
    if (index < 0) return;
    map.removeLayer(active[index].layer);
    active.splice(index, 1);
    restack();
    var box = document.querySelector('input[data-layer="' + cssEscape(name) + '"]');
    if (box) box.checked = false;
  }

  function move(name, delta) {
    var index = active.findIndex(function (e) { return e.name === name; });
    var target = index + delta;
    if (index < 0 || target < 0 || target >= active.length) return;
    var moved = active.splice(index, 1)[0];
    active.splice(target, 0, moved);
    restack();
  }

  // ── 레이어 패널 ─────────────────────────────────────────────────

  function renderCatalog() {
    var host = document.getElementById("layer-catalog");
    host.innerHTML = "";
    catalog.forEach(function (group, index) {
      var details = document.createElement("details");
      details.className = "group";
      if (index === 0) details.open = true;

      var summary = document.createElement("summary");
      summary.innerHTML = esc(group.name) +
        ' <span class="count">' + group.layers.length + "</span>";
      details.appendChild(summary);

      group.layers.forEach(function (layer) {
        var row = document.createElement("div");
        row.className = "layer-row";
        row.dataset.search = (layer.title + " " + layer.name).toLowerCase();

        var box = document.createElement("input");
        box.type = "checkbox";
        box.id = "lyr-" + layer.name;
        box.dataset.layer = layer.name;
        box.addEventListener("change", function () {
          if (box.checked) addLayer(layer.name); else removeLayer(layer.name);
        });

        var label = document.createElement("label");
        label.htmlFor = box.id;
        label.textContent = layer.title;
        if (layer.abstract) label.title = layer.abstract;
        if (!layer.verified) {
          var mark = document.createElement("span");
          mark.className = "unverified";
          mark.textContent = " ·";
          mark.title = "오픈API 로 그려지는지 아직 대조하지 않았다";
          label.appendChild(mark);
        }

        row.appendChild(box);
        row.appendChild(label);
        details.appendChild(row);
      });
      host.appendChild(details);
    });
  }

  function setCount(id, n) {
    var el = document.getElementById(id);
    if (el) el.textContent = n;
  }

  function renderActive() {
    var host = document.getElementById("active-list");
    setCount("count-layers", active.length);
    host.innerHTML = "";
    if (!active.length) {
      host.innerHTML = '<li class="empty">아직 켠 레이어가 없다</li>';
      return;
    }
    active.forEach(function (entry, index) {
      var li = document.createElement("li");

      var head = document.createElement("div");
      head.className = "active-head";

      var up = iconButton("↑", "위로", index === 0, function () { move(entry.name, -1); });
      var down = iconButton("↓", "아래로", index === active.length - 1, function () { move(entry.name, 1); });
      var title = document.createElement("span");
      title.className = "active-title";
      title.textContent = entry.title;
      title.title = entry.name;
      var legendBtn = iconButton("범", "범례를 펼친다", false, function () {
        entry.legendOpen = !entry.legendOpen;
        renderActive();
      });
      var off = iconButton("×", "끈다", false, function () { removeLayer(entry.name); });

      head.append(up, down, title, legendBtn, off);

      var foot = document.createElement("div");
      foot.className = "active-foot";
      var range = document.createElement("input");
      range.type = "range";
      range.min = 0; range.max = 100; range.value = Math.round(entry.opacity * 100);
      var num = document.createElement("span");
      num.className = "opacity-num";
      num.textContent = range.value + "%";
      range.addEventListener("input", function () {
        entry.opacity = range.value / 100;
        entry.layer.setOpacity(entry.opacity);
        num.textContent = range.value + "%";
      });
      foot.append(range, num);

      li.append(head, foot);

      if (entry.legendOpen) {
        var img = document.createElement("img");
        img.className = "legend-img";
        img.alt = entry.title + " 범례";
        img.src = BASE + "legend/?layer=" + encodeURIComponent(entry.name);
        img.addEventListener("error", function () {
          img.replaceWith(note("범례를 받지 못했다"));
        });
        li.appendChild(img);
      }
      host.appendChild(li);
    });
  }

  function iconButton(text, title, disabled, onClick) {
    var b = document.createElement("button");
    b.className = "iconbtn";
    b.type = "button";
    b.textContent = text;
    b.title = title;
    b.disabled = disabled;
    b.addEventListener("click", onClick);
    return b;
  }

  function note(text) {
    var p = document.createElement("p");
    p.className = "hint";
    p.textContent = text;
    return p;
  }

  // ── 도구 — 점 찍기·거리·넓이 ───────────────────────────────────
  //
  // 공식 뷰어가 주는 보조 기능을 옮겨 왔다. **하나도 저장하지 않는다** —
  // 지금 보면서 재는 것이라, 새로 고치면 사라지는 것이 맞다. 남길 것은
  // "내 자료" 로 올린다.

  var MODE_HINT = {
    info: "지도를 누르면 그 지점의 지질 속성이 뜬다.",
    point: "지도를 누르면 점이 찍히고 위경도가 적힌다. 점을 눌러 지운다.",
    line: "눌러 가며 선을 잇는다. 두 번 누르면 끝난다.",
    area: "눌러 가며 둘레를 두른다. 두 번 누르면 끝난다.",
  };

  function tempStyle(feature) {
    return new ol.style.Style({
      image: new ol.style.Circle({
        radius: 6,
        fill: new ol.style.Fill({ color: "#27456f" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 2 }),
      }),
      text: new ol.style.Text({
        text: String(feature.get("no")),
        offsetY: -14,
        font: "600 11px ui-monospace, Menlo, monospace",
        fill: new ol.style.Fill({ color: "#1a2f4f" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 3 }),
      }),
    });
  }

  /** 찾아간 자리. 겹고리로 눈에 띄게 하고 위경도를 곁에 적는다. */
  function foundStyle(feature) {
    return [
      new ol.style.Style({
        image: new ol.style.Circle({
          radius: 15,
          fill: new ol.style.Fill({ color: "rgba(196, 63, 74, .16)" }),
          stroke: new ol.style.Stroke({ color: "rgba(196, 63, 74, .55)", width: 2 }),
        }),
      }),
      new ol.style.Style({
        image: new ol.style.Circle({
          radius: 5,
          fill: new ol.style.Fill({ color: "#c43f4a" }),
          stroke: new ol.style.Stroke({ color: "#fff", width: 2 }),
        }),
        text: new ol.style.Text({
          text: feature.get("label") || "",
          offsetY: -26,
          font: "600 11px ui-monospace, Menlo, monospace",
          fill: new ol.style.Fill({ color: "#8d2b33" }),
          stroke: new ol.style.Stroke({ color: "#fff", width: 4 }),
          overflow: true,
        }),
      }),
    ];
  }

  /** 찍어 넣은 좌표로 간다.
   *
   *  **도폭 한 장이 화면에 들어오게** 맞춘다(`SHEET_LON`×`SHEET_LAT`).
   *  줌 단계를 숫자로 박으면 화면 크기에 따라 보이는 범위가 달라지는데,
   *  범위를 주고 맞추면 어느 화면에서나 같은 만큼이 보인다.
   */
  function goTo(lat, lon) {
    var extent = ol.proj.transformExtent(
      [lon - SHEET_LON / 2, lat - SHEET_LAT / 2,
       lon + SHEET_LON / 2, lat + SHEET_LAT / 2],
      "EPSG:4326", map.getView().getProjection());

    foundSource.clear();
    foundSource.addFeature(new ol.Feature({
      geometry: new ol.geom.Point(ol.proj.fromLonLat([lon, lat])),
      label: formatPair(lon, lat),
    }));

    map.getView().fit(extent, { duration: 450, callback: function () {
      // 화면 한복판에 정확히 놓는다. fit 은 범위를 맞출 뿐이라
      // 가장자리에서 한두 픽셀 어긋나는 일이 있다.
      map.getView().setCenter(ol.proj.fromLonLat([lon, lat]));
    } });
  }

  function measureStyle(feature) {
    var label = feature.get("label") || "";
    return new ol.style.Style({
      fill: new ol.style.Fill({ color: "rgba(39, 69, 111, .14)" }),
      stroke: new ol.style.Stroke({ color: "#27456f", width: 2.5, lineDash: [7, 5] }),
      image: new ol.style.Circle({
        radius: 4,
        fill: new ol.style.Fill({ color: "#27456f" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 1.5 }),
      }),
      text: label ? new ol.style.Text({
        text: label,
        font: "600 12px ui-monospace, Menlo, monospace",
        fill: new ol.style.Fill({ color: "#1a2f4f" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 4 }),
        overflow: true,
      }) : undefined,
    });
  }

  /** 미터를 사람이 읽는 길이로. */
  function asLength(m) {
    return m >= 1000 ? (m / 1000).toFixed(2) + " km" : m.toFixed(1) + " m";
  }

  /** 제곱미터를 사람이 읽는 넓이로. 헥타르를 함께 적는다 —
   *  현장에서 면적을 말할 때 ha 를 쓰는 일이 잦다. */
  function asArea(m2) {
    if (m2 >= 1e6) return (m2 / 1e6).toFixed(3) + " km² (" + (m2 / 1e4).toFixed(1) + " ha)";
    if (m2 >= 1e4) return (m2 / 1e4).toFixed(2) + " ha (" + Math.round(m2).toLocaleString() + " m²)";
    return Math.round(m2).toLocaleString() + " m²";
  }

  function measureOf(geometry) {
    var opts = { projection: map.getView().getProjection() };
    if (geometry instanceof ol.geom.Polygon) {
      return { text: asArea(ol.sphere.getArea(geometry, opts)), kind: "넓이" };
    }
    return { text: asLength(ol.sphere.getLength(geometry, opts)), kind: "거리" };
  }

  function setMode(next) {
    mode = next;
    if (drawInteraction) {
      map.removeInteraction(drawInteraction);
      drawInteraction = null;
    }
    document.querySelectorAll(".mode").forEach(function (b) {
      b.classList.toggle("on", b.dataset.mode === next);
    });
    document.getElementById("mode-hint").textContent = MODE_HINT[next] || "";
    document.getElementById("map").style.cursor =
      next === "info" ? "" : "crosshair";

    if (next !== "line" && next !== "area") return;

    drawInteraction = new ol.interaction.Draw({
      source: measureSource,
      type: next === "line" ? "LineString" : "Polygon",
      style: measureStyle,
    });
    drawInteraction.on("drawstart", function (evt) {
      // 재는 것은 한 번에 하나만 둔다. 여럿이 겹치면 어느 것이 어느 것인지
      // 알 수 없고, 화면이 금세 지저분해진다.
      measureSource.clear();
      var geometry = evt.feature.getGeometry();
      geometry.on("change", function () {
        var got = measureOf(geometry);
        evt.feature.set("label", got.text);
        showMeasure(got);
      });
    });
    drawInteraction.on("drawend", function (evt) {
      var got = measureOf(evt.feature.getGeometry());
      evt.feature.set("label", got.text);
      showMeasure(got, true);
    });
    map.addInteraction(drawInteraction);
  }

  function showMeasure(got, done) {
    var out = document.getElementById("measure-out");
    out.textContent = got.kind + " " + got.text;
    out.classList.toggle("done", !!done);
  }

  function addTempPoint(coordinate) {
    var ll = ol.proj.toLonLat(coordinate);
    tempSeq += 1;
    var feature = new ol.Feature({
      geometry: new ol.geom.Point(coordinate),
      no: tempSeq,
      lat: ll[1],
      lon: ll[0],
    });
    tempSource.addFeature(feature);
    renderTemp();
  }

  function renderTemp() {
    var host = document.getElementById("temp-list");
    var features = tempSource.getFeatures();
    setCount("count-temp", features.length);
    host.innerHTML = "";
    if (!features.length) {
      host.innerHTML = '<li class="empty">아직 찍은 점이 없다</li>';
      return;
    }
    features.forEach(function (feature) {
      var li = document.createElement("li");

      var no = document.createElement("span");
      no.className = "temp-no";
      no.textContent = feature.get("no");

      var text = document.createElement("button");
      text.type = "button";
      text.className = "temp-coord";
      text.title = "눌러서 복사한다";
      text.textContent = formatPair(feature.get("lon"), feature.get("lat"));
      text.addEventListener("click", function () {
        var value = text.textContent;
        if (!navigator.clipboard) return;
        navigator.clipboard.writeText(value).then(function () {
          text.textContent = "복사했다";
          setTimeout(function () { text.textContent = value; }, 700);
        });
      });

      var go = iconButton("⊙", "이 점으로 이동", false, function () {
        map.getView().animate({
          center: feature.getGeometry().getCoordinates(), duration: 300,
        });
      });
      var del = iconButton("×", "지운다", false, function () {
        tempSource.removeFeature(feature);
        renderTemp();
      });

      li.append(no, text, go, del);
      host.appendChild(li);
    });
  }

  /** 찍어 둔 점을 **목록으로 저장한다.** 구글 지도의 "장소 저장" 과 같은 자리다.
   *
   *  임시 표시는 새로 고치면 사라진다. 그러다 "이건 남겨야겠다" 싶은 때가
   *  오는데, 그때 파일로 내보냈다 다시 올리게 하면 아무도 안 한다.
   *  있는 그대로 점묶음이 되게 했다.
   */
  function saveTemp() {
    var features = tempSource.getFeatures();
    var msg = document.getElementById("save-msg");
    if (!features.length) {
      msg.className = "msg bad";
      msg.textContent = "저장할 점이 없다.";
      return;
    }
    var name = prompt("목록 이름", "찍은 점 " + new Date().toLocaleDateString("ko-KR"));
    if (name === null) return;

    msg.className = "msg";
    msg.textContent = "저장하는 중…";

    fetch(BASE + "pointsets/create/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({
        name: name,
        color: "#27456f",
        points: features.map(function (f) {
          return { lat: f.get("lat"), lon: f.get("lon"), label: "점 " + f.get("no") };
        }),
      }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) {
          msg.className = "msg bad";
          msg.textContent = res.d.error || "저장하지 못했다";
          return;
        }
        pointsets.unshift(res.d.pointset);
        renderPointSets();
        // 저장했으니 임시 표시는 치운다. 같은 점이 두 겹으로 남으면 헷갈린다.
        tempSource.clear();
        tempSeq = 0;
        renderTemp();
        msg.className = "msg good";
        msg.textContent = "'" + res.d.pointset.name + "' 으로 저장했다.";
      })
      .catch(function () {
        msg.className = "msg bad";
        msg.textContent = "저장하지 못했다";
      });
  }

  function wireTools() {
    document.querySelectorAll(".mode").forEach(function (button) {
      button.addEventListener("click", function () { setMode(button.dataset.mode); });
    });
    document.getElementById("save-temp").addEventListener("click", saveTemp);
    document.getElementById("clear-temp").addEventListener("click", function () {
      tempSource.clear();
      measureSource.clear();
      foundSource.clear();
      tempSeq = 0;
      renderTemp();
      var out = document.getElementById("measure-out");
      out.textContent = "아직 잰 것이 없다";
      out.classList.remove("done");
    });
    renderTemp();
    setMode("info");
  }

  // ── 클릭해 속성 읽기 ────────────────────────────────────────────

  function onClick(evt) {
    if (mode === "point") {
      addTempPoint(evt.coordinate);
      return;
    }
    if (mode !== "info") return;      // 재는 중에는 팝업을 띄우지 않는다

    var parts = [];

    // 내 점이 먼저다 — 눌러서 맞힌 것이 분명하기 때문이다
    map.forEachFeatureAtPixel(evt.pixel, function (feature) {
      if (feature.get("no") !== undefined && feature.get("lat") !== undefined) {
        parts.push({
          title: "찍은 점 " + feature.get("no"),
          props: {
            "위도": feature.get("lat").toFixed(6),
            "경도": feature.get("lon").toFixed(6),
            "도분초": coordText(feature.get("lon"), feature.get("lat")),
          },
        });
        return;
      }
      parts.push({ title: feature.get("_점묶음") || "내 자료", props: plain(feature.getProperties()) });
    }, { hitTolerance: 5 });

    var queryable = active.filter(function (e) {
      var row = byName[e.name];
      return row && row.queryable;
    });

    if (!queryable.length) {
      showPopup(evt.coordinate, parts, parts.length ? "" : "켠 레이어가 없다");
      return;
    }

    showPopup(evt.coordinate, parts, "읽는 중…");

    var view = map.getView();
    var pending = queryable.length;
    var results = new Array(queryable.length);

    queryable.forEach(function (entry, index) {
      var url = entry.layer.getSource().getFeatureInfoUrl(
        evt.coordinate, view.getResolution(), view.getProjection(),
        { INFO_FORMAT: "application/json", FEATURE_COUNT: 5 });
      if (!url) { pending -= 1; return; }
      // 서버의 /featureinfo/ 로 돌린다 — 인증키는 서버가 붙인다
      url = url.replace(BASE + "wms", BASE + "featureinfo/");

      fetch(url)
        .then(function (r) { return r.json(); })
        .catch(function () { return { features: [] }; })
        .then(function (data) {
          results[index] = (data.features || []).map(function (f) {
            return { title: entry.title, props: f.props };
          });
          pending -= 1;
          if (pending === 0) {
            var all = parts.concat.apply(parts, results.filter(Boolean));
            showPopup(evt.coordinate, all, all.length ? "" : "이 자리에는 아무것도 없다");
          }
        });
    });

    if (pending === 0) showPopup(evt.coordinate, parts, parts.length ? "" : "이 자리에는 아무것도 없다");
  }

  function showPopup(coordinate, parts, emptyText) {
    var body = document.getElementById("popup-body");
    body.innerHTML = "";

    // **첫 줄은 언제나 누른 자리의 위경도다.** 속성이 무엇이 나오든,
    // 무엇도 안 나오든 "여기가 어디인가" 는 늘 답이 되어야 한다.
    var ll = ol.proj.toLonLat(coordinate);
    var head = document.createElement("button");
    head.type = "button";
    head.className = "popup-coord";
    head.title = "눌러서 복사한다";
    head.textContent = formatPair(ll[0], ll[1]);
    head.addEventListener("click", function () {
      var value = head.textContent;
      if (!navigator.clipboard) return;
      navigator.clipboard.writeText(value).then(function () {
        head.textContent = "복사했다";
        setTimeout(function () { head.textContent = value; }, 700);
      });
    });
    body.appendChild(head);

    if (!parts.length) {
      var none = document.createElement("p");
      none.className = "none";
      none.textContent = emptyText || "";
      body.appendChild(none);
    } else {
      parts.forEach(function (part) {
        var h = document.createElement("h3");
        h.textContent = part.title;
        body.appendChild(h);
        var table = document.createElement("table");
        Object.keys(part.props).forEach(function (key) {
          var tr = document.createElement("tr");
          var th = document.createElement("th");
          th.textContent = key;
          tr.append(th, valueCell(part.props[key]));
          table.appendChild(tr);
        });
        body.appendChild(table);
      });
    }
    document.getElementById("popup").classList.add("on");
    popupOverlay.setPosition(coordinate);
  }

  /** 속성값 한 칸. 서버가 `{text, links}` 로 갈라 보낸 것은 진짜 링크로 그린다.
   *  **5만 지질도의 `도폭`** 이 그렇게 온다 — 원도 PDF 와 수치지질도 DOI 가
   *  딸려 있다. 주소 검사는 서버가 이미 했다(`views._split_links`). 여기서는
   *  `textContent` 와 `href` 만 쓰고 **innerHTML 을 쓰지 않는다.** */
  function valueCell(value) {
    var td = document.createElement("td");
    if (value && typeof value === "object" && value.links) {
      if (value.text) td.appendChild(document.createTextNode(value.text));
      value.links.forEach(function (link) {
        var a = document.createElement("a");
        a.className = "proplink";
        a.href = link.url;
        a.target = "_blank";
        a.rel = "noopener noreferrer";
        a.textContent = link.label;
        td.appendChild(a);
      });
    } else {
      td.textContent = String(value);
    }
    return td;
  }

  function plain(props) {
    var out = {};
    Object.keys(props).forEach(function (k) {
      if (k === "geometry" || k.charAt(0) === "_") return;
      if (props[k] === null || props[k] === "") return;
      out[k] = props[k];
    });
    return out;
  }

  // ── 좌표 ────────────────────────────────────────────────────────

  function dd2dms(value, isLat) {
    var hemi = isLat ? (value >= 0 ? "N" : "S") : (value >= 0 ? "E" : "W");
    value = Math.abs(value);
    var deg = Math.floor(value);
    var rest = (value - deg) * 60;
    var min = Math.floor(rest);
    var sec = (rest - min) * 60;
    if (Math.round(sec * 10) / 10 >= 60) { sec = 0; min += 1; }
    if (min >= 60) { min = 0; deg += 1; }
    return deg + "°" + String(min).padStart(2, "0") + "'" +
      sec.toFixed(1).padStart(4, "0") + '"' + hemi;
  }

  function coordText(lon, lat) {
    return dd2dms(lat, true) + " " + dd2dms(lon, false);
  }

  function formatPair(lon, lat) {
    return useDms
      ? dd2dms(lat, true) + " " + dd2dms(lon, false)
      : lat.toFixed(6) + ", " + lon.toFixed(6);
  }

  function onMove(evt) {
    if (evt.dragging) return;
    var ll = ol.proj.toLonLat(evt.coordinate);
    document.getElementById("mouse-coord").textContent = formatPair(ll[0], ll[1]);
  }

  // ── 점묶음 ──────────────────────────────────────────────────────

  function pointStyle(color) {
    return new ol.style.Style({
      image: new ol.style.Circle({
        radius: 5,
        fill: new ol.style.Fill({ color: color }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 1.5 }),
      }),
    });
  }

  function loadPointSet(ps) {
    if (pointLayers[ps.id]) {
      pointLayers[ps.id].setVisible(ps.visible);
      return;
    }
    var source = new ol.source.Vector({
      url: BASE + "pointsets/" + ps.id + "/geojson/",
      format: new ol.format.GeoJSON({ featureProjection: "EPSG:3857" }),
    });
    source.on("featuresloadend", function (e) {
      e.features.forEach(function (f) { f.set("_점묶음", ps.name); });
    });
    var layer = new ol.layer.Vector({
      source: source,
      style: pointStyle(ps.color),
      visible: ps.visible,
    });
    pointLayers[ps.id] = layer;
    pointLayerGroup.getLayers().push(layer);
  }

  function renderPointSets() {
    var host = document.getElementById("pointset-list");
    setCount("count-points", pointsets.length);
    host.innerHTML = "";
    if (!pointsets.length) {
      host.innerHTML = '<li class="empty">올린 자료가 없다</li>';
      return;
    }
    pointsets.forEach(function (ps) {
      loadPointSet(ps);
      var li = document.createElement("li");

      var box = document.createElement("input");
      box.type = "checkbox";
      box.checked = ps.visible;
      box.addEventListener("change", function () {
        ps.visible = box.checked;
        if (pointLayers[ps.id]) pointLayers[ps.id].setVisible(ps.visible);
      });

      var swatch = document.createElement("span");
      swatch.className = "swatch";
      swatch.style.background = ps.color;

      var name = document.createElement("span");
      name.className = "ps-name";
      name.textContent = ps.name;

      var count = document.createElement("span");
      count.className = "ps-count";
      count.textContent = ps.count + "점";

      var zoom = iconButton("⊙", "이 자료로 범위를 맞춘다", false, function () {
        var source = pointLayers[ps.id] && pointLayers[ps.id].getSource();
        var extent = source && source.getExtent();
        if (extent && isFinite(extent[0])) {
          map.getView().fit(extent, { padding: [40, 40, 60, 40], maxZoom: 14, duration: 300 });
        }
      });

      var del = iconButton("×", "지운다", false, function () {
        if (!confirm("'" + ps.name + "' 을 지운다.")) return;
        post(BASE + "pointsets/" + ps.id + "/delete/").then(function () {
          if (pointLayers[ps.id]) {
            pointLayerGroup.getLayers().remove(pointLayers[ps.id]);
            delete pointLayers[ps.id];
          }
          pointsets = pointsets.filter(function (x) { return x.id !== ps.id; });
          renderPointSets();
        });
      });

      li.append(box, swatch, name, count, zoom, del);
      host.appendChild(li);
    });
  }

  function csrf() {
    var input = document.querySelector("#upload-form [name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  function post(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": csrf() },
      body: body || new FormData(),
    });
  }

  // ── 붙이기 ──────────────────────────────────────────────────────

  function wireBasemap() {
    var select = document.getElementById("basemap");
    Object.keys(BASEMAPS).forEach(function (key) {
      var option = document.createElement("option");
      option.value = key;
      option.textContent = BASEMAPS[key].title;
      if (BASEMAPS[key].note) option.title = BASEMAPS[key].note;
      select.appendChild(option);
    });
    var labelBox = document.getElementById("basemap-labels");
    var labelWrap = document.getElementById("basemap-labels-wrap");

    function syncLabelBox() {
      var spec = BASEMAPS[select.value];
      var has = !!(spec && spec.labels);
      labelWrap.style.display = has ? "" : "none";
      labelBox.checked = labelsOn();
    }

    select.value = savedBasemap();
    select.addEventListener("change", function () {
      setBasemap(select.value);
      syncLabelBox();
      restack();
    });
    labelBox.addEventListener("change", function () { setLabels(labelBox.checked); });

    setBasemap(select.value);
    syncLabelBox();
  }

  // ── 설정과 판 이력 ─────────────────────────────────────────────

  function wireSettings() {
    var sheet = document.getElementById("settings");
    var loaded = false;

    function open() {
      sheet.hidden = false;
      renderState();
      if (loaded) return;
      loaded = true;
      fetch(BASE + "patchnotes/")
        .then(function (r) { return r.json(); })
        .then(function (d) { renderNotes(d.notes || []); })
        .catch(function () {
          document.getElementById("notes").textContent = "판 이력을 읽지 못했다.";
        });
    }

    function close() { sheet.hidden = true; }

    document.getElementById("gear").addEventListener("click", open);
    document.getElementById("settings-close").addEventListener("click", close);
    sheet.addEventListener("click", function (e) { if (e.target === sheet) close(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !sheet.hidden) close();
    });
  }

  /** 지금 무엇으로 돌고 있는지. 화면을 보고 상태를 물어오는 일이 잦아 둔다. */
  function renderState() {
    var rows = [
      ["배경지도", (BASEMAPS[document.getElementById("basemap").value] || {}).title || "없음"],
      ["켠 레이어", active.length ? active.map(function (e) { return e.title; }).join(", ") : "없음"],
      ["찍은 점", tempSource.getFeatures().length + "개"],
      ["올린 자료", pointsets.length + "묶음"],
      ["좌표 표기", useDms ? "도분초" : "십진도"],
    ];
    var host = document.getElementById("settings-state");
    host.innerHTML = "";
    rows.forEach(function (row) {
      var dt = document.createElement("dt");
      dt.textContent = row[0];
      var dd = document.createElement("dd");
      dd.textContent = row[1];
      host.append(dt, dd);
    });
  }

  function renderNotes(notes) {
    var host = document.getElementById("notes");
    host.innerHTML = "";
    if (!notes.length) {
      host.textContent = "아직 적힌 판이 없다.";
      return;
    }
    notes.forEach(function (note) {
      var head = document.createElement("h4");
      head.innerHTML = esc(note.version) +
        (note.title ? ' <span class="note-title">' + esc(note.title) + "</span>" : "") +
        (note.date ? ' <span class="note-date">' + esc(note.date) + "</span>" : "");
      host.appendChild(head);

      if (note.lead) {
        var lead = document.createElement("p");
        lead.className = "note-lead";
        lead.textContent = note.lead;
        host.appendChild(lead);
      }
      if (note.items.length) {
        var ul = document.createElement("ul");
        note.items.forEach(function (item) {
          var li = document.createElement("li");
          // 문서에 `코드` 가 섞여 온다. 한 겹만 풀어 준다.
          li.innerHTML = esc(item).replace(/`([^`]+)`/g, "<code>$1</code>")
                                  .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
          ul.appendChild(li);
        });
        host.appendChild(ul);
      }
    });
  }

  function wireTabs() {
    document.querySelectorAll(".tab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll(".tab").forEach(function (t) { t.classList.remove("on"); });
        document.querySelectorAll(".tabbody").forEach(function (b) { b.classList.remove("on"); });
        tab.classList.add("on");
        document.getElementById("tab-" + tab.dataset.tab).classList.add("on");
      });
    });
  }

  function wireFilter() {
    var input = document.getElementById("layer-filter");
    input.addEventListener("input", function () {
      var q = input.value.trim().toLowerCase();
      document.querySelectorAll("#layer-catalog .group").forEach(function (group) {
        var shown = 0;
        group.querySelectorAll(".layer-row").forEach(function (row) {
          var hit = !q || row.dataset.search.indexOf(q) >= 0;
          row.style.display = hit ? "" : "none";
          if (hit) shown += 1;
        });
        group.style.display = shown ? "" : "none";
        if (q) group.open = true;
      });
    });
  }

  function wireCoordBar() {
    document.getElementById("dms-toggle").addEventListener("click", function () {
      useDms = !useDms;
      this.classList.toggle("on", useDms);
    });

    document.getElementById("mouse-coord").addEventListener("click", function () {
      var text = this.textContent;
      if (!text || text === "—" || !navigator.clipboard) return;
      var self = this;
      navigator.clipboard.writeText(text).then(function () {
        self.textContent = "복사했다";
        setTimeout(function () { self.textContent = text; }, 700);
      });
    });

    document.getElementById("goto-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var input = document.getElementById("goto-input");
      var q = input.value.trim();
      if (!q) return;
      fetch(BASE + "coords/parse/?q=" + encodeURIComponent(q))
        .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
        .then(function (d) {
          goTo(d.lat, d.lon);
          input.setCustomValidity("");
        })
        .catch(function () {
          input.setCustomValidity("좌표로 읽지 못했다");
          input.reportValidity();
          setTimeout(function () { input.setCustomValidity(""); }, 1500);
        });
    });
  }

  function wireUpload() {
    var form = document.getElementById("upload-form");
    var file = document.getElementById("upload-file");
    var msg = document.getElementById("upload-msg");

    file.addEventListener("change", function () {
      var box = file.closest(".filebox");
      box.classList.toggle("has", !!file.files.length);
      if (file.files.length) box.querySelector("span").textContent = file.files[0].name;
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!file.files.length) return;
      var data = new FormData();
      data.append("file", file.files[0]);
      data.append("name", document.getElementById("upload-name").value);
      data.append("color", document.getElementById("upload-color").value);

      msg.className = "msg";
      msg.textContent = "읽는 중…";

      post(BASE + "pointsets/upload/", data)
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) {
            msg.className = "msg bad";
            msg.textContent = res.d.error || "올리지 못했다";
            return;
          }
          pointsets.unshift(res.d.pointset);
          renderPointSets();
          msg.className = "msg good";
          msg.textContent = res.d.pointset.count + "점을 올렸다." +
            (res.d.notes && res.d.notes.length ? " " + res.d.notes.join(" / ") : "");
          form.reset();
          var box = file.closest(".filebox");
          box.classList.remove("has");
          box.querySelector("span").textContent = "CSV · GeoJSON 고르기";
        })
        .catch(function () {
          msg.className = "msg bad";
          msg.textContent = "올리지 못했다";
        });
    });
  }

  function wirePopup() {
    document.getElementById("popup-close").addEventListener("click", function () {
      document.getElementById("popup").classList.remove("on");
      popupOverlay.setPosition(undefined);
    });
  }

  function esc(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function cssEscape(text) {
    return String(text).replace(/["\\]/g, "\\$&");
  }

  initMap();
  wireBasemap();
  renderCatalog();
  renderActive();
  renderPointSets();
  wireTools();
  wireSettings();
  wireTabs();
  wireFilter();
  wireCoordBar();
  wireUpload();
  wirePopup();

  // 처음 열면 5만 지질도를 켜 둔다. 빈 지도보다 무엇이든 보이는 편이 낫고,
  // **5만이 실제로 가장 많이 보는 축척이다.** 100만·25만은 켜서 보는 것이지
  // 켜 두고 시작할 것이 아니다.
  if (byName["L_50K_Geology_Map"]) {
    var box = document.querySelector('input[data-layer="L_50K_Geology_Map"]');
    if (box) { box.checked = true; }
    addLayer("L_50K_Geology_Map");
  }
})();
