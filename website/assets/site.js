/* PortWatch website — progressive enhancement, sem dependências. */
(function () {
  "use strict";

  var root = document.documentElement;
  var reduceMotion = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function all(selector, context) {
    return Array.prototype.slice.call((context || document).querySelectorAll(selector));
  }

  function one(selector, context) {
    return (context || document).querySelector(selector);
  }

  function listen(target, event, handler, options) {
    if (target) target.addEventListener(event, handler, options || false);
  }

  function setupMenu() {
    var button = document.getElementById("menuBtn");
    var links = document.getElementById("navLinks");
    if (!button || !links) return;

    function close() {
      links.classList.remove("open");
      button.setAttribute("aria-expanded", "false");
      button.setAttribute("aria-label", "Abrir menu");
    }

    listen(button, "click", function () {
      var isOpen = links.classList.toggle("open");
      button.setAttribute("aria-expanded", String(isOpen));
      button.setAttribute("aria-label", isOpen ? "Fechar menu" : "Abrir menu");
    });
    listen(links, "click", function (event) {
      if (event.target.closest("a")) close();
    });
    listen(document, "keydown", function (event) {
      if (event.key === "Escape") {
        close();
        button.focus();
      }
    });
    listen(window, "resize", function () {
      if (window.innerWidth > 1040) close();
    });
  }

  function setupNavigation() {
    var header = one("header.nav");
    var navLinks = all("nav.links a[href^='#']");
    var sections = all("main section[id]");
    var ticking = false;

    function updateHeader() {
      if (header) header.classList.toggle("scrolled", window.scrollY > 24);
      ticking = false;
    }

    listen(window, "scroll", function () {
      if (!ticking) {
        ticking = true;
        window.requestAnimationFrame(updateHeader);
      }
    }, { passive: true });
    updateHeader();

    if (!("IntersectionObserver" in window)) return;
    var byId = {};
    navLinks.forEach(function (link) { byId[link.hash.slice(1)] = link; });
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting || !byId[entry.target.id]) return;
        navLinks.forEach(function (link) { link.classList.remove("active"); });
        byId[entry.target.id].classList.add("active");
      });
    }, { rootMargin: "-30% 0px -60%", threshold: 0 });
    sections.forEach(function (section) { observer.observe(section); });
  }

  var HERO_LINES = [
    '<span class="p">➜</span> curl <span class="flag">http://localhost:8000</span>/api/v1/system/summary | jq',
    '<span class="j-punc">{</span>',
    '  <span class="j-key">"portwatch_status"</span><span class="j-punc">:</span> <span class="j-str">"ok"</span><span class="j-punc">,</span>',
    '  <span class="j-key">"docker_version"</span><span class="j-punc">:</span> <span class="j-str">"29.6.2"</span><span class="j-punc">,</span>',
    '  <span class="j-key">"containers_running"</span><span class="j-punc">:</span> <span class="j-num">9</span><span class="j-punc">,</span>',
    '  <span class="j-key">"networks_total"</span><span class="j-punc">:</span> <span class="j-num">5</span><span class="j-punc">,</span>',
    '  <span class="j-key">"ports_used_total"</span><span class="j-punc">:</span> <span class="j-num">14</span>',
    '<span class="j-punc">}</span>',
    '<span class="cursor"></span>'
  ];

  var INSTALL_LINES = [
    '<span class="t-prompt">➜</span> git clone <span class="t-flag">git@github.com:rique/PortWatch.git</span>',
    '<span class="t-prompt">➜</span> cd PortWatch',
    '<span class="t-prompt">➜</span> make dev-up',
    '<span class="t-prompt">➜</span> cd apps/backend && uv sync --group dev',
    '<span class="t-comment"># configure as URLs locais do sandbox (veja o README)</span>',
    '<span class="t-prompt">➜</span> uv run uvicorn portwatch_backend.app:app --port 8000',
    '<span class="t-comment"># em outro terminal: cd apps/web && pnpm install && pnpm dev</span>',
    '<span class="t-comment"># dashboard: http://localhost:5173 · API: http://localhost:8000/docs</span>',
    '<span class="cursor"></span>'
  ];

  function renderLines(target, lines, className) {
    if (!target) return;
    target.innerHTML = lines.map(function (line, index) {
      return '<div class="' + className + '" style="--line:' + index + '">' + line + "</div>";
    }).join("");
  }

  function setupContent() {
    renderLines(document.getElementById("termOut"), HERO_LINES, "t-line");
    renderLines(document.getElementById("installTerm"), INSTALL_LINES, "tr");
    all("[data-count]").forEach(function (element) {
      element.textContent = (element.getAttribute("data-count") || "0") + (element.getAttribute("data-suffix") || "");
    });
    all("[data-kpi-count]").forEach(function (element) {
      element.firstChild.nodeValue = element.getAttribute("data-kpi-count") || "0";
    });
  }

  function setupReveals() {
    var items = all(".reveal, .reveal--left, .reveal--right, .reveal--zoom");
    if (reduceMotion || !("IntersectionObserver" in window)) {
      items.forEach(function (element) { element.classList.add("is-visible"); });
      return;
    }
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    }, { rootMargin: "0px 0px -8%", threshold: 0.08 });
    items.forEach(function (element) { observer.observe(element); });
  }

  function setupBackground() {
    var canvas = document.getElementById("bgNet");
    if (!canvas || !canvas.getContext || reduceMotion) {
      if (canvas) canvas.hidden = true;
      return;
    }
    var context = canvas.getContext("2d");
    var particles = [];
    var width = 0;
    var height = 0;
    var frame = 0;
    var running = true;

    function resize() {
      var ratio = Math.min(window.devicePixelRatio || 1, 2);
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.round(width * ratio);
      canvas.height = Math.round(height * ratio);
      canvas.style.width = width + "px";
      canvas.style.height = height + "px";
      context.setTransform(ratio, 0, 0, ratio, 0, 0);
      particles = [];
      var count = Math.max(16, Math.min(34, Math.round(width / 42)));
      for (var index = 0; index < count; index += 1) {
        particles.push({
          x: Math.random() * width,
          y: Math.random() * height,
          dx: (Math.random() - 0.5) * 0.18,
          dy: (Math.random() - 0.5) * 0.18
        });
      }
    }

    function draw() {
      if (!running) return;
      context.clearRect(0, 0, width, height);
      particles.forEach(function (particle, index) {
        particle.x = (particle.x + particle.dx + width) % width;
        particle.y = (particle.y + particle.dy + height) % height;
        for (var otherIndex = index + 1; otherIndex < particles.length; otherIndex += 1) {
          var other = particles[otherIndex];
          var distance = Math.hypot(particle.x - other.x, particle.y - other.y);
          if (distance > 120) continue;
          context.strokeStyle = "rgba(34,211,238," + ((1 - distance / 120) * 0.09) + ")";
          context.beginPath();
          context.moveTo(particle.x, particle.y);
          context.lineTo(other.x, other.y);
          context.stroke();
        }
        context.fillStyle = "rgba(52,211,153,.22)";
        context.beginPath();
        context.arc(particle.x, particle.y, 1.2, 0, Math.PI * 2);
        context.fill();
      });
      frame = window.requestAnimationFrame(draw);
    }

    listen(window, "resize", resize, { passive: true });
    listen(document, "visibilitychange", function () {
      running = !document.hidden;
      window.cancelAnimationFrame(frame);
      if (running) draw();
    });
    resize();
    draw();
  }

  function failSafe(error) {
    root.classList.add("stable", "failsafe");
    console.warn("[PortWatch] enhancement disabled:", error);
  }

  try {
    root.classList.add("stable");
    setupMenu();
    setupNavigation();
    setupContent();
    setupReveals();
    setupBackground();
  } catch (error) {
    failSafe(error);
  }
})();
