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
  var catalog = JSON.parse(document.getElementById("catalog-data").textContent || "[]");
  var pointsets = JSON.parse(document.getElementById("pointset-data").textContent || "[]");

  var map, popupOverlay, pointLayerGroup;
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

  function initMap() {
    pointLayerGroup = new ol.layer.Group({ layers: [] });

    map = new ol.Map({
      target: "map",
      layers: [
        new ol.layer.Tile({ source: new ol.source.OSM(), opacity: 0.55 }),
        pointLayerGroup,
      ],
      view: new ol.View({
        // 남한 전체가 들어오는 자리
        center: ol.proj.fromLonLat([127.8, 36.2]),
        zoom: 7,
        minZoom: 5,
        maxZoom: 19,
      }),
      controls: ol.control.defaults.defaults({ attributionOptions: { collapsible: true } })
        .extend([new ol.control.ScaleLine()]),
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
    var baseCount = 1;   // OSM
    active.slice().reverse().forEach(function (entry, index) {
      entry.layer.setZIndex(baseCount + index);
      entry.layer.set("gsm", true);
      map.getLayers().insertAt(baseCount + index, entry.layer);
    });
    pointLayerGroup.setZIndex(500);
    renderActive();
  }

  function addLayer(name) {
    if (active.some(function (e) { return e.name === name; })) return;
    var row = byName[name];
    if (!row) return;
    active.unshift({
      name: name,
      title: row.title,
      opacity: 1,
      legendOpen: false,
      layer: new ol.layer.Tile({ source: wmsSource(name), opacity: 1 }),
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

  function renderActive() {
    var host = document.getElementById("active-list");
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

  // ── 클릭해 속성 읽기 ────────────────────────────────────────────

  function onClick(evt) {
    var parts = [];

    // 내 점이 먼저다 — 눌러서 맞힌 것이 분명하기 때문이다
    map.forEachFeatureAtPixel(evt.pixel, function (feature) {
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
    if (!parts.length) {
      body.innerHTML = '<p class="none">' + esc(emptyText || "") + "</p>";
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
          var td = document.createElement("td");
          td.textContent = String(part.props[key]);
          tr.append(th, td);
          table.appendChild(tr);
        });
        body.appendChild(table);
      });
    }
    document.getElementById("popup").classList.add("on");
    popupOverlay.setPosition(coordinate);
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
          map.getView().animate({
            center: ol.proj.fromLonLat([d.lon, d.lat]), zoom: 13, duration: 400,
          });
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
  renderCatalog();
  renderActive();
  renderPointSets();
  wireTabs();
  wireFilter();
  wireCoordBar();
  wireUpload();
  wirePopup();

  // 처음 열면 25만 지질도를 켜 둔다 — 빈 지도보다 무엇이든 보이는 편이 낫다
  if (byName["L_250K_Geology_Map"]) {
    var box = document.querySelector('input[data-layer="L_250K_Geology_Map"]');
    if (box) { box.checked = true; }
    addLayer("L_250K_Geology_Map");
  }
})();
