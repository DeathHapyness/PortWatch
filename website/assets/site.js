/*!
 * PortWatch — orquestração de animação (vanilla, zero dependências)
 * Substitui o antigo motor Anime.js; mantém o mesmo visual e marcadores.
 * Sem nenhuma biblioteca externa: IntersectionObserver + rAF + estilos
 * inline determinísticos. Garantia: sem JS ou em erro, tudo fica visível
 * via classe failsafe + fallbacks CSS (html:not(.js)).
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduceMQ = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  var reduceMotion = !!(reduceMQ && reduceMQ.matches);
  var mobileMQ = window.matchMedia ? window.matchMedia("(max-width: 860px)") : null;
  var mobile = !!(mobileMQ && mobileMQ.matches);

  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }
  function on(el, ev, fn, opts) { el.addEventListener(ev, fn, opts || false); }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function seg(p, a, b) { return clamp((p - a) / (b - a || 1), 0, 1); }
  function ease(t) { return t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2; } /* easeInOutQuad */
  function lerp(a, b, t) { return a + (b - a) * t; }
  function rand(a, b) { return a + Math.random() * (b - a); }

  /* =========================================================
     Menu mobile
     ========================================================= */
  (function menu() {
    var btn = document.getElementById("menuBtn");
    var nav = document.getElementById("navLinks");
    if (!btn || !nav) return;
    on(btn, "click", function () {
      var open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
      btn.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
    });
    on(nav, "click", function (e) {
      var a = e.target && e.target.closest && e.target.closest("a");
      if (a) { nav.classList.remove("open"); btn.setAttribute("aria-expanded", "false"); }
    });
  })();

  /* =========================================================
     Nav-spy (IntersectionObserver)
     ========================================================= */
  (function navSpy() {
    var anchors = qsa("nav.links a");
    var secs = qsa("main section[id]");
    if (!("IntersectionObserver" in window) || !secs.length) return;
    var map = {};
    anchors.forEach(function (a) { var h = a.getAttribute("href") || ""; if (h.charAt(0) === "#") map[h.slice(1)] = a; });
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var link = map[en.target.id];
        if (!link) return;
        anchors.forEach(function (a) { a.classList.remove("active"); });
        link.classList.add("active");
      });
    }, { rootMargin: "-35% 0px -55% 0px", threshold: 0 });
    secs.forEach(function (s) { obs.observe(s); });
  })();

  /* =========================================================
     Navbar scrolled
     ========================================================= */
  (function navScrolled() {
    var nav = qs("header.nav");
    if (!nav) return;
    var ticking = false;
    function update() { nav.classList.toggle("scrolled", window.scrollY > 24); ticking = false; }
    on(window, "scroll", function () { if (!ticking) { window.requestAnimationFrame(update); ticking = true; } }, { passive: true });
    update();
  })();

  /* =========================================================
     Contadores [data-count] / [data-kpi-count]
     ========================================================= */
  var countedOnce = new WeakSet ? new WeakSet() : null;
  function animateCount(el) {
    if (countedOnce) { if (countedOnce.has(el)) return; countedOnce.add(el); }
    var isKpi = el.hasAttribute("data-kpi-count");
    var target = parseFloat(el.getAttribute("data-count") || el.getAttribute("data-kpi-count")) || 0;
    var from = parseFloat(el.getAttribute("data-from")) || 0;
    var suffix = el.getAttribute("data-suffix") || "";
    var duration = 1200, start = null, textNode = null;
    if (isKpi) {
      if (!el.firstChild || el.firstChild.nodeType !== 3) { textNode = document.createTextNode(String(Math.round(from))); el.insertBefore(textNode, el.firstChild); }
      else textNode = el.firstChild;
    }
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / duration, 1);
      var e = 1 - Math.pow(1 - p, 3);
      var val = Math.round(from + (target - from) * e);
      if (isKpi) textNode.nodeValue = String(val); else el.textContent = val + suffix;
      if (p < 1) window.requestAnimationFrame(step);
    }
    window.requestAnimationFrame(step);
  }
  function forceCounters() {
    qsa("[data-count]").forEach(function (el) { el.textContent = (el.getAttribute("data-count") || "0") + (el.getAttribute("data-suffix") || ""); });
    qsa("[data-kpi-count]").forEach(function (el) {
      var t = el.getAttribute("data-kpi-count") || "0";
      var em = el.querySelector("em");
      el.textContent = t;
      if (em) el.appendChild(em);
    });
  }

  /* =========================================================
     Dados dos terminais
     ========================================================= */
  var HERO_LINES = [
    { cls: "t-line t-cmd", html: '<span class="p">➜</span> curl <span class="flag">http://localhost:8000</span>/api/v1/system/summary | jq' },
    { cls: "t-line", html: '<span class="j-punc">{</span>' },
    { cls: "t-line", html: '  <span class="j-key">"status"</span><span class="j-punc">:</span> <span class="j-str">"ok"</span><span class="j-punc">,</span>' },
    { cls: "t-line", html: '  <span class="j-key">"docker_version"</span><span class="j-punc">:</span> <span class="j-str">"28.3.2"</span><span class="j-punc">,</span>' },
    { cls: "t-line", html: '  <span class="j-key">"containers_running"</span><span class="j-punc">:</span> <span class="j-num">9</span><span class="j-punc">,</span>' },
    { cls: "t-line", html: '  <span class="j-key">"containers_stopped"</span><span class="j-punc">:</span> <span class="j-num">3</span><span class="j-punc">,</span>' },
    { cls: "t-line", html: '  <span class="j-key">"networks_total"</span><span class="j-punc">:</span> <span class="j-num">5</span><span class="j-punc">,</span>' },
    { cls: "t-line", html: '  <span class="j-key">"ports_used_total"</span><span class="j-punc">:</span> <span class="j-num">14</span><span class="j-punc">,</span>' },
    { cls: "t-line", html: '  <span class="j-key">"mode"</span><span class="j-punc">:</span> <span class="j-str">"somente-observação"</span>' },
    { cls: "t-line", html: '<span class="j-punc">}</span>' },
    { cls: "t-line", html: '<span class="cursor"></span>' }
  ];
  var INSTALL_LINES = [
    { cls: "tr t-cmd", html: '<span class="t-prompt">➜</span> git clone <span class="t-flag">git@github.com:rique/PortWatch.git</span>' },
    { cls: "tr", html: '<span class="t-comment"># entrar no projeto</span>' },
    { cls: "tr t-cmd", html: '<span class="t-prompt">➜</span> cd PortWatch' },
    { cls: "tr", html: '<span class="t-comment"># ambiente isolado de desenvolvimento (ADR 0005)</span>' },
    { cls: "tr t-cmd", html: '<span class="t-prompt">➜</span> cp .env.example portwatch.env   <span class="t-comment"># dev-sandbox</span>' },
    { cls: "tr t-cmd", html: '<span class="t-prompt">➜</span> make dev   <span class="t-comment"># backend + frontend</span>' },
    { cls: "tr", html: '<span class="t-comment"># primeira leitura do host</span>' },
    { cls: "tr t-cmd", html: '<span class="t-prompt">➜</span> curl localhost:8000/api/v1/system/summary' },
    { cls: "tr", html: '{<span class="j-key">"status"</span>: <span class="j-str">"ok"</span>, <span class="j-key">"containers_running"</span>: <span class="j-num">12</span>, …}' },
    { cls: "tr", html: '<span class="cursor"></span>' }
  ];

  function renderTerminalHTML(lines) {
    return lines.map(function (l) { return '<div class="' + l.cls + '">' + l.html + "</div>"; }).join("");
  }
  function staticTerminals() {
    var out = document.getElementById("termOut");
    var ins = document.getElementById("installTerm");
    if (out) out.innerHTML = renderTerminalHTML(HERO_LINES);
    if (ins) ins.innerHTML = renderTerminalHTML(INSTALL_LINES);
  }

  /* =========================================================
     makeTerminal — terminais com loop (rAF + setTimeout tracked)
     ========================================================= */
  function makeTerminal(container, lines, opts) {
    if (!container) return { play: function () {}, stop: function () {} };
    opts = opts || {};
    var lineDelay = opts.lineDelay || 65;
    var holdTime = opts.holdTime || 2800;
    var onDone = opts.onDone || null;
    var timers = [];
    var playing = false;

    function clearTimers() { timers.forEach(function (t) { window.clearTimeout(t); }); timers = []; }
    function track(ms, fn) { var id = window.setTimeout(fn, ms); timers.push(id); return id; }

    function render() {
      container.innerHTML = "";
      var frag = document.createDocumentFragment();
      lines.forEach(function (ln) {
        var d = document.createElement("div");
        d.className = ln.cls || "";
        d.innerHTML = ln.html;
        frag.appendChild(d);
      });
      container.appendChild(frag);
      return qsa(":scope > *", container);
    }

    function cycle() {
      var els = render();
      els.forEach(function (el, i) {
        el.style.opacity = "0";
        el.style.transform = "translateY(4px)";
        el.style.transition = "opacity .22s ease, transform .22s ease";
        track(lineDelay * i + 30, function () {
          el.style.opacity = "1";
          el.style.transform = "none";
        });
      });
      var totalMs = lineDelay * els.length + 260;
      if (onDone) track(totalMs, onDone);
      track(totalMs + holdTime, function () { if (playing) cycle(); });
    }

    function play() { if (playing) return; playing = true; cycle(); }
    function stop() { playing = false; clearTimers(); }

    if (reduceMotion) { render(); return { play: function () {}, stop: function () {} }; }
    return { play: play, stop: stop };
  }

  /* =========================================================
     Motor de scroll: rAF compartilhado + registro de seções
     ========================================================= */
  var scrubSections = [];
  var scrollTicking = false;

  function registerScrub(updateFn) { scrubSections.push(updateFn); }

  on(window, "scroll", function () {
    if (scrubSections.length && !scrollTicking) {
      window.requestAnimationFrame(tickScroll);
      scrollTicking = true;
    }
  }, { passive: true });

  function tickScroll() {
    scrollTicking = false;
    var vh = window.innerHeight;
    scrubSections.forEach(function (fn) {
      try { fn(vh); } catch (e) { /* ignora erros isolados de seção */ }
    });
  }

  /* =========================================================
     Helpers de reveal — IO + helpers de estilos inline
     ========================================================= */
  function showEl(el, opts) {
    opts = opts || {};
    var d = opts.delay || parseFloat(getComputedStyle(el).getPropertyValue("--d")) || 0;
    var propStr = "opacity " + (opts.dur || 750) + "ms " + (opts.ease || "var(--ease)") + " " + d + "ms, transform " + (opts.dur || 750) + "ms " + (opts.ease || "var(--ease)") + " " + d + "ms";
    el.style.transition = propStr;
    el.style.opacity = "1";
    el.style.transform = "none";
    el.classList.add("is-visible");
  }

  function applyInitial(el, opacity, transform) {
    el.style.opacity = String(opacity);
    if (transform !== undefined) el.style.transform = transform;
    el.style.transition = "none";
  }

  function drawPath(pathEl, progress) {
    pathEl.style.transition = "none";
    pathEl.style.strokeDashoffset = String(1 - progress);
  }

  function showSeq(items, baseDelay, stagger) {
    items.forEach(function (el, i) {
      if (!el) return;
      showEl(el, { delay: baseDelay + i * stagger });
    });
  }

  /* =========================================================
     Classe Scrub — aplica estados iniciais antes do primeiro paint
     ========================================================= */
  var canScrub = !reduceMotion && !mobile && ("IntersectionObserver" in window);
  try {
    if (canScrub) root.classList.add("scrub");
  } catch (e) { canScrub = false; }

  /* =========================================================
     IO reveal genérico — .reveal*, .chip (dentro de reqChips),
     .person, .stack-card, .sec-card, .tl-item (via setupRoadmap)
     ========================================================= */
  var ioRevealObs = null;
  function setupIOReveal() {
    ioRevealObs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        ioRevealObs.unobserve(en.target);
        showEl(en.target);
      });
    }, { threshold: 0.12 });
    qsa(".reveal, .reveal--left, .reveal--right, .reveal--zoom").forEach(function (el) { ioRevealObs.observe(el); });
  }

  /* =========================================================
     1 — Hero
     ========================================================= */
  function setupHero() {
    var hero = qs(".hero");
    if (!hero) return;
    var badge = qs(".badge.h-in");
    var title = qs("#heroTitle");
    var lead = qs(".lead.h-in");
    var cta = qs(".cta-row.h-in");
    var termWrap = qs(".terminal-wrap");

    /* estados iniciais para elementos .h-in (opacity 0 no CSS) */
    [badge, title, lead, cta].forEach(function (el) { if (el) { el.style.opacity = "0"; el.style.transform = "translateY(22px)"; el.style.transition = "none"; } });
    if (termWrap) { termWrap.style.opacity = "0"; termWrap.style.transform = "translateY(30px) scale(.95) rotateX(6deg)"; termWrap.style.transformOrigin = "bottom center"; termWrap.style.transition = "none"; }

    /* cascata de entrada (load cascade) */
    track(100, function () { if (badge) { badge.classList.add("in"); showEl(badge); } });
    track(220, function () { if (title) { title.classList.add("in"); showEl(title); } });
    track(360, function () { if (lead) { lead.classList.add("in"); showEl(lead); } });
    track(500, function () { if (cta) { cta.classList.add("in"); showEl(cta); } });
    track(420, function () { if (termWrap) { termWrap.classList.add("in"); showEl(termWrap, { dur: 950 }); } });

    if (!canScrub) return;

    /* estados iniciais para elementos do grafo hero (ocultos por html.js) */
    var hgNodes = qsa(".hg-node", hero);
    var hgRings = qsa(".hg-ring", hero);
    var hgLines = qsa(".hg-line", hero);
    hgNodes.concat(hgRings).forEach(function (el) { applyInitial(el, 0, "scale(.4)"); });
    hgLines.forEach(function (el) { applyInitial(el, undefined); el.style.strokeDashoffset = "1"; el.style.strokeDasharray = "1"; });

    /* parallax / garnish while hero scrolls out */
    registerScrub(function (vh) {
      var rect = hero.getBoundingClientRect();
      if (rect.bottom < 0 || rect.top > vh) return;
      var hp = clamp(1 - (rect.bottom / (rect.height + vh * 0.3)), 0, 1);
      var easeHp = ease(hp);
      /* graph reveal: first 55% of scroll-out */
      var gp = ease(clamp(hp * 1.8, 0, 1));
      hgNodes.forEach(function (el, i) {
        var staggered = ease(clamp((gp - i * 0.055), 0, 1));
        el.style.opacity = String(staggered);
        el.style.transform = "scale(" + lerp(0.4, 1, staggered) + ")";
      });
      hgRings.forEach(function (el, i) {
        var s = ease(clamp((gp - i * 0.055), 0, 1));
        el.style.opacity = String(s * 0.35);
        el.style.transform = "scale(" + lerp(0.4, 1, s) + ")";
      });
      hgLines.forEach(function (el, i) {
        var lp = ease(clamp((gp - 0.18 - i * 0.065), 0, 1));
        el.style.strokeDashoffset = String(1 - lp);
      });
      /* title parallax + fade */
      if (title) { title.style.transform = "translateY(" + (-18 * easeHp) + "px) scale(" + lerp(1, 0.97, easeHp) + ")"; title.style.opacity = String(lerp(1, 0.72, easeHp)); }
      /* term parallax */
      if (termWrap) { termWrap.style.transform = "translateY(" + (-12 * easeHp) + "px) scale(" + lerp(1, 1.015, easeHp) + ")"; }
      /* backdrop */
      var bd = qs(".backdrop");
      if (bd) bd.style.transform = "translateY(" + (24 * easeHp) + "px)";
    });
  }

  /* =========================================================
     2 — Jornada
     ========================================================= */
  var journeyRandoms = null;
  function setupJourney() {
    var section = qs(".journey");
    var words = qsa(".j-word", section);
    if (!section || !words.length) return;

    if (reduceMotion || mobile) {
      words.forEach(function (w) {
        var io = new IntersectionObserver(function (ents) {
          if (!ents[0].isIntersecting) return; io.unobserve(w);
          w.style.transition = "opacity .55s var(--ease), transform .55s var(--ease)";
          w.style.opacity = "1"; w.style.transform = "none";
        }, { threshold: 0.2 });
        io.observe(w);
      });
      return;
    }

    section.classList.add("pinned");
    /* precompute random offsets (fixed per load) — less scattered */
    if (!journeyRandoms) {
      journeyRandoms = words.map(function () {
        return { rx: rand(-120, 120), ry: rand(-80, 80), rot: rand(-8, 8) };
      });
    }
    /* initial states: words scattered but visible */
    words.forEach(function (w, i) {
      var r = journeyRandoms[i];
      w.style.transition = "none";
      w.style.opacity = "0.4";
      w.style.transform = "translate(" + r.rx + "px," + r.ry + "px) rotate(" + r.rot + "deg)";
    });
    var jFinal = qs(".j-final", section);
    if (jFinal) { jFinal.style.transform = "scale(1)"; jFinal.style.transition = "none"; }

    registerScrub(function (vh) {
      var rect = section.getBoundingClientRect();
      var dist = section.offsetHeight - vh;
      if (dist <= 0) return;
      var p = clamp(-rect.top / dist, 0, 1);
      var totalDuration = words.length * 180 + 850;
      words.forEach(function (w, i) {
        var wp = clamp((p * totalDuration - i * 180) / 700, 0, 1);
        var e = ease(wp);
        var r = journeyRandoms[i];
        w.style.opacity = String(lerp(0.4, 1, e));
        w.style.transform = "translate(" + (r.rx * (1 - e)) + "px," + (r.ry * (1 - e)) + "px) rotate(" + (r.rot * (1 - e)) + "deg)";
      });
      /* j-final pop at end */
      if (jFinal) {
        var fp = clamp((p * totalDuration - words.length * 180 - 100) / 600, 0, 1);
        var fe = ease(fp);
        var sc = fp < 0.5 ? lerp(1, 1.12, fe * 2) : lerp(1.12, 1, (fe - 0.5) * 2);
        jFinal.style.transform = "scale(" + sc + ")";
        jFinal.style.opacity = String(lerp(0.4, 1, fe));
      }
    });
  }

  /* =========================================================
     3 — Dashboard (pin-stage)
     ========================================================= */
  function setupDashboard() {
    var pin = document.getElementById("dashPin");
    var shot = document.getElementById("dashShot");
    if (!pin || !shot) return;
    var bar = qs(".shot-bar", shot);
    var side = qs(".sl-side", shot);
    var kpis = qsa(".kpi", shot);
    var panels = qsa(".sl-panel", shot);
    var bars = qsa(".bar", shot);
    var chips = qsa(".pchip", shot);
    var legend = qs(".legend", shot);
    var kpiNumbers = qsa("[data-kpi-count]", shot);
    var allLayers = [bar, side].concat(kpis).concat(panels).concat([legend]).filter(Boolean);

    if (reduceMotion || mobile) {
      /* one-shot reveal */
      var timerBase = 0;
      var seq = [shot, side].concat(kpis).concat(panels).concat(chips).concat([legend]).filter(Boolean);
      var io = new IntersectionObserver(function (ents) {
        if (!ents[0].isIntersecting) return; io.unobserve(pin);
        seq.forEach(function (el, i) {
          track(80 * i, function () {
            el.style.transition = "opacity .45s var(--ease), transform .45s var(--ease)";
            el.style.opacity = "1"; el.style.transform = "none";
          });
        });
        bars.forEach(function (b, i) {
          track(350 + i * 28, function () {
            b.style.transition = "transform .4s var(--ease)";
            b.style.transform = "scaleY(1)";
          });
        });
        track(600, function () { kpiNumbers.forEach(animateCount); });
      }, { threshold: 0.15 });
      io.observe(pin);
      return;
    }

    /* scrub: initial states — frame visível desde o início */
    applyInitial(shot, 0.35, "scale(.96) rotateX(4deg) translateY(10px)");
    if (bar) applyInitial(bar, 0, "translateY(-4px)");
    applyInitial(side, 0, "translateX(-12px)");
    kpis.forEach(function (el) { applyInitial(el, 0, "translateY(8px)"); });
    panels.forEach(function (el) { applyInitial(el, 0, "translateY(8px)"); });
    bars.forEach(function (b) { b.style.transform = "scaleY(0)"; b.style.transformOrigin = "bottom"; b.style.transition = "none"; });
    chips.forEach(function (c) { applyInitial(c, 0, "scale(.9) translateY(4px)"); });
    if (legend) applyInitial(legend, 0);
    var kpiTriggered = false;

    registerScrub(function (vh) {
      var rect = pin.getBoundingClientRect();
      var dist = pin.offsetHeight - vh;
      if (dist <= 0) return;
      var p = clamp(-rect.top / dist, 0, 1);

      function a(from, to) { return ease(seg(p, from, to)); }

      /* frame: aparece rápido nos primeiros 12% */
      shot.style.opacity = String(lerp(0.35, 1, a(0, 0.12)));
      shot.style.transform = "scale(" + lerp(0.96, 1, a(0, 0.12)) + ") rotateX(" + lerp(4, 0, a(0, 0.12)) + "deg) translateY(" + lerp(10, 0, a(0, 0.12)) + "px)";

      if (bar) { bar.style.opacity = String(a(0.03, 0.12)); bar.style.transform = "translateY(" + lerp(-4, 0, a(0.03, 0.12)) + "px)"; }

      side.style.opacity = String(a(0.10, 0.22));
      side.style.transform = "translateX(" + lerp(-12, 0, a(0.10, 0.22)) + "px)";

      kpis.forEach(function (el) { el.style.opacity = String(a(0.20, 0.34)); el.style.transform = "translateY(" + lerp(8, 0, a(0.20, 0.34)) + "px)"; });

      panels.forEach(function (el) { el.style.opacity = String(a(0.32, 0.46)); el.style.transform = "translateY(" + lerp(8, 0, a(0.32, 0.46)) + "px)"; });

      bars.forEach(function (b, i) {
        var idx = parseInt(b.style.getPropertyValue("--i"), 10) || i;
        b.style.transform = "scaleY(" + ease(seg(p, 0.36 + idx * 0.015, 0.54 + idx * 0.015)) + ")";
      });

      chips.forEach(function (c, i) {
        var idx = parseInt(c.style.getPropertyValue("--i"), 10) || i;
        var cp = ease(seg(p, 0.42 + idx * 0.02, 0.58 + idx * 0.02));
        c.style.opacity = String(cp);
        c.style.transform = "scale(" + lerp(0.9, 1, cp) + ") translateY(" + lerp(4, 0, cp) + "px)";
      });

      if (legend) legend.style.opacity = String(a(0.60, 0.72));

      if (!kpiTriggered && p >= 0.65) { kpiTriggered = true; kpiNumbers.forEach(animateCount); }
      else if (kpiTriggered && p < 0.60) { kpiTriggered = false; }
    });
  }

  /* =========================================================
     4 — Portas (pin-stage)
     ========================================================= */
  var portsRandoms = null;
  function setupPorts() {
    var pin = document.getElementById("portsPin");
    var groups = document.getElementById("portGroups");
    if (!pin || !groups) return;
    var published = qsa(".g-published .port-node", groups);
    var occupied = qsa(".g-occupied .port-node", groups);
    var available = qsa(".g-available .port-node", groups);
    var legend = qs(".port-legend", pin);
    var allScattered = published.concat(occupied);

    if (reduceMotion || mobile) {
      var seq = allScattered.concat(available).concat([legend]).filter(Boolean);
      var io = new IntersectionObserver(function (ents) {
        if (!ents[0].isIntersecting) return; io.unobserve(pin);
        seq.forEach(function (el, i) {
          track(50 * i, function () {
            el.style.transition = "opacity .4s var(--ease), transform .4s var(--ease)";
            el.style.opacity = "1"; el.style.transform = "none";
          });
        });
      }, { threshold: 0.15 });
      io.observe(pin);
      return;
    }

    if (!portsRandoms) {
      portsRandoms = {
        scattered: allScattered.map(function () { return { rx: rand(-160, 160), ry: rand(-90, 90) }; }),
        avail: available.map(function () { return { rx: rand(-200, 200), ry: rand(-60, 60) }; })
      };
    }
    /* initial states */
    allScattered.forEach(function (el, i) {
      var r = portsRandoms.scattered[i];
      el.style.transition = "none";
      el.style.opacity = "0";
      el.style.transform = "translate(" + r.rx + "px," + r.ry + "px) scale(.75)";
    });
    available.forEach(function (el, i) {
      var r = portsRandoms.avail[i];
      el.style.transition = "none";
      el.style.opacity = "0";
      el.style.transform = "translate(" + r.rx + "px," + r.ry + "px) scale(.75)";
    });
    if (legend) applyInitial(legend, 0);
    var publishedPulsed = false;

    registerScrub(function (vh) {
      var rect = pin.getBoundingClientRect();
      var dist = pin.offsetHeight - vh;
      if (dist <= 0) return;
      var p = clamp(-rect.top / dist, 0, 1);

      /* scattered fly-in [0, 0.35] */
      allScattered.forEach(function (el, i) {
        var ip = ease(seg(p, i * 22 / 4000, 0.35));
        var r = portsRandoms.scattered[i];
        el.style.opacity = String(ip);
        el.style.transform = "translate(" + (r.rx * (1 - ip)) + "px," + (r.ry * (1 - ip)) + "px) scale(" + lerp(0.75, 1, ip) + ")";
      });

      /* published pulse [0.35, 0.45] */
      var pp = ease(seg(p, 0.35, 0.45));
      published.forEach(function (el) { el.style.transform = "scale(" + lerp(1, 1.08, pp < 0.5 ? pp * 2 : (1 - pp) * 2) + ")"; });

      /* available fly-in [0.40, 0.70] */
      available.forEach(function (el, i) {
        var ap = ease(seg(p, 0.40 + i * 24 / 3500, 0.70));
        var r = portsRandoms.avail[i];
        el.style.opacity = String(ap);
        el.style.transform = "translate(" + (r.rx * (1 - ap)) + "px," + (r.ry * (1 - ap)) + "px) scale(" + lerp(0.75, 1, ap) + ")";
      });

      if (legend) legend.style.opacity = String(ease(seg(p, 0.72, 0.82)));
    });
  }

  /* =========================================================
     5 — Redes Docker (SVG graph)
     ========================================================= */
  function setupNetworks() {
    var svgEl = document.getElementById("netGraph");
    var wrap = qs(".netgraph-wrap");
    if (!svgEl) return;
    var containerNodes = qsa("rect.ng-node:not(.hub)", svgEl);
    var hubNodes = qsa("rect.ng-node.hub", svgEl);
    var edges = qsa(".ng-edge", svgEl);
    var labels = qsa(".ng-label");
    var pulses = qsa(".ng-pulse", svgEl);

    /* initial states (hidden by html.js) */
    containerNodes.concat(hubNodes).forEach(function (el) { applyInitial(el, 0, "scale(.5)"); });
    edges.forEach(function (el) { applyInitial(el); el.style.strokeDashoffset = "1"; el.style.strokeDasharray = "1"; });
    labels.forEach(function (el) { applyInitial(el, 0); });
    pulses.forEach(function (el) { applyInitial(el, 0); });

    var drawn = false;
    var pulseRAF = null;

    function startPulses() {
      if (reduceMotion || !edges.length) return;
      var edgeEls = edges.slice(0, pulses.length);
      pulses.forEach(function (dot, i) {
        var edge = edgeEls[i];
        if (!edge) return;
        var len = edge.getTotalLength ? edge.getTotalLength() : 100;
        var offset = i * 500;
        var dur = 2200;
        function tick(ts) {
          var t = ((ts - offset) % dur) / dur;
          if (t < 0) t += 1;
          var easeT = (1 - Math.cos(t * Math.PI * 2)) / 2; /* inOutSine */
          var pt = edge.getPointAtLength(len * easeT);
          dot.setAttribute("cx", pt.x);
          dot.setAttribute("cy", pt.y);
          var fadeIn = t < 0.1 ? t / 0.1 : t > 0.85 ? (1 - t) / 0.15 : 1;
          dot.style.opacity = String(clamp(fadeIn, 0, 1));
          pulseRAF = window.requestAnimationFrame(tick);
        }
        pulseRAF = window.requestAnimationFrame(tick);
      });
    }

    function stopPulses() { if (pulseRAF) { window.cancelAnimationFrame(pulseRAF); pulseRAF = null; } }

    var io = new IntersectionObserver(function (ents) {
      if (!ents[0].isIntersecting) { if (drawn) stopPulses(); return; }
      io.unobserve(wrap || svgEl);
      if (drawn) { startPulses(); return; }
      drawn = true;
      /* staggered reveal via timeouts */
      containerNodes.forEach(function (el, i) {
        track(90 * i, function () { el.style.transition = "opacity .5s var(--ease), transform .5s var(--ease)"; el.style.opacity = "1"; el.style.transform = "none"; });
      });
      hubNodes.forEach(function (el, i) {
        track(260 + i * 90, function () { el.style.transition = "opacity .5s var(--ease), transform .5s var(--ease)"; el.style.opacity = "1"; el.style.transform = "none"; });
      });
      labels.forEach(function (el, i) {
        track(200 + i * 60, function () { el.style.transition = "opacity .5s var(--ease)"; el.style.opacity = "1"; });
      });
      edges.forEach(function (el, i) {
        track(420 + i * 110, function () {
          el.style.transition = "stroke-dashoffset .7s var(--ease)";
          el.style.strokeDashoffset = "0";
        });
      });
      track(800, startPulses);
    }, { threshold: 0.15 });
    io.observe(wrap || svgEl);
  }

  /* =========================================================
     7 — Funcionalidades (beats)
     ========================================================= */
  function setupFeatureBeats() {
    var beats = qsa(".beat");
    beats.forEach(function (beat) {
      var kind = beat.getAttribute("data-beat");
      var demo = qs(".beat-demo", beat);
      if (!demo) return;

      var io = new IntersectionObserver(function (ents) {
        if (!ents[0].isIntersecting) return;
        io.unobserve(beat);

        /* beat fade in */
        beat.style.transition = "opacity .6s var(--ease), transform .6s var(--ease)";
        beat.style.opacity = "1";
        beat.style.transform = "none";

        if (kind === "containers") {
          var dots = qsa("[data-dot]", beat);
          dots.forEach(function (d, i) {
            track(250 + i * 110, function () {
              d.style.transition = "opacity .4s var(--ease), transform .4s var(--ease)";
              d.style.opacity = "1"; d.style.transform = "scale(1)";
            });
          });
        } else if (kind === "ports") {
          var chips = qsa("[data-p]", beat);
          chips.forEach(function (c, i) {
            track(250 + i * 140, function () {
              c.style.transition = "color .5s, border-color .5s, transform .5s var(--ease)";
              c.style.color = "#34d399";
              c.style.borderColor = "rgba(52,211,153,.5)";
              c.style.transform = "scale(1)";
            });
          });
        } else {
          /* networks / health: draw path */
          var path = qs("path[data-edge]", demo);
          if (path) {
            path.style.strokeDasharray = "1";
            path.style.strokeDashoffset = "1";
            track(250, function () {
              path.style.transition = "stroke-dashoffset .7s var(--ease)";
              path.style.strokeDashoffset = "0";
            });
          }
        }
      }, { threshold: 0.2 });
      io.observe(beat);
    });
  }

  /* =========================================================
     6 — Arquitetura (pin-stage)
     ========================================================= */
  function setupArchitecture() {
    var pin = document.getElementById("archPin");
    var stageEl = document.getElementById("archStage");
    if (!pin || !stageEl) return;
    var host = qs('[data-node="host"]', stageEl);
    var proxy = qs('[data-node="proxy"]', stageEl);
    var core = qs('[data-node="core"]', stageEl);
    var ui = qs('[data-node="ui"]', stageEl);
    var cli = qs('[data-node="cli"]', stageEl);
    var arrows = qsa(".arrow", stageEl);
    var growPaths = arrows.map(function (a) { return qs(".grow-path", a); });
    var archPulses = qsa(".arch-pulse", stageEl);
    var note = qs(".arch-note", stageEl);

    /* initial states */
    [host, proxy, core, ui, cli, note].filter(Boolean).forEach(function (el) { applyInitial(el, 0, "translateY(14px) scale(.96)"); });
    growPaths.filter(Boolean).forEach(function (el) { applyInitial(el); el.style.strokeDashoffset = "1"; el.style.strokeDasharray = "1"; });
    archPulses.forEach(function (el) { applyInitial(el, 0); });

    if (reduceMotion || mobile) {
      var seq = [host, proxy, core, ui, cli, note].filter(Boolean);
      var io = new IntersectionObserver(function (ents) {
        if (!ents[0].isIntersecting) return; io.unobserve(pin);
        seq.forEach(function (el, i) {
          track(200 + i * 180, function () {
            el.style.transition = "opacity .5s var(--ease), transform .5s var(--ease)";
            el.style.opacity = "1"; el.style.transform = "none";
          });
        });
        growPaths.filter(Boolean).forEach(function (el, i) {
          track(350 + i * 250, function () {
            el.style.transition = "stroke-dashoffset .6s var(--ease)";
            el.style.strokeDashoffset = "0";
          });
        });
      }, { threshold: 0.15 });
      io.observe(pin);
      return;
    }

    var arrowEls = growPaths.map(function (p) {
      if (!p) return null;
      return { path: p, len: p.getTotalLength ? p.getTotalLength() : 30 };
    });

    registerScrub(function (vh) {
      var rect = pin.getBoundingClientRect();
      var dist = pin.offsetHeight - vh;
      if (dist <= 0) return;
      var p = clamp(-rect.top / dist, 0, 1);
      function a(from, to) { return ease(seg(p, from, to)); }

      host.style.opacity = String(a(0, 0.10));
      host.style.transform = "translateY(" + lerp(14, 0, a(0, 0.10)) + "px) scale(" + lerp(0.96, 1, a(0, 0.10)) + ")";

      arrowEls.forEach(function (ae, i) {
        if (!ae) return;
        var from = 0.08 + i * 0.18;
        var to = from + 0.12;
        drawPath(ae.path, a(from, to));
      });

      /* arch-pulse positions along path */
      archPulses.forEach(function (dot, i) {
        var ae = arrowEls[i];
        if (!ae || !ae.path) return;
        var from = 0.08 + i * 0.18;
        var to = from + 0.12;
        var pp = seg(p, from, to);
        var easeP = (1 - Math.cos(pp * Math.PI)) / 2; /* inOutSine */
        var pt = ae.path.getPointAtLength(ae.len * easeP);
        dot.setAttribute("cx", pt.x);
        dot.setAttribute("cy", pt.y);
        var fadeIn = pp > 0 && pp < 1 ? (pp < 0.1 ? pp / 0.1 : pp > 0.85 ? (1 - pp) / 0.15 : 1) : 0;
        dot.style.opacity = String(clamp(fadeIn, 0, 1));
      });

      proxy.style.opacity = String(a(0.18, 0.30));
      proxy.style.transform = "translateY(" + lerp(14, 0, a(0.18, 0.30)) + "px) scale(" + lerp(0.96, 1, a(0.18, 0.30)) + ")";

      core.style.opacity = String(a(0.38, 0.50));
      core.style.transform = "translateY(" + lerp(14, 0, a(0.38, 0.50)) + "px) scale(" + lerp(0.96, 1, a(0.38, 0.50)) + ")";

      [ui, cli].filter(Boolean).forEach(function (el, i) {
        var from = 0.56 + i * 0.04;
        var ap = a(from, from + 0.10);
        el.style.opacity = String(ap);
        el.style.transform = "translateY(" + lerp(14, 0, ap) + "px) scale(" + lerp(0.96, 1, ap) + ")";
      });

      if (note) { note.style.opacity = String(a(0.70, 0.80)); note.style.transform = "none"; }

      /* slight camera lift */
      stageEl.style.transform = "translateY(" + (-16 * p) + "px)";
    });
  }

  /* =========================================================
     Roadmap — barra de progresso + itens acesos
     ========================================================= */
  function setupRoadmap() {
    var tlWrap = document.getElementById("roadmapTimeline");
    var fill = document.getElementById("tlFill");
    var items = qsa(".tl-item", tlWrap);
    if (!tlWrap) return;

    /* fill initial */
    if (fill) fill.style.transformOrigin = "top center";

    if (reduceMotion) {
      if (fill) fill.style.transform = "scaleY(1)";
      items.forEach(function (el) { el.classList.add("lit"); });
      return;
    }

    /* fill progress via rAF driver */
    if (fill) {
      registerScrub(function (vh) {
        var rect = tlWrap.getBoundingClientRect();
        var center = vh / 2;
        var top = rect.top;
        var bottom = rect.bottom;
        if (bottom < 0 || top > vh) return;
        var p = clamp((center - top) / (bottom - top), 0, 1);
        fill.style.transform = "scaleY(" + p + ")";
      });
    }

    /* items lit via IO */
    var itemIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) en.target.classList.add("lit");
        else en.target.classList.remove("lit");
      });
    }, { rootMargin: "-40% 0px -40% 0px", threshold: 0 });
    items.forEach(function (el) { itemIO.observe(el); });
  }

  /* =========================================================
     Instalação — terminal + checklist + chips
     ========================================================= */
  function setupInstall() {
    var installTerm = document.getElementById("installTerm");
    var check = document.getElementById("installCheck");
    var reqChips = qsa("#reqChips .chip");
    var checkItems = check ? qsa(".ic-item", check) : [];
    var icPaths = check ? qsa(".ic-path", check) : [];
    var played = false;

    function playChecklist() {
      if (!checkItems.length) return;
      checkItems.forEach(function (el, i) {
        track(160 * i, function () {
          el.style.transition = "opacity .3s var(--ease), transform .3s var(--ease)";
          el.style.opacity = "1";
          el.style.transform = "none";
        });
      });
      icPaths.forEach(function (p, i) {
        p.style.strokeDasharray = "1";
        p.style.strokeDashoffset = "1";
        track(120 + i * 160, function () {
          p.style.transition = "stroke-dashoffset .26s var(--ease)";
          p.style.strokeDashoffset = "0";
        });
      });
    }

    function resetChecklist() {
      checkItems.forEach(function (el) { el.style.opacity = "0"; });
      icPaths.forEach(function (p) { p.style.strokeDashoffset = "1"; });
    }

    /* chips initial */
    reqChips.forEach(function (c) { c.style.transition = "none"; c.style.opacity = "0"; c.style.transform = "translateY(8px) scale(.94)"; });

    var term = makeTerminal(installTerm, INSTALL_LINES, {
      lineDelay: 90,
      holdTime: 2600,
      onDone: reduceMotion ? null : function () {
        if (!played) { played = true; playChecklist(); }
      }
    });

    if (reduceMotion) {
      staticTerminals();
      checkItems.forEach(function (el) { el.style.opacity = "1"; el.style.transform = "none"; });
      reqChips.forEach(function (c) { c.style.opacity = "1"; c.style.transform = "none"; });
    } else {
      var io = new IntersectionObserver(function (ents) {
        if (!ents[0].isIntersecting) { term.stop(); resetChecklist(); return; }
        io.unobserve(installTerm);
        played = false;
        term.play();
      }, { threshold: 0.15 });
      io.observe(installTerm);

      if (reqChips.length) {
        var chipIO = new IntersectionObserver(function (ents) {
          if (!ents[0].isIntersecting) return;
          chipIO.unobserve(qs("#reqChips"));
          reqChips.forEach(function (c, i) {
            track(70 * i, function () {
              c.style.transition = "opacity .4s var(--ease), transform .4s var(--ease)";
              c.style.opacity = "1"; c.style.transform = "none";
            });
          });
        }, { threshold: 0.2 });
        chipIO.observe(qs("#reqChips"));
      }
    }
  }

  /* =========================================================
     Inicialização principal — try/catch global
     ========================================================= */
  function track(ms, fn) { return window.setTimeout(fn, ms); }

  try {
    staticTerminals();
    setupIOReveal();
    setupHero();
    setupJourney();
    setupDashboard();
    setupPorts();
    setupNetworks();
    setupFeatureBeats();
    setupArchitecture();
    setupRoadmap();
    setupInstall();

    /* hero terminal loop */
    if (!reduceMotion) {
      var heroTerm = makeTerminal(document.getElementById("termOut"), HERO_LINES, { lineDelay: 55, holdTime: 3400 });
      track(500, function () { heroTerm.play(); });
      var heroTermIO = new IntersectionObserver(function (ents) {
        if (!ents[0].isIntersecting) heroTerm.stop(); else heroTerm.play();
      }, { threshold: 0 });
      heroTermIO.observe(document.getElementById("termOut"));
    }

    /* counters */
    if (!reduceMotion) {
      qsa("[data-count]").forEach(function (el) {
        var io = new IntersectionObserver(function (ents) {
          if (!ents[0].isIntersecting) return;
          io.unobserve(el);
          animateCount(el);
        }, { threshold: 0.3 });
        io.observe(el);
      });
    } else {
      forceCounters();
    }

  } catch (err) {
    failSafe(err);
  }

  function failSafe(err) {
    console.warn("[PortWatch] Motor de animação falhou, fallback seguro:", err);
    root.classList.add("failsafe");
    root.classList.remove("scrub");
    var section = qs(".journey");
    if (section) section.classList.remove("pinned");

    /* força todos os elementos inicialmente ocultos a ficarem visíveis */
    qsa(
      ".reveal, .reveal--left, .reveal--right, .reveal--zoom," +
      ".h-in, .terminal-wrap, .shot, .bar, .pchip, .node," +
      ".chip, .port-node, .arch-note, .ng-label," +
      ".hero-graph .hg-node, .hero-graph .hg-ring," +
      ".netgraph .ng-node, .netgraph .ng-edge," +
      ".hero-graph .hg-line, .grow-path," +
      ".bd-net path, .bd-heart path, .ic-path," +
      ".shot-layer, .ic-item, .tl-fill"
    ).forEach(function (el) {
      el.style.transition = "none";
      el.style.opacity = "1";
      el.style.transform = "none";
      if (el.style.strokeDashoffset !== undefined) el.style.strokeDashoffset = "0";
      el.classList.add("is-visible");
    });

    staticTerminals();
    forceCounters();
  }

})();
