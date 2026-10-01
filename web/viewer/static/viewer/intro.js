/* 대돌여지도 소개 (wetherilli 113).
 *
 * 장면(`section.scene`)마다 무대가 화면에 붙어 있고, 스크롤이 장면 안의 진행 `--p`(0→1)와
 * 단계(`data-step`)를 민다. 단계가 바뀌면 그 단계의 글·그림에 `.on` 을 단다.
 * 지금 장면(또는 단계)이 적은 테마와 목적지를 바탕색과 "지도로 바로 가기" 에 옮긴다.
 *
 * 글은 모두 템플릿이 적는다 — 여기에는 화면 문장이 없다.
 */
(function () {
  "use strict";

  var BASE = location.pathname.replace(/\/*$/, "/");
  var scenes = Array.prototype.slice.call(document.querySelectorAll(".scene, .doors-wrap"));
  var skip = document.getElementById("skip");
  var skipTo = document.getElementById("skip-to");
  var chapters = Array.prototype.slice.call(document.querySelectorAll("#chapters a"));

  scenes.forEach(function (s) {
    if (s.dataset.steps) s.style.setProperty("--steps", s.dataset.steps);
  });

  /** `data-step="0 1"` 처럼 여러 단계에 걸친 것도 있다. */
  function inStep(el, step) {
    return (" " + el.dataset.step + " ").indexOf(" " + step + " ") >= 0;
  }

  /** 장면 안의 진행 0→1 — 무대가 화면에 붙어 있는 동안만 움직인다. */
  function progress(s) {
    var r = s.getBoundingClientRect();
    var run = r.height - innerHeight;
    if (run <= 0) return r.top < innerHeight / 2 ? 1 : 0;
    return Math.max(0, Math.min(1, -r.top / run));
  }

  var current = null, ticking = false;

  function update() {
    ticking = false;
    var mid = innerHeight / 2, active = scenes[0];
    scenes.forEach(function (s) {
      var r = s.getBoundingClientRect();
      if (r.top <= mid && r.bottom > mid) active = s;
      if (r.bottom < -innerHeight || r.top > innerHeight * 2) return;   // 먼 장면은 셈하지 않는다
      var p = progress(s);
      s.style.setProperty("--p", p.toFixed(4));
      var steps = +s.dataset.steps || 0;
      if (!steps) return;
      var step = Math.min(steps - 1, Math.floor(p * steps * 0.999));
      if (s.dataset.step === String(step)) return;
      s.dataset.step = step;
      s.querySelectorAll("[data-step]").forEach(function (el) {
        el.classList.toggle("on", inStep(el, step));
      });
    });
    // 테마·목적지 — 지금 단계의 것이 장면의 것을 이긴다
    var theme = active.dataset.theme, go = active.dataset.go, label = active.dataset.goLabel;
    active.querySelectorAll("[data-step].on").forEach(function (el) {
      if (el.dataset.theme) theme = el.dataset.theme;
      if (el.dataset.go) { go = el.dataset.go; label = el.dataset.goLabel; }
    });
    theme = theme || "korea";
    if (document.body.dataset.theme !== theme) document.body.dataset.theme = theme;
    var href = BASE + (go || "map/");
    if (skip.getAttribute("href") !== href) {
      skip.setAttribute("href", href);
      skipTo.textContent = label || "";
    }
    if (active !== current) {
      current = active;
      chapters.forEach(function (a) {
        a.classList.toggle("on", a.dataset.for.split(" ").indexOf(active.id) >= 0);
      });
    }
  }

  function wake() {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  }
  addEventListener("scroll", wake, { passive: true });
  addEventListener("resize", wake);
  update();

  // ── 자동 재생 ──────────────────────────────────────────────────
  //
  // 스크롤하지 않아도 넘어간다. 멈출 자리(stop)는 장면의 단계마다 하나 — 단계 k 의 가운데
  // `(k + .5) / 단계 수` 이고, 첫 장면처럼 움직임이 스크롤에 걸린 것은 `data-stops` 로 적는다.
  // 자리마다 **보이는 글의 길이만큼** 머문다(읽을 틈). 넘어갈 때는 스크롤을 부드럽게 민다 —
  // 장면의 움직임이 스크롤에 걸려 있으니 그대로 재생된다.
  // 사람이 휠·터치·키·스크롤 막대로 움직이면 멈춘다. 단추로 다시 켠다.

  var EN = document.documentElement.lang === "en";
  var still = matchMedia("(prefers-reduced-motion: reduce)").matches;
  var play = document.getElementById("play");
  var stops = [];

  function measure() {
    stops = [];
    scenes.forEach(function (s) {
      var top = s.getBoundingClientRect().top + scrollY;
      var run = Math.max(0, s.offsetHeight - innerHeight);
      var steps = +s.dataset.steps || 0;
      var fs = s.dataset.stops ? s.dataset.stops.split(" ").map(Number)
             : steps ? Array.apply(null, Array(steps)).map(function (_, k) { return (k + .5) / steps; })
             : [0];
      fs.forEach(function (f) { stops.push({ scene: s, y: Math.round(top + run * f) }); });
    });
  }

  /** 그 자리에서 읽을 글자 수로 머무는 시간을 정한다. 한국어는 한 글자가 영어보다 무겁다. */
  function dwell(stop) {
    var s = stop.scene, text = "";
    s.querySelectorAll("h1, h2, h3, p, li, figcaption").forEach(function (el) {
      if (el.closest(".src") || el.closest(".badge")) return;
      if (!el.offsetParent) return;
      // 단계에 걸린 글은 `.on` 으로 본다 — 막 뜨는 중이라 아직 흐릴 수 있다.
      // 스크롤에 걸린 것(첫 장면의 종이·물음)은 지금의 투명도로 본다
      var gated = el.closest("[data-step]");
      if (gated && gated !== s) { if (!gated.classList.contains("on")) return; }
      else if (+getComputedStyle(el.closest(".paper, .hook-text, .resolve") || el).opacity < .5) return;
      text += el.textContent.replace(/\s+/g, " ");
    });
    if (s.classList.contains("doors-wrap")) return 0;
    var ms = 1800 + text.length * (EN ? 32 : 70);
    return Math.max(3200, Math.min(12000, ms));
  }

  var playing = false, idx = 0, timer = 0, raf = 0, expectY = null;

  function setPlaying(on) {
    playing = on;
    play.setAttribute("aria-pressed", on ? "true" : "false");
    play.querySelector(".play-label").textContent = on ? play.dataset.pause : play.dataset.play;
    play.style.setProperty("--t", 0);
    cancelAnimationFrame(raf);
    clearTimeout(timer);
    if (on) go(nextIndex());
  }

  /** 지금 자리에서 가장 가까운 앞쪽 멈출 자리. */
  function nextIndex() {
    for (var i = 0; i < stops.length; i++) if (stops[i].y >= scrollY - 4) return i;
    return stops.length - 1;
  }

  function scrollToY(y) {
    expectY = y;
    scrollTo({ top: y, behavior: "instant" });
  }

  /** i 번째 자리로 부드럽게 가서 머문 뒤 다음으로. */
  function go(i) {
    idx = i;
    var from = scrollY, to = stops[i].y, d = to - from;
    var dur = still ? 0 : Math.max(900, Math.min(2400, Math.abs(d) / innerHeight * 750));
    var t0 = performance.now();
    function step(now) {
      var t = dur ? Math.min(1, (now - t0) / dur) : 1;
      var e = t < .5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
      scrollToY(Math.round(from + d * e));
      if (t < 1) raf = requestAnimationFrame(step);
      else { update(); stay(); }
    }
    raf = requestAnimationFrame(step);
  }

  function stay() {
    var last = idx >= stops.length - 1;
    var ms = dwell(stops[idx]);
    if (last || !ms) { setPlaying(false); return; }
    var spent = 0, prev = performance.now();
    function tick(now) {
      if (!document.hidden) spent += now - prev;       // 다른 탭에 있는 동안은 세지 않는다
      prev = now;
      play.style.setProperty("--t", Math.min(1, spent / ms).toFixed(3));
      if (spent >= ms) { play.style.setProperty("--t", 0); go(idx + 1); }
      else raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);
  }

  function interrupt() { if (playing) setPlaying(false); }
  addEventListener("wheel", interrupt, { passive: true });
  addEventListener("touchstart", interrupt, { passive: true });
  addEventListener("keydown", function (e) {
    if (["ArrowDown", "ArrowUp", "PageDown", "PageUp", "Home", "End", " "].indexOf(e.key) >= 0) interrupt();
  });
  // 스크롤 막대를 끈 것 — 우리가 민 자리와 다르면 사람이 움직인 것이다
  addEventListener("scroll", function () {
    if (playing && expectY !== null && Math.abs(scrollY - expectY) > 3) interrupt();
  }, { passive: true });
  addEventListener("resize", function () {
    measure();
    if (playing) setPlaying(true);
  });

  play.addEventListener("click", function () {
    if (playing) { setPlaying(false); return; }
    // 끝에서 다시 누르면 처음부터
    if (nextIndex() >= stops.length - 1 && scrollY >= stops[stops.length - 1].y - 4) scrollToY(0);
    setPlaying(true);
  });

  // 장면 막대 — 그 장면의 첫 자리로 간다. 재생 중이면 거기서 이어 간다
  chapters.forEach(function (a) {
    a.addEventListener("click", function (e) {
      var target = document.getElementById(a.getAttribute("href").slice(1));
      var i = stops.findIndex(function (st) { return st.scene === target; });
      if (i < 0) return;
      e.preventDefault();
      cancelAnimationFrame(raf);
      if (playing) { go(i); return; }
      scrollToY(stops[i].y);
    });
  });

  measure();
  // 처음 열었을 때만 저절로 — 이미 내려가 있는 자리(새로 고침)에서는 그 자리에서 이어 간다
  setPlaying(true);

  // 언어 — 지도 화면과 같은 쿠키다(`gsm_lang`)
  document.querySelectorAll(".langs button").forEach(function (b) {
    b.addEventListener("click", function () {
      document.cookie = "gsm_lang=" + b.dataset.lang + "; path=/; max-age=31536000; SameSite=Lax";
      location.reload();
    });
  });
})();
