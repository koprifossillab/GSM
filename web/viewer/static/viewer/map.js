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

  // ── 말 ───────────────────────────────────────────────────────────
  //
  // 화면의 글은 한국어로 적고 `T()` 로 감싼다. 영어판이면 서버가 번역표
  // (`viewer/i18n.py` 의 `EN`)를 실어 보내고, 표에 없는 문장은 한국어로
  // 남는다. **문장을 새로 적으면 번역표에도 적는다** — 시험
  // (`test_i18n`)이 빠진 것을 잡는다. 숫자·이름이 끼는 자리는 `{n}` 처럼
  // 자리표로 두고 넘긴다 — 영어는 말 차례가 달라 이어 붙이면 어색하다.
  var LANG = document.documentElement.lang === "en" ? "en" : "ko";
  var I18N = JSON.parse((document.getElementById("i18n-data") || {}).textContent || "{}");

  function T(text, vars) {
    var out = (LANG === "en" && I18N[text]) || text;
    if (vars) {
      out = out.replace(/\{(\w+)\}/g, function (m, k) { return k in vars ? vars[k] : m; });
    }
    return out;
  }
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
  var rangeSource, rangeLayer, rangeSeq = 0;
  var mode = "info", drawInteraction = null, tempSeq = 0, lastMeasure = "";
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
    none: { title: T("없음 (바탕만)"), make: null },
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
      title: T("VWorld 배경지도"),
      note: T("국토지리정보원"),
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
    // 백지도·야간지도. `Base` 와 같은 창구에 레이어 이름만 다르다.
    // **지질도 밑에는 백지도가 낫다** — 도로·지명 색이 죽어 있어 지질도의
    // 분홍·자홍과 다투지 않는다 (004). 야간은 먹갈색 화면과 어울린다.
    BASEMAPS.vworld_white = {
      title: T("VWorld 백지도"),
      note: T("국토지리정보원. 지질도 밑에 깔기 좋다"),
      make: function () { return vworldPlain("white"); },
    };
    BASEMAPS.vworld_midnight = {
      title: T("VWorld 야간"),
      note: T("국토지리정보원"),
      make: function () { return vworldPlain("midnight"); },
    };
    // 위성 사진과 지명은 **따로 오는 레이어다**(`Satellite`·`Hybrid`).
    // 그래서 지명만 끌 수 있다 — 지질 경계를 볼 때 글자가 방해가 된다.
    // 일반 배경지도(`Base`)는 지명이 그림에 박혀 있어 끄지 못한다.
    BASEMAPS.vworld_hybrid = {
      title: T("VWorld 위성"),
      note: T("국토지리정보원. 지명을 끄고 켤 수 있다"),
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

  /** VWorld 의 한 장짜리 배경(`white`·`midnight`). */
  function vworldPlain(name) {
    return new ol.layer.Tile({
      opacity: 0.85,
      source: new ol.source.XYZ({
        url: "https://api.vworld.kr/req/wmts/1.0.0/" + encodeURIComponent(vworldKey)
             + "/" + name + "/{z}/{y}/{x}.png",
        crossOrigin: "anonymous",
        maxZoom: 19,
        attributions: '© <a href="https://www.vworld.kr/" target="_blank" rel="noopener">VWorld</a>',
      }),
    });
  }

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
    // 잡은 범위. 재는 것(`measureSource`)과 달리 여럿을 두고 목록에 남긴다
    rangeSource = new ol.source.Vector();
    rangeLayer = new ol.layer.Vector({ source: rangeSource, style: rangeStyle });
    // 좌표를 찍어 찾아간 자리. 한 번에 하나만 둔다.
    foundSource = new ol.source.Vector();
    foundLayer = new ol.layer.Vector({ source: foundSource, style: foundStyle });

    map = new ol.Map({
      target: "map",
      layers: [pointLayerGroup, rangeLayer, measureLayer, tempLayer, foundLayer],
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
      // 아래 가장자리에는 좌표 막대가 덮여 있다. 여백을 주지 않으면 팝업
      // 아랫단이 막대 밑으로 들어간다.
      autoPan: { animation: { duration: 200 }, margin: 72 },
      offset: [0, -8],
      positioning: "bottom-center",
    });
    map.addOverlay(popupOverlay);

    map.on("moveend", renderEdges);
    map.on("moveend", saveView);
    window.addEventListener("resize", renderEdges);
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
    rangeLayer.setZIndex(550);
    measureLayer.setZIndex(600);
    tempLayer.setZIndex(700);
    foundLayer.setZIndex(800);
    renderActive();
    saveLayers();
    if (typeof refreshCompare === "function") refreshCompare();
  }

  // ── 기억하기 ─────────────────────────────────────────────────────
  //
  // 켠 레이어(차례·투명도)와 보던 자리를 브라우저에 둔다. 새로 고치면 다
  // 풀리던 것이 불편했다. **이 브라우저에만 남는다** — 서버에 올리지 않고,
  // 사생활 모드처럼 저장이 막혀도 처음 화면으로 돌 뿐 멈추지 않는다.

  var restoring = false;   // 되살리는 동안에는 저장하지 않는다

  function saveLayers() {
    if (restoring) return;
    var rows = active.map(function (e) {
      return { name: e.name, opacity: Math.round(e.opacity * 100) / 100 };
    });
    try { localStorage.setItem("gsm.layers", JSON.stringify(rows)); } catch (e) { /* 사생활 모드 */ }
  }

  function saveView() {
    var view = map.getView();
    var center = ol.proj.toLonLat(view.getCenter());
    var state = { lon: +center[0].toFixed(5), lat: +center[1].toFixed(5),
                  zoom: +view.getZoom().toFixed(2) };
    try { localStorage.setItem("gsm.view", JSON.stringify(state)); } catch (e) { /* 사생활 모드 */ }
  }

  function readJson(key) {
    try { return JSON.parse(localStorage.getItem(key) || "null"); } catch (e) { return null; }
  }

  /** 기억한 것이 있으면 되살리고 true. 처음 온 사람이면 false. */
  function restoreState() {
    var view = readJson("gsm.view");
    if (view && isFinite(view.lon) && isFinite(view.lat) && isFinite(view.zoom)) {
      map.getView().setCenter(ol.proj.fromLonLat([view.lon, view.lat]));
      map.getView().setZoom(view.zoom);
    }
    var rows = readJson("gsm.layers");
    if (!Array.isArray(rows)) return false;
    restoring = true;
    // addLayer 는 맨 위에 얹는다. 그래서 맨 아래 것부터 얹는다.
    rows.slice().reverse().forEach(function (row) {
      if (!row || !byName[row.name]) return;     // 카탈로그에서 내려간 레이어
      addLayer(row.name);
      var entry = active[0];
      if (entry.name === row.name && isFinite(row.opacity)) {
        entry.opacity = Math.min(1, Math.max(0, row.opacity));
        entry.layer.setOpacity(entry.opacity);
      }
      var box = document.querySelector('input[data-layer="' + cssEscape(row.name) + '"]');
      if (box) box.checked = true;
    });
    restoring = false;
    renderActive();
    saveLayers();
    return true;
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

  /** `name` 을 `target` 자리(0 이 맨 위)로 옮긴다. 끌어 놓을 때 쓴다. */
  function moveTo(name, target) {
    var index = active.findIndex(function (e) { return e.name === name; });
    if (index < 0) return;
    var moved = active.splice(index, 1)[0];
    if (index < target) target -= 1;          // 빼낸 만큼 뒤쪽 자리가 당겨진다
    active.splice(Math.max(0, Math.min(target, active.length)), 0, moved);
    restack();
  }

  // 끌고 있는 레이어. 끌기는 줄의 머리에서만 시작한다 — 줄 전체를 끌 수
  // 있게 하면 투명도 막대를 움직이다 줄이 끌려간다.
  var dragName = null;

  function wireDrag(li, head, entry, index) {
    head.draggable = true;
    head.classList.add("grab");
    head.addEventListener("dragstart", function (e) {
      dragName = entry.name;
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", entry.name);
      li.classList.add("dragging");
    });
    head.addEventListener("dragend", function () {
      dragName = null;
      document.querySelectorAll("#active-list li").forEach(function (x) {
        x.classList.remove("dragging", "drop-before", "drop-after");
      });
    });
    function after(e) {
      var box = li.getBoundingClientRect();
      return e.clientY > box.top + box.height / 2;
    }
    li.addEventListener("dragover", function (e) {
      if (!dragName) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = "move";
      li.classList.toggle("drop-after", after(e));
      li.classList.toggle("drop-before", !after(e));
    });
    li.addEventListener("dragleave", function () {
      li.classList.remove("drop-before", "drop-after");
    });
    li.addEventListener("drop", function (e) {
      if (!dragName) return;
      e.preventDefault();
      moveTo(dragName, index + (after(e) ? 1 : 0));
    });
  }

  // ── 레이어 패널 ─────────────────────────────────────────────────

  /** 늘 펼쳐 두는 기본 지질도 다섯 장. 차례가 화면의 차례다.
   *  지체구조도는 상류가 "그 밖" 에 넣어 두었지만 지질도로 늘 보는 것이라
   *  여기로 끌어온다. */
  var BASE_LAYERS = [
    "L_1M_Geology_Map",
    "L_250K_Geology_Map",
    "L_50K_Geology_Map",
    "l_50k_geology_frame_latest",
    "G_tectonic",
  ];

  /** 카탈로그.
   *
   *  **기본 지질도 다섯 장만 펼치고 나머지는 모두 "추가 지질도" 안으로
   *  접는다.** 61 개를 한 줄로 늘어놓으면 패널이 화면보다 길어져서 아래의
   *  "그리기" 칸이 밀려 안 보인다. 늘 보는 것과 찾아서 켜는 것의 차이를
   *  접기로 나타낸다. 추가 지질도 안에서는 상류의 레이어군을 그대로 쓴다.
   */
  function renderCatalog() {
    var host = document.getElementById("layer-catalog");
    host.innerHTML = "";

    function layerRow(layer) {
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
        mark.title = T("오픈API 로 그려지는지 아직 대조하지 않았다");
        label.appendChild(mark);
      }

      row.appendChild(box);
      row.appendChild(label);
      return row;
    }

    function folder(className, title, count, open) {
      var details = document.createElement("details");
      details.className = className;
      details.open = !!open;
      var summary = document.createElement("summary");
      summary.innerHTML = esc(title) + ' <span class="count">' + count + "</span>";
      details.appendChild(summary);
      return details;
    }

    var base = BASE_LAYERS.filter(function (name) { return byName[name]; });
    var baseBox = folder("group base", T("기본 지질도"), base.length, true);
    base.forEach(function (name) { baseBox.appendChild(layerRow(byName[name])); });
    host.appendChild(baseBox);

    var rest = [];
    var restCount = 0;
    catalog.forEach(function (group) {
      var layers = group.layers.filter(function (l) { return BASE_LAYERS.indexOf(l.name) < 0; });
      if (!layers.length) return;
      restCount += layers.length;
      rest.push({ name: group.name, layers: layers });
    });
    if (!restCount) return;

    var more = folder("group more", T("추가 지질도"), restCount, false);
    rest.forEach(function (group) {
      var details = folder("group", group.name, group.layers.length, false);
      group.layers.forEach(function (layer) { details.appendChild(layerRow(layer)); });
      more.appendChild(details);
    });
    host.appendChild(more);
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
      host.innerHTML = '<li class="empty">' + esc(T("아직 켠 레이어가 없다")) + "</li>";
      return;
    }
    active.forEach(function (entry, index) {
      var li = document.createElement("li");

      var head = document.createElement("div");
      head.className = "active-head";

      var up = iconButton("↑", T("위로"), index === 0, function () { move(entry.name, -1); });
      var down = iconButton("↓", T("아래로"), index === active.length - 1, function () { move(entry.name, 1); });
      var title = document.createElement("span");
      title.className = "active-title";
      title.textContent = entry.title;
      title.title = entry.name;
      var legendBtn = iconButton(T("범"), T("범례를 펼친다"), false, function () {
        entry.legendOpen = !entry.legendOpen;
        renderActive();
      });
      var bbox = byName[entry.name] && byName[entry.name].bbox;
      var fit = iconButton("⊙", T("이 레이어가 있는 곳으로 범위를 맞춘다"), !bbox, function () {
        fitLayer(entry.name);
      });
      var off = iconButton("×", T("끈다"), false, function () { removeLayer(entry.name); });

      head.append(up, down, title, fit, legendBtn, off);
      head.title = T("끌어서 차례를 바꾼다");
      wireDrag(li, head, entry, index);

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
      range.addEventListener("change", saveLayers);
      foot.append(range, num);

      li.append(head, foot);

      if (entry.legendOpen) {
        var img = document.createElement("img");
        img.className = "legend-img";
        img.alt = T("{title} 범례", { title: entry.title });
        img.src = BASE + "legend/?layer=" + encodeURIComponent(entry.name);
        img.addEventListener("error", function () {
          img.replaceWith(note(T("범례를 받지 못했다")));
        });
        li.appendChild(img);
      }
      host.appendChild(li);
    });
  }

  /** 레이어의 범위(`Layer.bbox`, 위경도)로 지도를 옮긴다.
   *  해저지질도처럼 바다에만 있는 레이어를 켰는데 화면에 아무것도 안
   *  보일 때 쓴다. 범위는 상류의 `GetCapabilities` 가 준 것이다. */
  function fitLayer(name) {
    var bbox = byName[name] && byName[name].bbox;
    if (!bbox) return;
    var extent = ol.proj.transformExtent(bbox, "EPSG:4326", "EPSG:3857");
    map.getView().fit(extent, { padding: [40, 40, 60, 40], duration: 300 });
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
    info: T("지도를 누르면 그 지점의 지질 속성이 뜬다."),
    point: T("지도를 누르면 점이 찍히고 위경도가 적힌다. 점을 눌러 지운다."),
    line: T("눌러 가며 선을 잇는다. 두 번 누르면 끝난다."),
    area: T("눌러 가며 둘레를 두른다. 두 번 누르면 끝난다."),
    box: T("누른 채 끌어 네모를 그린다. 손을 떼면 꼭짓점·중앙·넓이가 뜬다."),
  };

  function tempStyle(feature) {
    return new ol.style.Style({
      image: new ol.style.Circle({
        radius: 6,
        fill: new ol.style.Fill({ color: "#5c3a1e" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 2 }),
      }),
      text: new ol.style.Text({
        text: String(feature.get("no")),
        offsetY: -14,
        font: "600 11px ui-monospace, Menlo, monospace",
        fill: new ol.style.Fill({ color: "#3f2712" }),
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
          fill: new ol.style.Fill({ color: "rgba(158, 59, 42, .16)" }),
          stroke: new ol.style.Stroke({ color: "rgba(158, 59, 42, .6)", width: 2 }),
        }),
      }),
      new ol.style.Style({
        image: new ol.style.Circle({
          radius: 5,
          fill: new ol.style.Fill({ color: "#9e3b2a" }),
          stroke: new ol.style.Stroke({ color: "#fff", width: 2 }),
        }),
        text: new ol.style.Text({
          text: feature.get("label") || "",
          offsetY: -26,
          font: "600 11px ui-monospace, Menlo, monospace",
          fill: new ol.style.Fill({ color: "#7a2c1f" }),
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
  function goTo(lat, lon, label) {
    var extent = ol.proj.transformExtent(
      [lon - SHEET_LON / 2, lat - SHEET_LAT / 2,
       lon + SHEET_LON / 2, lat + SHEET_LAT / 2],
      "EPSG:4326", map.getView().getProjection());

    foundSource.clear();
    foundSource.addFeature(new ol.Feature({
      geometry: new ol.geom.Point(ol.proj.fromLonLat([lon, lat])),
      label: label || formatPair(lon, lat),
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
      fill: new ol.style.Fill({ color: "rgba(92, 58, 30, .16)" }),
      stroke: new ol.style.Stroke({ color: "#5c3a1e", width: 2.5, lineDash: [7, 5] }),
      image: new ol.style.Circle({
        radius: 4,
        fill: new ol.style.Fill({ color: "#5c3a1e" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 1.5 }),
      }),
      text: label ? new ol.style.Text({
        text: label,
        font: "600 12px ui-monospace, Menlo, monospace",
        fill: new ol.style.Fill({ color: "#3f2712" }),
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
      return { text: asArea(ol.sphere.getArea(geometry, opts)), kind: T("넓이") };
    }
    return { text: asLength(ol.sphere.getLength(geometry, opts)), kind: T("거리") };
  }

  function setMode(next) {
    mode = next;
    if (drawInteraction) {
      map.removeInteraction(drawInteraction);
      drawInteraction = null;
    }
    document.querySelectorAll(".tool[data-mode]").forEach(function (b) {
      b.classList.toggle("on", b.dataset.mode === next);
    });
    document.getElementById("map").style.cursor =
      next === "info" ? "" : "crosshair";
    updateToolOut();

    if (next === "box") {
      drawInteraction = rangeInteraction();
      map.addInteraction(drawInteraction);
      return;
    }
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

  // ── 범위잡기 ─────────────────────────────────────────────────────
  //
  // 누른 채 끌어 네모를 그리고, 손을 떼면 네 꼭짓점·중앙·넓이를 보인다.
  // 시료 채취 권역이나 도폭 밖 조사 범위를 적어 두는 자리다. **여럿을 잡아
  // 두고 "찍고 잰 것" 에 남긴다** — 재는 선은 하나만 두는 것과 다르다.
  // 저장하지 않는다. 남길 것은 "점묶음으로 저장" 으로 꼭짓점과 중앙을 올린다.

  function rangeStyle(feature) {
    return new ol.style.Style({
      fill: new ol.style.Fill({ color: "rgba(201, 162, 75, .14)" }),
      stroke: new ol.style.Stroke({ color: "#c9a24b", width: 2 }),
      text: new ol.style.Text({
        text: T("범위 {n}", { n: feature.get("no") }),
        font: "600 12px ui-monospace, Menlo, monospace",
        fill: new ol.style.Fill({ color: "#3f2712" }),
        stroke: new ol.style.Stroke({ color: "#fff", width: 4 }),
        overflow: true,
      }),
    });
  }

  function rangeInteraction() {
    // 누르고 끄는 동안은 지도가 끌리지 않는다 (DragBox 가 먼저 받는다)
    var box = new ol.interaction.DragBox({ condition: ol.events.condition.always, className: "range-box" });
    box.on("boxend", function () {
      var extent = box.getGeometry().getExtent();
      if (ol.extent.getWidth(extent) === 0 || ol.extent.getHeight(extent) === 0) return;
      addRange(extent);
    });
    return box;
  }

  /** 범위 하나의 수치. 넓이는 구면으로 잰다 — 3857 의 네모 넓이는 위도에
   *  따라 부풀어서, 우리나라에서는 1.5 배쯤 크게 나온다. */
  function rangeFacts(extent) {
    var sw = ol.proj.toLonLat([extent[0], extent[1]]);
    var ne = ol.proj.toLonLat([extent[2], extent[3]]);
    var w = sw[0], s = sw[1], e = ne[0], n = ne[1];
    var polygon = ol.geom.Polygon.fromExtent(extent);
    var opts = { projection: map.getView().getProjection() };
    return {
      nw: [w, n], ne: [e, n], se: [e, s], sw: [w, s],
      center: [(w + e) / 2, (s + n) / 2],
      area: ol.sphere.getArea(polygon, opts),
      // 가로는 가운데 위도에서 잰다. 위아래 변은 위도가 달라 길이가 다르다
      width: ol.sphere.getDistance([w, (s + n) / 2], [e, (s + n) / 2]),
      height: ol.sphere.getDistance([w, s], [w, n]),
    };
  }

  function rangeRows(f) {
    var rows = {};
    rows[T("북서")] = formatPair(f.nw[0], f.nw[1]);
    rows[T("북동")] = formatPair(f.ne[0], f.ne[1]);
    rows[T("남동")] = formatPair(f.se[0], f.se[1]);
    rows[T("남서")] = formatPair(f.sw[0], f.sw[1]);
    rows[T("중앙")] = formatPair(f.center[0], f.center[1]);
    rows[T("넓이")] = asArea(f.area);
    rows[T("가로 × 세로")] = asLength(f.width) + " × " + asLength(f.height);
    return rows;
  }

  function rangeText(feature) {
    var rows = rangeRows(rangeFacts(feature.getGeometry().getExtent()));
    return [T("범위 {n}", { n: feature.get("no") })].concat(Object.keys(rows).map(function (k) {
      return k + "\t" + rows[k];
    })).join("\n");
  }

  function addRange(extent) {
    rangeSeq += 1;
    var feature = new ol.Feature({ geometry: ol.geom.Polygon.fromExtent(extent), no: rangeSeq });
    rangeSource.addFeature(feature);
    renderTemp();
    showRange(feature);
  }

  function showRange(feature) {
    var extent = feature.getGeometry().getExtent();
    var facts = rangeFacts(extent);
    lastMeasure = T("범위 {n}", { n: feature.get("no") }) + " " + asArea(facts.area);
    var out = document.getElementById("measure-out");
    out.textContent = lastMeasure;
    out.classList.add("done");
    updateToolOut();
    // 팝업은 위경도의 한가운데에 띄운다 — 표의 "중앙" 과 첫 줄 위경도가 같아야 한다.
    // 지도 좌표(3857)의 한가운데는 위도가 몇 백만 분의 1 도 어긋난다
    showPopup(ol.proj.fromLonLat(facts.center),
              [{ title: T("범위 {n}", { n: feature.get("no") }), props: rangeRows(facts) }], "");
  }

  function showMeasure(got, done) {
    var out = document.getElementById("measure-out");
    out.textContent = got.kind + " " + got.text;
    out.classList.toggle("done", !!done);
    lastMeasure = got.kind + " " + got.text;
    updateToolOut();
  }

  /** 지도 위 손잡이 옆의 알림.
   *
   *  **재는 결과가 손잡이 곁에 있어야 한다.** 처음에는 왼쪽 패널에만
   *  적었는데, 손잡이를 누른 자리에서는 아무 일도 안 일어나는 것처럼
   *  보였다. 누른 곳에서 답이 나와야 한다. */
  function updateToolOut() {
    var out = document.getElementById("tool-out");
    var points = tempSource ? tempSource.getFeatures().length : 0;
    var bits = [];
    if (lastMeasure) bits.push(lastMeasure);
    if (points) bits.push(T("점 {n}개", { n: points }));
    if (mode === "point" && !points) bits.push(T("지도를 눌러 점을 찍는다"));
    if (mode === "line" && !lastMeasure) bits.push(T("눌러 가며 잇는다 · 두 번 누르면 끝"));
    if (mode === "area" && !lastMeasure) bits.push(T("눌러 가며 두른다 · 두 번 누르면 끝"));
    if (mode === "box" && !rangeSource.getFeatures().length) bits.push(T("누른 채 끌어 네모를 그린다"));
    out.textContent = bits.join("  ·  ");
    out.hidden = !bits.length;
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
    var ranges = rangeSource.getFeatures();
    setCount("count-temp", features.length + ranges.length);
    updateToolOut();
    host.innerHTML = "";
    ranges.forEach(function (feature) { host.appendChild(rangeItem(feature)); });
    if (!features.length && ranges.length) return;
    if (!features.length) {
      host.innerHTML = '<li class="empty">' + T("지도 오른쪽 위 <b>점</b> 도구로 찍는다") + "</li>";
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
      text.title = T("눌러서 복사한다");
      text.textContent = formatPair(feature.get("lon"), feature.get("lat"));
      text.addEventListener("click", function () {
        var value = text.textContent;
        copyText(value).then(function () {
          text.textContent = T("복사했다");
          setTimeout(function () { text.textContent = value; }, 700);
        });
      });

      var go = iconButton("⊙", T("이 점으로 이동"), false, function () {
        map.getView().animate({
          center: feature.getGeometry().getCoordinates(), duration: 300,
        });
      });
      var del = iconButton("×", T("지운다"), false, function () {
        tempSource.removeFeature(feature);
        renderTemp();
      });

      li.append(no, text, go, del);
      host.appendChild(li);
    });
  }

  function rangeItem(feature) {
    var li = document.createElement("li");
    li.className = "range-item";
    var no = document.createElement("span");
    no.className = "temp-no range";
    no.textContent = feature.get("no");
    var facts = rangeFacts(feature.getGeometry().getExtent());
    var text = document.createElement("button");
    text.type = "button";
    text.className = "temp-coord";
    text.title = T("눌러서 꼭짓점·중앙·넓이를 복사한다");
    text.textContent = asArea(facts.area) + " · " + formatPair(facts.center[0], facts.center[1]);
    text.addEventListener("click", function () {
      var value = text.textContent;
      copyText(rangeText(feature)).then(function () {
        text.textContent = T("복사했다");
        setTimeout(function () { text.textContent = value; }, 700);
      });
    });
    var go = iconButton("⊙", T("이 범위로 가서 수치를 본다"), false, function () {
      map.getView().fit(feature.getGeometry().getExtent(), { padding: [60, 60, 80, 60], duration: 300 });
      showRange(feature);
    });
    var del = iconButton("×", T("지운다"), false, function () {
      rangeSource.removeFeature(feature);
      renderTemp();
    });
    li.append(no, text, go, del);
    return li;
  }

  /** 찍어 둔 점을 **목록으로 저장한다.** 구글 지도의 "장소 저장" 과 같은 자리다.
   *
   *  임시 표시는 새로 고치면 사라진다. 그러다 "이건 남겨야겠다" 싶은 때가
   *  오는데, 그때 파일로 내보냈다 다시 올리게 하면 아무도 안 한다.
   *  있는 그대로 점묶음이 되게 했다.
   */
  /** 범위를 점묶음에 담을 때는 꼭짓점 넷과 중앙을 점으로 올린다.
   *  점묶음은 점만 받는다 — 면을 받게 되면 네모 그대로 올린다. */
  function rangePoints(ranges) {
    var out = [];
    ranges.forEach(function (feature) {
      var f = rangeFacts(feature.getGeometry().getExtent());
      var name = T("범위 {n}", { n: feature.get("no") });
      [["북서", f.nw], ["북동", f.ne], ["남동", f.se], ["남서", f.sw], ["중앙", f.center]].forEach(function (c) {
        out.push({ lat: c[1][1], lon: c[1][0], label: name + " " + T(c[0]) });
      });
    });
    return out;
  }

  function saveTemp() {
    var features = tempSource.getFeatures();
    var ranges = rangeSource.getFeatures();
    var msg = document.getElementById("save-msg");
    if (!features.length && !ranges.length) {
      msg.className = "msg bad";
      msg.textContent = T("저장할 점이 없다.");
      return;
    }
    var name = prompt(T("목록 이름"), T("찍은 점 {date}", { date: new Date().toLocaleDateString(LANG === "en" ? "en-GB" : "ko-KR") }));
    if (name === null) return;

    msg.className = "msg";
    msg.textContent = T("저장하는 중…");

    fetch(BASE + "pointsets/create/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf() },
      body: JSON.stringify({
        name: name,
        color: "#5c3a1e",
        points: features.map(function (f) {
          return { lat: f.get("lat"), lon: f.get("lon"), label: T("점 {n}", { n: f.get("no") }) };
        }).concat(rangePoints(ranges)),
      }),
    })
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) {
          msg.className = "msg bad";
          msg.textContent = res.d.error || T("저장하지 못했다");
          return;
        }
        pointsets.unshift(res.d.pointset);
        renderPointSets();
        // 저장했으니 임시 표시는 치운다. 같은 점이 두 겹으로 남으면 헷갈린다.
        tempSource.clear();
        tempSeq = 0;
        rangeSource.clear();
        rangeSeq = 0;
        renderTemp();
        msg.className = "msg good";
        msg.textContent = T("'{name}' 으로 저장했다.", { name: res.d.pointset.name });
      })
      .catch(function () {
        msg.className = "msg bad";
        msg.textContent = T("저장하지 못했다");
      });
  }

  function wireTools() {
    // **누른 손잡이를 다시 누르면 꺼진다.** 아무것도 안 켜져 있으면 속성을
    // 읽는 것이 기본이라, "속성 읽기" 단추를 따로 두지 않는다.
    document.querySelectorAll(".tool[data-mode]").forEach(function (button) {
      button.addEventListener("click", function () {
        setMode(mode === button.dataset.mode ? "info" : button.dataset.mode);
      });
    });
    document.getElementById("tool-clear").addEventListener("click", clearDrawn);
    document.getElementById("save-temp").addEventListener("click", saveTemp);
    document.getElementById("clear-temp").addEventListener("click", clearDrawn);
    renderTemp();
    setMode("info");
  }

  function clearDrawn() {
    tempSource.clear();
    measureSource.clear();
    foundSource.clear();
    rangeSource.clear();
    rangeSeq = 0;
    tempSeq = 0;
    lastMeasure = "";
    renderTemp();
    var out = document.getElementById("measure-out");
    out.textContent = T("아직 잰 것이 없다");
    out.classList.remove("done");
    updateToolOut();
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
          title: T("찍은 점 {n}", { n: feature.get("no") }),
          props: {
            "위도": feature.get("lat").toFixed(6),
            "경도": feature.get("lon").toFixed(6),
            "도분초": coordText(feature.get("lon"), feature.get("lat")),
          },
        });
        return;
      }
      parts.push({ title: feature.get("_점묶음") || T("내 자료"), props: plain(feature.getProperties()) });
    }, {
      hitTolerance: 5,
      // 찾아간 자리의 표식은 자료가 아니다. 거리·넓이 선도 그렇다
      layerFilter: function (layer) {
        return layer !== foundLayer && layer !== measureLayer && layer !== rangeLayer;
      },
    });

    var queryable = active.filter(function (e) {
      var row = byName[e.name];
      return row && row.queryable;
    });

    if (!queryable.length) {
      showPopup(evt.coordinate, parts, parts.length ? "" : T("켠 레이어가 없다"));
      return;
    }

    showPopup(evt.coordinate, parts, T("읽는 중…"));

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
            showPopup(evt.coordinate, all, all.length ? "" : T("이 자리에는 아무것도 없다"));
          }
        });
    });

    if (pending === 0) showPopup(evt.coordinate, parts, parts.length ? "" : T("이 자리에는 아무것도 없다"));
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
    head.title = T("눌러서 복사한다");
    var value = formatPair(ll[0], ll[1]);
    var lat = useDms ? dd2dms(ll[1], true) : ll[1].toFixed(6);
    var lon = useDms ? dd2dms(ll[0], false) : ll[0].toFixed(6);
    head.innerHTML =
      '<span class="k">' + esc(T("위도")) + '</span><span class="v">' + esc(lat) + "</span>" +
      '<span class="k">' + esc(T("경도")) + '</span><span class="v">' + esc(lon) + "</span>" +
      '<span class="copy">' + esc(T("복사")) + "</span>";
    head.addEventListener("click", function () {
      copyText(value).then(function () {
        head.classList.add("copied");
        head.querySelector(".copy").textContent = T("복사했다");
        setTimeout(function () {
          head.classList.remove("copied");
          head.querySelector(".copy").textContent = T("복사");
        }, 900);
      });
    });
    body.appendChild(head);

    // 주소는 VWorld 열쇠가 있을 때만 묻는다. 바다처럼 주소가 없는 자리면 줄을 두지 않는다
    if (vworldKey) {
      var addr = document.createElement("p");
      addr.className = "popup-addr";
      body.appendChild(addr);
      addressFor(ll[0], ll[1]).then(function (d) {
        var lines = [d.road, d.parcel && d.parcel !== d.road ? d.parcel : ""].filter(Boolean);
        if (lines.length) addr.textContent = lines.join(" · ");
        else addr.remove();
      });
    }

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
        var extras = 0;
        Object.keys(part.props).forEach(function (key) {
          var tr = document.createElement("tr");
          var th = document.createElement("th");
          th.textContent = T(key);
          tr.append(th, valueCell(part.props[key]));
          if (EXTRA_PROPS.indexOf(key) >= 0) {
            tr.className = "extra";
            extras += 1;
          }
          table.appendChild(tr);
        });
        table.classList.toggle("show-extra", showExtraProps);
        body.appendChild(table);
        if (extras) body.appendChild(extraToggle(table, extras));
      });
    }
    document.getElementById("popup").classList.add("on");
    document.getElementById("map-wrap").classList.add("popup-open");
    popupOverlay.setPosition(coordinate);
    // 속성이 늦게 와서 팝업이 자라도 자리는 그대로라 OL 이 다시 끌어오지
    // 않는다. 채운 뒤에 한 번 더 화면 안으로 끌어온다.
    popupOverlay.panIntoView({ animation: { duration: 200 }, margin: 72 });
  }

  /** 평소에는 접어 두는 속성. 사람이 읽을 것이 아니거나 다른 줄과 겹친다.
   *
   *  - `symnum` — 대표암상의 분류 번호로 보인다. 같은 쥐라기 화강암이면
   *    도폭이 달라도(`Jbgr` 무주 · `Jsgr` 뚝섬) 같은 값(101401)이다
   *  - `mapname` — 도폭 이름. `도폭` 줄에 이미 있다
   *  - `mapidx` — 도폭 번호(`GF20`). 도폭을 찾을 때만 쓴다
   *
   *  "모두 표시" 를 누르면 펼친다. 한 번 펼치면 다음 팝업에도 펼쳐 둔다. */
  var EXTRA_PROPS = ["symnum", "mapname", "mapidx"];
  var showExtraProps = false;

  function extraToggle(table, count) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "extra-toggle";
    b.dataset.count = count;
    b.addEventListener("click", function () {
      showExtraProps = !showExtraProps;
      syncExtra();
    });
    syncExtra(b);
    return b;
  }

  function syncExtra(only) {
    var buttons = only ? [only] : document.querySelectorAll("#popup-body .extra-toggle");
    buttons.forEach(function (b) {
      b.textContent = showExtraProps ? T("접기") : T("모두 표시 ({n})", { n: b.dataset.count });
    });
    if (only) return;
    document.querySelectorAll("#popup-body table").forEach(function (t) {
      t.classList.toggle("show-extra", showExtraProps);
    });
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

  /** 보이는 지도의 네 가장자리 위경도. 종이 지도의 테두리 눈금처럼 읽는다.
   *
   *  **커서 자리의 좌표는 없앴다.** 움직일 때마다 바뀌어 읽을 틈이 없고,
   *  누른 자리는 팝업 첫 줄이 이미 답한다. 대신 "지금 어디를 보고 있나" 를
   *  테두리에 적는다. 웹 메르카토르라 위도는 x 와, 경도는 y 와 무관하다 —
   *  가장자리 한가운데 한 점씩만 읽으면 된다. 아래쪽은 좌표 막대가 덮는
   *  만큼을 빼고 읽는다. */
  function renderEdges() {
    var size = map.getSize();
    if (!size) return;
    var w = size[0], h = size[1];
    var bar = document.getElementById("coordbar").offsetHeight || 0;
    var bottom = h - bar;
    function at(px, py) { return ol.proj.toLonLat(map.getCoordinateFromPixel([px, py])); }
    var n = at(w / 2, 0)[1];
    var s = at(w / 2, bottom)[1];
    var west = at(0, bottom / 2)[0];
    var east = at(w, bottom / 2)[0];
    function lat(v) { return useDms ? dd2dms(v, true) : Math.abs(v).toFixed(4) + "°" + (v >= 0 ? "N" : "S"); }
    function lon(v) { return useDms ? dd2dms(v, false) : Math.abs(v).toFixed(4) + "°" + (v >= 0 ? "E" : "W"); }
    document.getElementById("edge-n").textContent = lat(n);
    document.getElementById("edge-s").textContent = lat(s);
    document.getElementById("edge-w").textContent = lon(west);
    document.getElementById("edge-e").textContent = lon(east);
  }

  // ── 점묶음 ──────────────────────────────────────────────────────

  //: 이름표를 보이기 시작하는 줌. 이보다 멀리서 보면 글자가 점을 덮는다.
  var LABEL_MIN_ZOOM = 11;

  /** 점 하나의 모양. 가까이 보면 **이름표를 곁에 적는다** — 전에는 눌러야
   *  떴다. 겹치는 글자는 OL 이 걸러낸다(`declutter`). */
  function pointStyle(color) {
    var dot = new ol.style.Circle({
      radius: 5,
      fill: new ol.style.Fill({ color: color }),
      stroke: new ol.style.Stroke({ color: "#fff", width: 1.5 }),
    });
    var plain = new ol.style.Style({ image: dot });
    return function (feature, resolution) {
      var label = feature.get("이름표");
      var zoom = map.getView().getZoomForResolution(resolution);
      if (!label || zoom < LABEL_MIN_ZOOM) return plain;
      return new ol.style.Style({
        image: dot,
        text: new ol.style.Text({
          text: String(label),
          font: "12px sans-serif",
          offsetX: 8,
          textAlign: "left",
          fill: new ol.style.Fill({ color: "#1f1409" }),
          stroke: new ol.style.Stroke({ color: "rgba(255,255,255,0.9)", width: 3 }),
        }),
      });
    };
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
      declutter: true,
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
      host.innerHTML = '<li class="empty">' + T("왼쪽 위 <b>불러오기</b> 탭에서 올린다") + "</li>";
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
      count.textContent = T("{n}점", { n: ps.count });

      var zoom = iconButton("⊙", T("이 자료로 범위를 맞춘다"), false, function () {
        var source = pointLayers[ps.id] && pointLayers[ps.id].getSource();
        var extent = source && source.getExtent();
        if (extent && isFinite(extent[0])) {
          map.getView().fit(extent, { padding: [40, 40, 60, 40], maxZoom: 14, duration: 300 });
        }
      });

      // 올린 것을 GeoJSON 으로 돌려받는다. 원래 CSV 였어도 위경도와 속성이
      // 그대로 나온다 — QGIS 에 곧장 얹을 수 있다
      var save = iconButton("⤓", T("GeoJSON 으로 내려받는다"), false, function () {
        location.href = BASE + "pointsets/" + ps.id + "/geojson/?download=1";
      });

      var del = iconButton("×", T("지운다"), false, function () {
        if (!confirm(T("'{name}' 을 지운다.", { name: ps.name }))) return;
        post(BASE + "pointsets/" + ps.id + "/delete/").then(function () {
          if (pointLayers[ps.id]) {
            pointLayerGroup.getLayers().remove(pointLayers[ps.id]);
            delete pointLayers[ps.id];
          }
          pointsets = pointsets.filter(function (x) { return x.id !== ps.id; });
          renderPointSets();
        });
      });

      li.append(box, swatch, name, count, zoom, save, del);
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

  // ── 주제도 비교 ──────────────────────────────────────────────────
  //
  // 두 가지다. **밀어 보기**는 고른 레이어를 세로 막대의 왼쪽에만 그려,
  // 막대를 끌며 밑의 것과 견준다. 같은 자리를 두 주제도로 번갈아 보는 데
  // 좋다. **나란히**는 지도를 둘로 가른다 — 두 지도가 같은 보기(`ol.View`)를
  // 나눠 써서 함께 움직이고, 한쪽의 마우스 자리를 다른 쪽에 점으로 비춘다.
  // 투명도를 내려 겹치는 것만으로는 5만과 25만처럼 색이 비슷한 것을 가르기
  // 어렵다.

  var compareMode = "off";
  var swipePos = 0.5;                 // 막대의 자리. 지도 폭에 대한 비
  var swipeName = null;               // 막대 왼쪽에만 그리는 레이어
  var swipeKeys = [];
  var map2 = null, map2Layer = null, map2Base = null, map2Name = null;
  var mirror1 = null, mirror2 = null;

  function clipBefore(e) {
    var ctx = e.context;
    var size = map.getSize();
    var x = size[0] * swipePos;
    var tl = ol.render.getRenderPixel(e, [0, 0]);
    var tr = ol.render.getRenderPixel(e, [x, 0]);
    var bl = ol.render.getRenderPixel(e, [0, size[1]]);
    var br = ol.render.getRenderPixel(e, [x, size[1]]);
    ctx.save();
    ctx.beginPath();
    ctx.moveTo(tl[0], tl[1]);
    ctx.lineTo(bl[0], bl[1]);
    ctx.lineTo(br[0], br[1]);
    ctx.lineTo(tr[0], tr[1]);
    ctx.closePath();
    ctx.clip();
  }

  function clipAfter(e) { e.context.restore(); }

  function unclip() {
    swipeKeys.forEach(function (k) { ol.Observable.unByKey(k); });
    swipeKeys = [];
  }

  function applySwipe() {
    unclip();
    var entry = active.find(function (e) { return e.name === swipeName; });
    if (entry) {
      swipeKeys = [entry.layer.on("prerender", clipBefore), entry.layer.on("postrender", clipAfter)];
    }
    placeSwipeBar();
    map.render();
  }

  function placeSwipeBar() {
    var bar = document.getElementById("swipe");
    bar.hidden = compareMode !== "swipe";
    bar.style.left = (swipePos * 100) + "%";
  }

  function rightLayerTitle() {
    var row = byName[map2Name];
    return row ? row.title : "";
  }

  function buildMap2() {
    if (!map2) {
      map2 = new ol.Map({
        target: "map2",
        view: map.getView(),            // 같은 보기를 나눠 쓴다 — 함께 움직인다
        controls: [],
        layers: [],
      });
      mirror1 = mirrorOverlay(map);
      mirror2 = mirrorOverlay(map2);
      map.on("pointermove", function (e) { if (compareMode === "split") mirror2.setPosition(e.coordinate); });
      map2.on("pointermove", function (e) { if (compareMode === "split") mirror1.setPosition(e.coordinate); });
      map.getViewport().addEventListener("pointerleave", function () { mirror2.setPosition(undefined); });
      map2.getViewport().addEventListener("pointerleave", function () { mirror1.setPosition(undefined); });
    }
    if (map2Base) map2.removeLayer(map2Base);
    var spec = BASEMAPS[document.getElementById("basemap").value];
    map2Base = spec && spec.make ? spec.make() : null;
    if (map2Base) { map2Base.setZIndex(0); map2.addLayer(map2Base); }
    if (map2Layer) map2.removeLayer(map2Layer);
    map2Layer = null;
    if (map2Name && byName[map2Name]) {
      map2Layer = new ol.layer.Tile({ source: wmsSource(map2Name), opacity: DEFAULT_OPACITY, zIndex: 1 });
      map2.addLayer(map2Layer);
    }
    document.getElementById("split-right").textContent = rightLayerTitle();
    document.getElementById("split-left").textContent =
      active.length ? active.map(function (e) { return e.title; }).join(" · ") : T("켠 레이어가 없다");
  }

  /** 다른 쪽 지도의 마우스 자리를 비추는 작은 점. */
  function mirrorOverlay(target) {
    var el = document.createElement("div");
    el.className = "mirror-dot";
    var overlay = new ol.Overlay({ element: el, positioning: "center-center", stopEvent: false });
    target.addOverlay(overlay);
    return overlay;
  }

  function setCompare(mode) {
    compareMode = mode;
    document.querySelectorAll("#compare-mode button").forEach(function (b) {
      b.classList.toggle("on", b.dataset.cmp === mode);
    });
    var wrap = document.getElementById("map-wrap");
    wrap.classList.toggle("split", mode === "split");
    document.getElementById("map2").hidden = mode !== "split";
    if (mode !== "swipe") unclip();
    if (mode === "split") buildMap2();
    if (mode !== "split" && mirror1) { mirror1.setPosition(undefined); mirror2.setPosition(undefined); }
    refreshCompare();
    // 지도 칸의 폭이 바뀌었으니 다시 잰다
    setTimeout(function () { map.updateSize(); if (map2) map2.updateSize(); }, 0);
  }

  /** 비교 칸의 고르개를 지금 켠 레이어에 맞춘다. restack 이 부른다. */
  function refreshCompare() {
    var pick = document.getElementById("compare-pick");
    var wrap = document.getElementById("compare-pick-wrap");
    var hint = document.getElementById("compare-hint");
    if (!pick) return;
    wrap.hidden = compareMode === "off";
    hint.textContent = compareMode === "swipe" ? T("고른 레이어가 막대 왼쪽에만 보인다. 막대를 끌어 견준다.")
      : compareMode === "split" ? T("왼쪽은 켠 레이어, 오른쪽은 고른 레이어. 두 지도가 함께 움직인다.")
      : "";
    pick.innerHTML = "";
    if (compareMode === "swipe") {
      document.getElementById("compare-pick-label").textContent = T("막대 왼쪽");
      if (!active.some(function (e) { return e.name === swipeName; })) {
        swipeName = active.length ? active[0].name : null;
      }
      active.forEach(function (e) {
        var o = document.createElement("option");
        o.value = e.name; o.textContent = e.title;
        pick.appendChild(o);
      });
      if (active.length < 2) hint.textContent = T("먼저 레이어를 둘 이상 켠다.");
      pick.value = swipeName || "";
      applySwipe();
    } else if (compareMode === "split") {
      document.getElementById("compare-pick-label").textContent = T("오른쪽");
      if (!map2Name || !byName[map2Name]) {
        map2Name = active.length > 1 ? active[1].name
          : (byName["L_250K_Geology_Map"] ? "L_250K_Geology_Map" : Object.keys(byName)[0]);
      }
      catalog.forEach(function (group) {
        var og = document.createElement("optgroup");
        og.label = group.name;
        group.layers.forEach(function (l) {
          var o = document.createElement("option");
          o.value = l.name; o.textContent = l.title;
          og.appendChild(o);
        });
        pick.appendChild(og);
      });
      pick.value = map2Name;
      buildMap2();
      placeSwipeBar();
    } else {
      placeSwipeBar();
    }
  }

  function wireCompare() {
    document.querySelectorAll("#compare-mode button").forEach(function (b) {
      b.addEventListener("click", function () { setCompare(b.dataset.cmp); });
    });
    document.getElementById("compare-pick").addEventListener("change", function () {
      if (compareMode === "swipe") { swipeName = this.value; applySwipe(); }
      if (compareMode === "split") { map2Name = this.value; buildMap2(); }
    });
    document.getElementById("basemap").addEventListener("change", function () {
      if (compareMode === "split") buildMap2();
    });
    // 막대 끌기. 손잡이만이 아니라 막대 어디를 잡아도 된다
    var bar = document.getElementById("swipe");
    var dragging = false;
    bar.addEventListener("pointerdown", function (e) {
      dragging = true;
      bar.setPointerCapture(e.pointerId);
      e.preventDefault();
    });
    bar.addEventListener("pointermove", function (e) {
      if (!dragging) return;
      var box = document.getElementById("map").getBoundingClientRect();
      swipePos = Math.min(0.98, Math.max(0.02, (e.clientX - box.left) / box.width));
      placeSwipeBar();
      map.render();
    });
    bar.addEventListener("pointerup", function () { dragging = false; });
    setCompare("off");
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

  // ── 모양 고르기 — 이 브라우저에만 남는다 ─────────────────────────
  //
  // 서버로 보내지 않는다. 고른 사람의 눈에만 걸린 일이고, 저장하려면
  // 계정이 있어야 하는데 이 뷰어에는 계정이 없다.

  var LOOKS = [
    { key: "theme", attr: "data-theme", store: "gsm.theme", fallback: "brown", sel: "#opt-theme" },
    { key: "font", attr: "data-font", store: "gsm.font", fallback: "sans", sel: "#opt-font" },
    { key: "size", attr: "data-size", store: "gsm.size", fallback: "m", sel: "#opt-size" },
  ];

  /** 고르개에 없는 값이 남아 있으면 기본으로 돌린다. 앞 판의
   *  `auto`·`dark` 가 이 브라우저에 남아 있을 수 있다. */
  function readLook(spec) {
    var value;
    try { value = localStorage.getItem(spec.store); } catch (e) { value = null; }
    var known = Array.prototype.some.call(
      document.querySelectorAll(spec.sel + " button"),
      function (b) { return b.dataset[spec.key] === value; });
    return known ? value : spec.fallback;
  }

  function applyLook(spec, value) {
    document.documentElement.setAttribute(spec.attr, value);
    try { localStorage.setItem(spec.store, value); } catch (e) { /* 사생활 모드 */ }
    document.querySelectorAll(spec.sel + " button").forEach(function (b) {
      b.classList.toggle("on", b.dataset[spec.key] === value);
    });
  }

  /** 설정 창을 열기 전에도 걸어 둔다 — 창을 한 번도 안 연 사람도
   *  지난번에 고른 모양으로 보아야 한다. */
  function initLooks() {
    LOOKS.forEach(function (spec) { applyLook(spec, readLook(spec)); });
  }

  function wireLooks() {
    LOOKS.forEach(function (spec) {
      document.querySelectorAll(spec.sel + " button").forEach(function (button) {
        button.addEventListener("click", function () {
          applyLook(spec, button.dataset[spec.key]);
        });
      });
    });
  }

  /** 한국어·영어. 화면 틀을 서버가 그리므로 **쿠키로 서버에 알리고 다시
   *  읽는다.** 쿠키에는 `ko`·`en` 두 글자만 담긴다. */
  function wireLang() {
    document.querySelectorAll("#opt-lang button").forEach(function (b) {
      b.classList.toggle("on", b.dataset.lang === LANG);
      b.addEventListener("click", function () {
        if (b.dataset.lang === LANG) return;
        document.cookie = "gsm_lang=" + b.dataset.lang + "; path=/; max-age=31536000; SameSite=Lax";
        location.reload();
      });
    });
  }

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
          document.getElementById("notes").textContent = T("판 이력을 읽지 못했다.");
        });
    }

    function close() { sheet.hidden = true; }

    document.getElementById("gear").addEventListener("click", open);
    document.getElementById("settings-close").addEventListener("click", close);
    sheet.addEventListener("click", function (e) { if (e.target === sheet) close(); });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && !sheet.hidden) close();
    });

    document.querySelectorAll(".stab").forEach(function (tab) {
      tab.addEventListener("click", function () {
        document.querySelectorAll(".stab").forEach(function (t) { t.classList.remove("on"); });
        document.querySelectorAll(".stabbody").forEach(function (b) { b.classList.remove("on"); });
        tab.classList.add("on");
        document.getElementById("stab-" + tab.dataset.stab).classList.add("on");
      });
    });

    wireLooks();
    wireLang();
  }

  /** 지금 무엇으로 돌고 있는지. 화면을 보고 상태를 물어오는 일이 잦아 둔다. */
  function renderState() {
    var rows = [
      [T("배경지도"), (BASEMAPS[document.getElementById("basemap").value] || {}).title || T("없음")],
      [T("켠 레이어"), active.length ? active.map(function (e) { return e.title; }).join(", ") : T("없음")],
      [T("찍은 점"), T("{n}개", { n: tempSource.getFeatures().length })],
      [T("올린 자료"), T("{n}묶음", { n: pointsets.length })],
      [T("좌표 표기"), useDms ? T("도분초") : T("십진도")],
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
      host.textContent = T("아직 적힌 판이 없다.");
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

  function wireCoordBar() {
    document.getElementById("dms-toggle").addEventListener("click", function () {
      useDms = !useDms;
      this.classList.toggle("on", useDms);
      renderEdges();
    });

    var input = document.getElementById("goto-input");
    document.getElementById("goto-form").addEventListener("submit", function (e) {
      e.preventDefault();
      var q = input.value.trim();
      if (!q) return;
      // 목록이 떠 있고 하나를 골라 두었으면 그리로 간다
      var picked = document.querySelector("#search-results li.on");
      if (picked) { picked.click(); return; }
      // **좌표가 먼저다.** 좌표로 읽히면 곧장 가고, 아니면 주소·장소로 찾는다
      fetch(BASE + "coords/parse/?q=" + encodeURIComponent(q))
        .then(function (r) { return r.ok ? r.json() : Promise.reject(); })
        .then(function (d) { closeResults(); goTo(d.lat, d.lon); })
        .catch(function () { searchPlaces(q); });
    });
    input.addEventListener("input", closeResults);
    input.addEventListener("keydown", function (e) {
      var items = Array.prototype.slice.call(document.querySelectorAll("#search-results li[data-i]"));
      if (!items.length) return;
      var at = items.findIndex(function (li) { return li.classList.contains("on"); });
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        at = e.key === "ArrowDown" ? Math.min(items.length - 1, at + 1) : Math.max(0, at - 1);
        items.forEach(function (li, i) { li.classList.toggle("on", i === at); });
        items[at].scrollIntoView({ block: "nearest" });
      } else if (e.key === "Escape") {
        closeResults();
      }
    });
    document.addEventListener("click", function (e) {
      if (!e.target.closest("#coordbar")) closeResults();
    });
  }

  // ── 주소·장소 찾기 (VWorld) ──────────────────────────────────────
  //
  // 서버의 `search/` 가 VWorld 에 묻는다. KIGAM 은 타지 않는다. 이름이 같은
  // 곳이 많아(가정동은 대전에도 인천에도 있다) **곧장 가지 않고 목록을
  // 띄운다.** 사람이 고른다.

  var KIND = { district: "행정구역", road: "도로명", parcel: "지번", place: "장소" };

  function closeResults() {
    var box = document.getElementById("search-results");
    box.hidden = true;
    box.innerHTML = "";
  }

  function searchPlaces(q) {
    var box = document.getElementById("search-results");
    box.hidden = false;
    box.innerHTML = '<li class="note">' + esc(T("찾는 중…")) + "</li>";
    fetch(BASE + "search/?q=" + encodeURIComponent(q))
      .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
      .then(function (res) {
        if (!res.ok) throw new Error(res.d.error || "");
        renderResults(res.d.results || []);
      })
      .catch(function (err) {
        box.innerHTML = '<li class="note">' + esc(err.message || T("찾지 못했다")) + "</li>";
      });
  }

  function renderResults(rows) {
    var box = document.getElementById("search-results");
    box.innerHTML = "";
    if (!rows.length) {
      box.innerHTML = '<li class="note">' + esc(T("찾은 것이 없다 — 주소·장소·행정구역을 넣어 본다")) + "</li>";
      return;
    }
    rows.forEach(function (row, i) {
      var li = document.createElement("li");
      li.dataset.i = i;
      li.innerHTML = '<span class="kind">' + esc(T(KIND[row.kind] || row.kind)) + "</span>" +
        '<span class="title">' + esc(row.title) + "</span>" +
        (row.sub ? '<span class="sub">' + esc(row.sub) + "</span>" : "");
      li.addEventListener("click", function () {
        closeResults();
        goTo(row.lat, row.lon, row.kind === "place" ? row.title : row.title.replace(/\s*\(.*\)$/, ""));
      });
      li.addEventListener("mouseenter", function () {
        box.querySelectorAll("li").forEach(function (x) { x.classList.toggle("on", x === li); });
      });
      box.appendChild(li);
    });
    var note = document.createElement("li");
    note.className = "note src";
    note.textContent = T("주소 검색: VWorld (국토지리정보원)");
    box.appendChild(note);
  }

  // 팝업 첫 줄 밑의 주소. 같은 자리를 여러 번 누르므로 브라우저에도 들고 있는다.
  var addressMemo = {};

  function addressFor(lon, lat) {
    var key = lat.toFixed(5) + "," + lon.toFixed(5);
    if (!addressMemo[key]) {
      addressMemo[key] = fetch(BASE + "whereis/?lat=" + lat.toFixed(5) + "&lon=" + lon.toFixed(5))
        .then(function (r) { return r.ok ? r.json() : {}; })
        .catch(function () { return {}; });
    }
    return addressMemo[key];
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
      msg.textContent = T("읽는 중…");

      post(BASE + "pointsets/upload/", data)
        .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, d: d }; }); })
        .then(function (res) {
          if (!res.ok) {
            msg.className = "msg bad";
            msg.textContent = res.d.error || T("올리지 못했다");
            return;
          }
          pointsets.unshift(res.d.pointset);
          renderPointSets();
          msg.className = "msg good";
          msg.textContent = T("{n}점을 올렸다.", { n: res.d.pointset.count }) +
            (res.d.notes && res.d.notes.length ? " " + res.d.notes.join(" / ") : "");
          form.reset();
          var box = file.closest(".filebox");
          box.classList.remove("has");
          box.querySelector("span").textContent = T("CSV · GeoJSON 고르기");
        })
        .catch(function () {
          msg.className = "msg bad";
          msg.textContent = T("올리지 못했다");
        });
    });
  }

  function wirePopup() {
    document.getElementById("popup-close").addEventListener("click", function () {
      document.getElementById("popup").classList.remove("on");
      document.getElementById("map-wrap").classList.remove("popup-open");
      popupOverlay.setPosition(undefined);
    });
  }

  function esc(text) {
    return String(text).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  /** 클립보드에 넣는다. 됐으면 풀리고 못 했으면 거절되는 Promise.
   *
   *  **`navigator.clipboard` 는 https 나 localhost 에서만 있다.** 운영은
   *  `http://paleolab` 이라 그것이 아예 없어서, 앞 판에서는 복사를 눌러도
   *  아무 일 없이 넘어갔다. 그때는 옛 길(`execCommand("copy")`)로 간다 —
   *  낡았다고 적혀 있지만 모든 브라우저가 아직 받는다. 누른 그 순간에
   *  불러야 하므로 이 함수는 클릭 처리기 안에서 곧장 부른다. */
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

  function cssEscape(text) {
    return String(text).replace(/["\\]/g, "\\$&");
  }

  initLooks();
  initMap();
  wireBasemap();
  wireCompare();
  renderCatalog();
  renderActive();
  renderPointSets();
  wireTools();
  wireSettings();
  wireTabs();
  wireCoordBar();
  wireUpload();
  wirePopup();

  // 처음 열면 5만 지질도를 켜 둔다. 빈 지도보다 무엇이든 보이는 편이 낫고,
  // **5만이 실제로 가장 많이 보는 축척이다.** 100만·25만은 켜서 보는 것이지
  // 켜 두고 시작할 것이 아니다. 기억한 것이 있으면 그것을 따른다 — 다 끄고
  // 떠났으면 다 꺼진 채로 연다.
  if (!restoreState() && byName["L_50K_Geology_Map"]) {
    var box = document.querySelector('input[data-layer="L_50K_Geology_Map"]');
    if (box) { box.checked = true; }
    addLayer("L_50K_Geology_Map");
  }

  // ── 대기 화면 ────────────────────────────────────────────────────
  //
  // **덜 그려진 지도를 보이지 않는다.** 첫 타일이 다 그려질 때
  // (`rendercomplete`) 걷는다. 너무 빨리 걷히면 깜빡이는 것처럼 보여서
  // 적어도 한 바퀴(1.2 초)는 보이고, 상류가 느려 타일이 끝내 안 와도
  // 12 초 뒤에는 걷는다 — 지도 말고 나머지는 쓸 수 있어야 한다.
  (function () {
    var splash = document.getElementById("splash");
    if (!splash) return;
    var shownAt = Date.now();
    var done = false;
    function lift() {
      if (done) return;
      done = true;
      var wait = Math.max(0, 1200 - (Date.now() - shownAt));
      setTimeout(function () {
        splash.classList.add("gone");
        setTimeout(function () { splash.remove(); }, 600);
      }, wait);
    }
    map.once("rendercomplete", lift);
    setTimeout(lift, 12000);
  })();
})();
