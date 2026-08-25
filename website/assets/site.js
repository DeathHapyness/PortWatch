/*!
 * PortWatch — orquestração de animação (Anime.js v4)
 * Depende de website/assets/vendor/anime.min.js (carregado antes deste
 * script, expõe o global `anime`).
 *
 * Sem esse global (falha de rede/CDN local ausente), o site continua
 * funcional: a folha de estilo só esconde elementos `.reveal*` quando
 * `html.js` está presente, então caímos para "tudo visível" abaixo.
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduceMotionMQ = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
  var reduceMotion = !!(reduceMotionMQ && reduceMotionMQ.matches);

  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return Array.prototype.slice.call((ctx || document).querySelectorAll(sel)); }

  /* ---------- Menu mobile (sem relação com animação) ---------- */
  (function menu() {
    var menuBtn = document.getElementById("menuBtn");
    var navLinks = document.getElementById("navLinks");
    if (!menuBtn || !navLinks) return;
    menuBtn.addEventListener("click", function () {
      var open = navLinks.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
      menuBtn.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
    });
    navLinks.addEventListener("click", function (e) {
      var a = e.target && e.target.closest && e.target.closest("a");
      if (a) {
        navLinks.classList.remove("open");
        menuBtn.setAttribute("aria-expanded", "false");
      }
    });
  })();

  /* ---------- Nav-spy (destaca o link da seção visível) ---------- */
  (function navSpy() {
    var navAnchors = qsa("nav.links a");
    var sections = qsa("main section[id]");
    if (!("IntersectionObserver" in window) || !sections.length) return;
    var map = {};
    navAnchors.forEach(function (a) {
      var href = a.getAttribute("href") || "";
      if (href.charAt(0) === "#") map[href.slice(1)] = a;
    });
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        var link = map[en.target.id];
        if (!link) return;
        navAnchors.forEach(function (a) { a.classList.remove("active"); });
        link.classList.add("active");
      });
    }, { rootMargin: "-35% 0px -55% 0px", threshold: 0 });
    sections.forEach(function (s) { spy.observe(s); });
  })();

  /* ---------- Navbar reage ao scroll (1 listener leve, throttled por rAF) ---------- */
  (function navScrolled() {
    var nav = qs("header.nav");
    if (!nav) return;
    var ticking = false;
    function update() {
      nav.classList.toggle("scrolled", window.scrollY > 24);
      ticking = false;
    }
    window.addEventListener("scroll", function () {
      if (!ticking) { window.requestAnimationFrame(update); ticking = true; }
    }, { passive: true });
    update();
  })();

  /* ---------- Contador dos stats / KPIs (rAF, reaproveitado) ---------- */
  var countedOnce = new WeakSet ? new WeakSet() : null;
  function animateCount(el) {
    if (countedOnce) {
      if (countedOnce.has(el)) return;
      countedOnce.add(el);
    }
    var isKpi = el.hasAttribute("data-kpi-count");
    var target = parseFloat(el.getAttribute("data-count") || el.getAttribute("data-kpi-count")) || 0;
    var from = parseFloat(el.getAttribute("data-from")) || 0;
    var suffix = el.getAttribute("data-suffix") || "";
    var duration = 1200;
    var start = null;
    var textNode = null;
    if (isKpi) {
      // garante um nó de texto dedicado como primeiro filho, antes do <em>
      if (!el.firstChild || el.firstChild.nodeType !== Node.TEXT_NODE) {
        textNode = document.createTextNode(String(Math.round(from)));
        el.insertBefore(textNode, el.firstChild);
      } else {
        textNode = el.firstChild;
      }
    }
    function step(ts) {
      if (start === null) start = ts;
      var p = Math.min((ts - start) / duration, 1);
      var eased = 1 - Math.pow(1 - p, 3);
      var val = Math.round(from + (target - from) * eased);
      if (isKpi) textNode.nodeValue = String(val);
      else el.textContent = val + suffix;
      if (p < 1) window.requestAnimationFrame(step);
    }
    window.requestAnimationFrame(step);
  }

  /* =========================================================
     A partir daqui, tudo depende do Anime.js. Sem o global,
     apenas garantimos que nada fique escondido.
     ========================================================= */
  var anime = window.anime;
  if (!anime || !anime.animate) {
    qsa(".reveal, .reveal--left, .reveal--right, .reveal--zoom, .terminal-wrap, .shot, .node, .port-node, .chip, .arch-note")
      .forEach(function (el) { el.style.opacity = 1; el.style.transform = "none"; });
    qsa(".pin-stage").forEach(function (el) { el.style.height = "auto"; });
    qsa(".pin-sticky").forEach(function (el) { el.style.position = "static"; el.style.height = "auto"; });
    // terminais ainda funcionam com um render estático simples
    staticTerminals();
    return;
  }

  var animate = anime.animate;
  var createTimeline = anime.createTimeline;
  var stagger = anime.stagger;
  var onScroll = anime.onScroll;
  var createScope = anime.createScope;
  var svgApi = anime.svg;
  var utils = anime.utils || { random: function (a, b) { return a + Math.random() * (b - a); } };

  function rand(a, b) { return utils.random(a, b); }

  /* ---------- Amarra uma timeline ao progresso real do scroll ----------
     `timeline.sync(onScroll({...}))` existe na API, mas nesta versão
     vendorizada não repintou os tweens ao longo do progresso (o
     ScrollObserver computava o progresso corretamente — confirmado via
     onUpdate — porém a timeline ficava presa no estado inicial ou final).
     `seek()` manual a partir de onUpdate é documentado e comprovadamente
     confiável, então é o mecanismo usado em todo o site para as seções
     "pinned"/scrub. Sempre volta ao rolar para cima, pois é o mesmo
     progresso (0↔1) sendo buscado a cada atualização de scroll. */
  function scrubTimeline(tl, opts) {
    tl.pause();
    var extraUpdate = opts.onUpdate;
    var merged = Object.assign({}, opts, {
      onUpdate: function (self) {
        // Evita buscar exatamente 0 ou a duração total: alguns
        // observers tratam essas bordas como "fora do intervalo" e
        // revertem/zeram o render nesse exato frame.
        var p = Math.min(Math.max(self.progress, 0), 1);
        tl.seek(Math.min(Math.max(p * tl.duration, 0.001), tl.duration - 0.001));
        if (extraUpdate) extraUpdate(self);
      }
    });
    return onScroll(merged);
  }

  /* ---------- Terminais (usados nos dois modos, JS e fallback) ---------- */
  function staticTerminals() {
    var termOut = document.getElementById("termOut");
    var installTerm = document.getElementById("installTerm");
    if (termOut) termOut.innerHTML = heroLinesHTML();
    if (installTerm) installTerm.innerHTML = installLinesHTML();
  }
  function heroLinesHTML() {
    return HERO_LINES.map(function (l) { return '<div class="' + l.cls + '">' + l.html + "</div>"; }).join("");
  }
  function installLinesHTML() {
    return INSTALL_LINES.map(function (l) { return '<div class="' + l.cls + '">' + l.html + "</div>"; }).join("");
  }

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

  /* makeTerminal: linhas aparecem rápido, em cascata (stagger), sem
     digitação lenta — motor trocado de setTimeout+classe para animate(). */
  function makeTerminal(container, lines, opts) {
    if (!container) return { play: function () {}, stop: function () {} };
    opts = opts || {};
    var lineDelay = opts.lineDelay || 65;
    var holdTime = opts.holdTime || 2800;
    var onDone = opts.onDone;
    var loopTimer = null;
    var playing = false;

    function render() {
      container.innerHTML = "";
      var frag = document.createDocumentFragment();
      lines.forEach(function (ln) {
        var div = document.createElement("div");
        div.className = ln.cls || "";
        div.innerHTML = ln.html;
        frag.appendChild(div);
      });
      container.appendChild(frag);
      return qsa(":scope > *", container);
    }

    function cycle() {
      var els = render();
      animate(els, {
        opacity: [0, 1],
        translateY: [4, 0],
        duration: 220,
        ease: "outQuad",
        delay: stagger(lineDelay)
      });
      var totalMs = lineDelay * els.length + 260;
      if (onDone) loopTimer = window.setTimeout(onDone, totalMs);
      loopTimer = window.setTimeout(function () {
        if (playing) cycle();
      }, totalMs + holdTime);
    }

    function play() {
      if (playing) return;
      playing = true;
      cycle();
    }
    function stop() {
      playing = false;
      if (loopTimer) { window.clearTimeout(loopTimer); loopTimer = null; }
    }

    if (reduceMotion) { render(); return { play: function () {}, stop: function () {} }; }
    return { play: play, stop: stop };
  }

  /* ---------- Escopo principal: media queries decidem o nível de movimento ---------- */
  createScope({
    mediaQueries: {
      reduce: "(prefers-reduced-motion: reduce)",
      mobile: "(max-width: 860px)"
    }
  }).add(function (self) {
    var m = self.matches;
    var reduce = !!m.reduce;
    var mobile = !!m.mobile;

    setupInstall(reduce, mobile);
    wireReveal();
    setupHero(reduce, mobile);
    setupJourney(reduce, mobile);
    setupDashboard(reduce, mobile);
    setupPorts(reduce, mobile);
    setupNetworks(reduce, mobile);
    setupFeatureBeats(reduce, mobile);
    setupArchitecture(reduce, mobile);
    setupRoadmap(reduce, mobile);

    var heroTerm = makeTerminal(document.getElementById("termOut"), HERO_LINES, { lineDelay: 55, holdTime: 3400 });
    if (!reduce) {
      // O terminal do hero já está visível ao carregar a página (não há uma
      // transição "de fora para dentro" para o onScroll detectar), então
      // disparamos o primeiro ciclo diretamente, junto com a cascata de
      // entrada; onScroll só cuida de pausar/retomar ao sair/voltar dele.
      window.setTimeout(heroTerm.play, 500);
      onScroll({ target: "#termOut", enter: "top bottom", leave: "bottom top", onLeave: heroTerm.stop, onEnterBackward: heroTerm.play });
    } else {
      staticTerminals();
    }

    /* contadores: stats sempre; kpis do dashboard disparam no marco final do pin */
    if (!reduce) {
      qsa("[data-count]").forEach(function (el) {
        onScroll({ target: el, enter: "top bottom", leave: "bottom top", onEnter: function () { animateCount(el); } });
      });
    } else {
      qsa("[data-count]").forEach(function (el) { el.textContent = (el.getAttribute("data-count") || "0") + (el.getAttribute("data-suffix") || ""); });
    }
  });

  /* =========================================================
     Reveal genérico — replica o antigo [data-animate]:
     cada elemento observa a si mesmo, delay lido de --d.
     ========================================================= */
  function wireReveal() {
    qsa(".reveal, .reveal--left, .reveal--right, .reveal--zoom").forEach(function (el) {
      if (el.dataset.revealWired) return;
      el.dataset.revealWired = "1";
      var d = parseFloat(getComputedStyle(el).getPropertyValue("--d")) || 0;
      var props = { opacity: [0, 1], duration: 750, ease: "outCubic", delay: d };
      if (el.classList.contains("reveal--left")) props.translateX = [-28, 0];
      else if (el.classList.contains("reveal--right")) props.translateX = [28, 0];
      else if (el.classList.contains("reveal--zoom")) { props.scale = [0.94, 1]; props.translateY = [10, 0]; }
      else props.translateY = [22, 0];
      onScroll({
        target: el,
        enter: "top bottom",
        leave: "bottom top",
        onEnter: function () { el.classList.add("is-visible"); animate(el, props); }
      });
    });
  }

  /* =========================================================
     1 — Hero
     ========================================================= */
  function setupHero(reduce, mobile) {
    var hero = qs(".hero");
    if (!hero) return;

    var loadTargets = {
      badge: qs(".badge.h-in"),
      title: qs("#heroTitle"),
      lead: qs(".lead.h-in"),
      cta: qs(".cta-row.h-in"),
      term: qs(".terminal-wrap")
    };
    var loadTl = createTimeline({ defaults: { ease: "outCubic" } });
    if (loadTargets.badge) loadTl.add(loadTargets.badge, { opacity: [0, 1], translateY: [24, 0], duration: 650 }, 0);
    if (loadTargets.title) loadTl.add(loadTargets.title, { opacity: [0, 1], translateY: [26, 0], duration: 800 }, 120);
    if (loadTargets.lead) loadTl.add(loadTargets.lead, { opacity: [0, 1], translateY: [22, 0], duration: 700 }, 260);
    if (loadTargets.cta) loadTl.add(loadTargets.cta, { opacity: [0, 1], translateY: [20, 0], duration: 650 }, 400);
    if (loadTargets.term) loadTl.add(loadTargets.term, { opacity: [0, 1], translateY: [30, 0], scale: [0.95, 1], rotateX: [6, 0], duration: 950 }, 320);

    if (reduce || mobile) return;

    var lines = qsa(".hg-line", hero);
    var nodes = qsa(".hg-node", hero);
    var rings = qsa(".hg-ring", hero);
    var drawables = lines.length && svgApi ? svgApi.createDrawable(lines) : null;

    var scrollTl = createTimeline({ defaults: { ease: "linear" } });
    scrollTl.add(nodes, { opacity: [0, 1], scale: [0.4, 1], delay: stagger(70) }, 0);
    scrollTl.add(rings, { opacity: [0, 0.35], scale: [0.4, 1], delay: stagger(70) }, 0);
    if (drawables) scrollTl.add(drawables, { draw: ["0 0", "0 1"], delay: stagger(110) }, 200);
    if (loadTargets.title) scrollTl.add(loadTargets.title, { translateY: [0, -18], scale: [1, 0.97], opacity: [1, 0.72] }, 0);
    if (loadTargets.term) scrollTl.add(loadTargets.term, { translateY: [0, -12], scale: [1, 1.015] }, 0);
    var backdropAfter = qs(".backdrop");
    if (backdropAfter) scrollTl.add(backdropAfter, { translateY: [0, 24] }, 0);

    scrubTimeline(scrollTl, { target: hero, container: null, enter: "top top", leave: "bottom top" });
  }

  /* =========================================================
     2 — Jornada (Servidor → Docker → Containers → Ports → PortWatch)
     ========================================================= */
  function setupJourney(reduce, mobile) {
    var section = qs(".journey");
    var words = qsa(".j-word", section);
    if (!section || !words.length) return;

    if (reduce || mobile) {
      words.forEach(function (w) {
        onScroll({
          target: w, enter: "top bottom", leave: "bottom top",
          onEnter: function () { animate(w, { opacity: [0, 1], translateY: [16, 0], duration: 550, delay: 0, ease: "outCubic" }); }
        });
      });
      return;
    }

    section.classList.add("pinned");
    var tl = createTimeline({ defaults: { ease: "outCubic" } });
    // Valores de espalhamento pré-calculados (números concretos, não
    // funções) — uma timeline sincronizada ao scroll pode ser "buscada"
    // (seek) para qualquer progresso a qualquer momento, então cada tween
    // precisa de um from/to já resolvido.
    words.forEach(function (w, i) {
      tl.add(w, {
        translateX: [rand(-220, 220), 0],
        translateY: [rand(-140, 140), 0],
        rotate: [rand(-14, 14), 0],
        opacity: [0.15, 1],
        duration: 700
      }, i * 180);
    });
    tl.add(".j-final", { scale: [1, 1.12, 1], duration: 500 }, words.length * 180 + 350);

    scrubTimeline(tl, { target: section, container: null, enter: "top top", leave: "bottom bottom" });
  }

  /* =========================================================
     3 — Dashboard (Preview) — pin-stage, construído em 5 marcos
     ========================================================= */
  function setupDashboard(reduce, mobile) {
    var pin = document.getElementById("dashPin");
    var shot = document.getElementById("dashShot");
    if (!pin || !shot) return;

    var bar = qs(".shot-bar", shot);
    var side = qs(".sl-side", shot);
    var kpis = qsa(".kpi", shot);
    var panels = qsa(".sl-panel", shot);
    var bars = qsa(".bar", shot);
    var chips = qsa(".pchip", shot);
    var kpiNumbers = qsa("[data-kpi-count]", shot);

    if (reduce || mobile) {
      var oneShot = createTimeline({ defaults: { ease: "outCubic" } })
        .add(shot, { opacity: [0, 1], scale: [0.96, 1], duration: 500 }, 0)
        .add(side, { opacity: [0, 1], translateX: [-16, 0], duration: 450 }, 100)
        .add(kpis, { opacity: [0, 1], translateY: [10, 0], delay: stagger(60), duration: 400 }, 180)
        .add(panels, { opacity: [0, 1], translateY: [12, 0], delay: stagger(90), duration: 450 }, 260)
        .add(bars, { scaleY: [0, 1], delay: stagger(30), duration: 400 }, 400)
        .add(chips, { opacity: [0, 1], scale: [0.9, 1], delay: stagger(25), duration: 350 }, 500);
      onScroll({
        target: pin, enter: "top bottom", leave: "bottom top",
        onEnter: function () { oneShot.play(); kpiNumbers.forEach(animateCount); }
      });
      return;
    }

    var tl = createTimeline({ defaults: { ease: "outCubic" } });
    // 0–20%: moldura
    tl.add(shot, { opacity: [0, 1], scale: [0.92, 1], rotateX: [8, 0], translateY: [20, 0] }, 0);
    if (bar) tl.add(bar, { opacity: [0, 1], translateY: [-6, 0] }, 100);
    // 20–40%: barra lateral
    tl.add(side, { opacity: [0, 1], translateX: [-18, 0] }, 1000);
    // 40–60%: containers / kpis
    tl.add(kpis, { opacity: [0, 1], translateY: [12, 0], delay: stagger(70) }, 2000);
    // 60–80%: portas preenchem
    tl.add(panels, { opacity: [0, 1], translateY: [12, 0], delay: stagger(120) }, 3000);
    tl.add(bars, { scaleY: [0, 1], delay: stagger(35) }, 3050);
    tl.add(chips, { opacity: [0, 1], scale: [0.9, 1], translateY: [6, 0], delay: stagger(28) }, 3300);
    // 80–100%: legenda + kpis finais
    tl.add(qs(".legend", shot), { opacity: [0, 1], duration: 700 }, 4200);

    var kpiTriggered = false;
    scrubTimeline(tl, {
      target: pin, container: null, enter: "top top", leave: "bottom bottom",
      onUpdate: function (self2) {
        if (!kpiTriggered && self2.progress >= 0.8) {
          kpiTriggered = true;
          kpiNumbers.forEach(animateCount);
        } else if (kpiTriggered && self2.progress < 0.75) {
          kpiTriggered = false;
        }
      }
    });
  }

  /* =========================================================
     4 — Portas — pin-stage, agrupamento por estado
     ========================================================= */
  function setupPorts(reduce, mobile) {
    var pin = document.getElementById("portsPin");
    var groups = document.getElementById("portGroups");
    if (!pin || !groups) return;

    var published = qsa(".g-published .port-node", groups);
    var occupied = qsa(".g-occupied .port-node", groups);
    var available = qsa(".g-available .port-node", groups);
    var legend = qs(".port-legend", pin);

    if (reduce || mobile) {
      var oneShot = createTimeline({ defaults: { ease: "outCubic" } })
        .add(published, { opacity: [0, 1], translateY: [10, 0], delay: stagger(50) }, 0)
        .add(occupied, { opacity: [0, 1], translateY: [10, 0], delay: stagger(50) }, 120)
        .add(available, { opacity: [0, 1], translateY: [10, 0], delay: stagger(50) }, 240)
        .add(legend, { opacity: [0, 1] }, 500);
      onScroll({ target: pin, enter: "top bottom", leave: "bottom top", onEnter: function () { oneShot.play(); } });
      return;
    }

    var tl = createTimeline({ defaults: { ease: "outCubic" } });
    var scattered = published.concat(occupied);
    // Números concretos pré-calculados por nó (ver nota em setupJourney
    // sobre por que uma timeline com sync:true não pode depender de
    // valores resolvidos por função).
    scattered.forEach(function (node, i) {
      tl.add(node, {
        translateX: [rand(-160, 160), 0],
        translateY: [rand(-90, 90), 0],
        opacity: [0, 1],
        scale: [0.75, 1],
        duration: 500
      }, i * 22);
    });
    tl.add(published, { scale: [1, 1.08, 1], duration: 400, delay: stagger(20) }, 1300);
    available.forEach(function (node, i) {
      tl.add(node, {
        translateX: [rand(-200, 200), 0],
        translateY: [rand(-60, 60), 0],
        opacity: [0, 1],
        scale: [0.75, 1],
        duration: 500
      }, 1800 + i * 24);
    });
    tl.add(legend, { opacity: [0, 1] }, 3200);

    scrubTimeline(tl, { target: pin, container: null, enter: "top top", leave: "bottom bottom" });
  }

  /* =========================================================
     5 — Redes Docker — grafo SVG
     ========================================================= */
  function setupNetworks(reduce, mobile) {
    var svgEl = document.getElementById("netGraph");
    if (!svgEl) return;
    var wrap = qs(".netgraph-wrap");
    var containerNodes = qsa("rect.ng-node:not(.hub)", svgEl);
    var hubNodes = qsa("rect.ng-node.hub", svgEl);
    var dashNode = containerNodes.length ? null : null;
    var edges = qsa(".ng-edge", svgEl);
    var pulses = qsa(".ng-pulse", svgEl);
    var labels = qsa(".ng-label");

    var drawables = edges.length && svgApi ? svgApi.createDrawable(edges) : null;

    var tl = createTimeline({ defaults: { ease: "outCubic" } });
    tl.add(containerNodes, { opacity: [0, 1], scale: [0.5, 1], delay: stagger(90) }, 0);
    tl.add(hubNodes, { opacity: [0, 1], scale: [0.5, 1], delay: stagger(90) }, 260);
    tl.add(labels, { opacity: [0, 1], delay: stagger(60) }, 200);
    if (drawables) tl.add(drawables, { draw: ["0 0", "0 1"], delay: stagger(110), ease: "inOutQuad" }, 420);

    function playPulses() {
      if (reduce || !edges.length || !svgApi) return;
      edges.slice(0, pulses.length).forEach(function (edge, i) {
        var dot = pulses[i];
        if (!dot) return;
        animate(dot, Object.assign({}, svgApi.createMotionPath(edge), {
          opacity: [0, 1, 1, 0],
          duration: 2200,
          delay: i * 500,
          loop: true,
          ease: "inOutSine"
        }));
      });
    }

    if (reduce || mobile) {
      onScroll({ target: wrap || svgEl, enter: "top bottom", leave: "bottom top", onEnter: function () { tl.play(); playPulses(); } });
      return;
    }

    onScroll({
      target: wrap || svgEl, container: null, enter: "top bottom", leave: "bottom top",
      onEnter: function () { tl.play(); playPulses(); },
      onEnterBackward: function () { tl.play(); }
    });
  }

  /* =========================================================
     7 — Funcionalidades — 4 beats sequenciais + resto em stagger
     (o resto dos cards e o api-panel já são cobertos por wireReveal)
     ========================================================= */
  function setupFeatureBeats(reduce, mobile) {
    var beats = qsa(".beat");
    if (!beats.length) return;
    beats.forEach(function (beat) {
      var kind = beat.getAttribute("data-beat");
      var tl = buildBeatTimeline(beat, kind);
      if (!tl) return;
      onScroll({
        target: beat, enter: "top bottom", leave: "bottom top",
        onEnter: function () { tl.play(); },
        onEnterBackward: function () { if (!reduce) tl.play(); },
        onLeaveBackward: function () { tl.pause(); tl.seek(0); }
      });
    });
  }

  function buildBeatTimeline(beat, kind) {
    var tl = createTimeline({ defaults: { ease: "outCubic" }, autoplay: false });
    tl.add(beat, { opacity: [0, 1], translateY: [18, 0], duration: 600 }, 0);
    if (kind === "containers") {
      var dots = qsa("[data-dot]", beat);
      tl.add(dots, { opacity: [0.35, 1], scale: [0.7, 1], delay: stagger(110) }, 250);
    } else if (kind === "ports") {
      var chips = qsa("[data-p]", beat);
      tl.add(chips, {
        color: ["#94a3b8", "#34d399"],
        borderColor: ["rgba(148,163,184,.28)", "rgba(52,211,153,.5)"],
        scale: [0.92, 1],
        delay: stagger(140)
      }, 250);
    } else if (kind === "networks" || kind === "health") {
      var path = qs("[data-edge]", beat);
      if (path && svgApi) {
        var drawable = svgApi.createDrawable(path);
        tl.add(drawable, { draw: ["0 0", "0 1"], duration: 700, ease: "inOutQuad" }, 250);
      }
    }
    return tl;
  }

  /* =========================================================
     6 — Arquitetura — pin-stage, fluxo contínuo com "câmera"
     ========================================================= */
  function setupArchitecture(reduce, mobile) {
    var pin = document.getElementById("archPin");
    var stageEl = document.getElementById("archStage");
    if (!pin || !stageEl) return;

    var host = qs('[data-node="host"]', stageEl);
    var proxy = qs('[data-node="proxy"]', stageEl);
    var core = qs('[data-node="core"]', stageEl);
    var ui = qs('[data-node="ui"]', stageEl);
    var cli = qs('[data-node="cli"]', stageEl);
    var arrows = qsa(".arrow", stageEl);
    var note = qs(".arch-note", stageEl);

    var arrowDrawables = [];
    arrows.forEach(function (arrowEl) {
      var path = qs(".grow-path", arrowEl);
      if (path && svgApi) arrowDrawables.push(svgApi.createDrawable(path)[0]);
      else arrowDrawables.push(null);
    });
    var pulses = qsa(".arch-pulse", stageEl);

    if (reduce || mobile) {
      var seq = createTimeline({ defaults: { ease: "outCubic" }, autoplay: false })
        .add(host, { opacity: [0, 1], translateY: [16, 0] }, 0)
        .add(arrowDrawables[0] || {}, { draw: ["0 0", "0 1"] }, 150)
        .add(proxy, { opacity: [0, 1], translateY: [16, 0] }, 300)
        .add(arrowDrawables[1] || {}, { draw: ["0 0", "0 1"] }, 450)
        .add(core, { opacity: [0, 1], translateY: [16, 0] }, 600)
        .add(arrowDrawables[2] || {}, { draw: ["0 0", "0 1"] }, 750)
        .add([ui, cli], { opacity: [0, 1], translateY: [16, 0], delay: stagger(90) }, 900)
        .add(note, { opacity: [0, 1] }, 1150);
      onScroll({ target: pin, enter: "top bottom", leave: "bottom top", onEnter: function () { seq.play(); } });
      return;
    }

    var tl = createTimeline({ defaults: { ease: "linear" } });
    tl.add(host, { opacity: [0, 1], translateY: [14, 0] }, 0);
    if (arrowDrawables[0]) tl.add(arrowDrawables[0], { draw: ["0 0", "0 1"] }, 400);
    if (pulses[0]) tl.add(pulses[0], Object.assign({ opacity: [0, 1, 1, 0] }, arrows[0] && svgApi ? svgApi.createMotionPath(qs(".grow-path", arrows[0])) : {}), 500);
    tl.add(proxy, { opacity: [0, 1], translateY: [14, 0] }, 1200);
    if (arrowDrawables[1]) tl.add(arrowDrawables[1], { draw: ["0 0", "0 1"] }, 1600);
    if (pulses[1]) tl.add(pulses[1], Object.assign({ opacity: [0, 1, 1, 0] }, arrows[1] && svgApi ? svgApi.createMotionPath(qs(".grow-path", arrows[1])) : {}), 1700);
    tl.add(core, { opacity: [0, 1], translateY: [14, 0] }, 2400);
    if (arrowDrawables[2]) tl.add(arrowDrawables[2], { draw: ["0 0", "0 1"] }, 2800);
    if (pulses[2]) tl.add(pulses[2], Object.assign({ opacity: [0, 1, 1, 0] }, arrows[2] && svgApi ? svgApi.createMotionPath(qs(".grow-path", arrows[2])) : {}), 2900);
    tl.add([ui, cli], { opacity: [0, 1], translateY: [14, 0], delay: stagger(100) }, 3600);
    tl.add(note, { opacity: [0, 1] }, 4200);
    tl.add(stageEl, { translateY: [0, -16] }, 0);

    scrubTimeline(tl, { target: pin, container: null, enter: "top top", leave: "bottom bottom" });
  }

  /* =========================================================
     Roadmap — barra de progresso + itens "acesos"
     ========================================================= */
  function setupRoadmap(reduce, mobile) {
    var tlWrap = document.getElementById("roadmapTimeline");
    var fill = document.getElementById("tlFill");
    var items = qsa(".tl-item", tlWrap);
    if (!tlWrap) return;

    if (reduce) {
      if (fill) fill.style.transform = "scaleY(1)";
      items.forEach(function (el) { el.classList.add("lit"); });
      return;
    }

    if (fill) {
      onScroll({
        target: tlWrap, container: null, enter: "top center", leave: "bottom center",
        onUpdate: function (self) { fill.style.transform = "scaleY(" + self.progress + ")"; }
      });
    }
    items.forEach(function (el) {
      onScroll({
        target: el, enter: "center bottom", leave: "center top",
        onEnter: function () { el.classList.add("lit"); },
        onLeave: function () { el.classList.remove("lit"); },
        onEnterBackward: function () { el.classList.add("lit"); },
        onLeaveBackward: function () { el.classList.remove("lit"); }
      });
    });
  }

  /* =========================================================
     Instalação — terminal + checklist + chips de pré-requisitos
     ========================================================= */
  function setupInstall(reduce, mobile) {
    var installTerm = document.getElementById("installTerm");
    var check = document.getElementById("installCheck");
    var reqChips = qsa("#reqChips .chip");

    var checkItems = check ? qsa(".ic-item", check) : [];
    function playChecklist() {
      if (!checkItems.length) return;
      var paths = qsa(".ic-path", check);
      var drawables = paths.length && svgApi ? svgApi.createDrawable(paths) : null;
      animate(checkItems, { opacity: [0, 1], translateX: [-6, 0], delay: stagger(160), duration: 300 });
      if (drawables) animate(drawables, { draw: ["0 0", "0 1"], delay: stagger(160, { start: 120 }), duration: 260, ease: "inOutQuad" });
    }
    function resetChecklist() {
      if (!checkItems.length) return;
      checkItems.forEach(function (el) { el.style.opacity = 0; });
      qsa(".ic-path", check).forEach(function (p) { p.style.strokeDashoffset = 1; });
    }

    var term = makeTerminal(installTerm, INSTALL_LINES, {
      lineDelay: 90,
      holdTime: 2600,
      onDone: reduce ? null : playChecklist
    });

    if (reduce) {
      staticTerminalInto(installTerm, INSTALL_LINES);
      if (check) checkItems.forEach(function (el) { el.style.opacity = 1; });
    } else {
      onScroll({
        target: installTerm, enter: "top bottom", leave: "bottom top",
        onEnter: term.play,
        onLeave: function () { term.stop(); resetChecklist(); }
      });
    }

    if (reqChips.length) {
      if (reduce) {
        reqChips.forEach(function (c) { c.style.opacity = 1; });
      } else {
        onScroll({
          target: "#reqChips", enter: "top bottom", leave: "bottom top",
          onEnter: function () {
            animate(reqChips, { opacity: [0, 1], translateY: [8, 0], scale: [0.94, 1], delay: stagger(70) });
          }
        });
      }
    }
  }

  function staticTerminalInto(container, lines) {
    if (!container) return;
    container.innerHTML = lines.map(function (l) { return '<div class="' + l.cls + '" style="opacity:1">' + l.html + "</div>"; }).join("");
  }
})();
