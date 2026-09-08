/* Agrégation · English phonology — progressive enhancements
   Everything on the pages works without this file; it only adds:
   mobile navigation drawer, ruby display modes, "on this page" highlight,
   back-to-top, collapsible video on practice pages. */
(function () {
  "use strict";
  var d = document, root = d.documentElement, body = d.body;

  /* ---- Mobile navigation drawer ---------------------------------------- */
  var toggle = d.querySelector(".nav-toggle");
  var nav = d.getElementById("site-nav");
  var backdrop = d.querySelector(".nav-backdrop");
  function closeNav() {
    body.classList.remove("nav-open");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
  }
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = body.classList.toggle("nav-open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
    });
    if (backdrop) backdrop.addEventListener("click", closeNav);
    nav.addEventListener("click", function (e) {
      if (e.target.closest("a") && window.innerWidth < 840) closeNav();
    });
    d.addEventListener("keydown", function (e) { if (e.key === "Escape") closeNav(); });
  }

  /* ---- Ruby transcriptions: above / inline / hidden (quiz) ------------- */
  var hasRuby = !!d.querySelector("ruby");
  if (hasRuby) body.classList.add("has-ruby");
  var rubyButtons = d.querySelectorAll(".ruby-switch button");
  function setRuby(mode) {
    root.setAttribute("data-ruby", mode);
    try { localStorage.setItem("rubyMode", mode); } catch (e) {}
    rubyButtons.forEach(function (b) {
      b.setAttribute("aria-pressed", b.getAttribute("data-ruby") === mode ? "true" : "false");
    });
  }
  setRuby(root.getAttribute("data-ruby") || "above");
  rubyButtons.forEach(function (b) {
    b.addEventListener("click", function () { setRuby(b.getAttribute("data-ruby")); });
  });
  if (hasRuby) {
    d.addEventListener("click", function (e) {
      var r = e.target.closest("ruby");
      if (r && root.getAttribute("data-ruby") === "hidden") r.classList.toggle("reveal");
    });
  }

  /* ---- "On this page": highlight the section being read ---------------- */
  var tocLinks = Array.prototype.slice.call(d.querySelectorAll(".toc a[href^='#']"));
  if (tocLinks.length && "IntersectionObserver" in window) {
    var byHeading = new Map();
    tocLinks.forEach(function (a) {
      var id = decodeURIComponent(a.getAttribute("href").slice(1));
      var h = d.getElementById(id);
      if (h) byHeading.set(h, a);
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          tocLinks.forEach(function (a) { a.classList.remove("active"); });
          var a = byHeading.get(en.target);
          if (a) a.classList.add("active");
        }
      });
    }, { rootMargin: "-15% 0px -75% 0px", threshold: 0 });
    byHeading.forEach(function (_a, h) { io.observe(h); });
  }

  /* ---- Back to top ------------------------------------------------------ */
  var btt = d.querySelector(".back-to-top");
  if (btt) {
    var onScroll = function () { btt.classList.toggle("show", window.scrollY > 700); };
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    btt.addEventListener("click", function () { window.scrollTo({ top: 0, behavior: "smooth" }); });
  }

  /* ---- Practice pages: collapsible sticky video ------------------------ */
  var vc = d.getElementById("video-container");
  if (vc) {
    var btn = d.createElement("button");
    btn.type = "button";
    btn.className = "video-toggle";
    btn.textContent = "Hide video";
    btn.addEventListener("click", function () {
      var c = vc.classList.toggle("collapsed");
      btn.textContent = c ? "Show video" : "Hide video";
    });
    vc.appendChild(btn);
  }
})();
