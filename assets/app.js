/* Olfatecho: revelado al hacer scroll, menú móvil, consentimiento y anuncios. */
(function () {
  "use strict";

  var reduce = window.matchMedia &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // 1. Revelado de secciones y tarjetas
  var reveals = document.querySelectorAll(".reveal");
  if (reduce || !("IntersectionObserver" in window)) {
    for (var i = 0; i < reveals.length; i++) reveals[i].classList.add("is-visible");
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (en.isIntersecting) {
          en.target.classList.add("is-visible");
          io.unobserve(en.target);
        }
      });
    }, { threshold: 0.12, rootMargin: "0px 0px -6% 0px" });
    for (var j = 0; j < reveals.length; j++) io.observe(reveals[j]);
  }

  // 2. Menú móvil
  var toggle = document.querySelector(".nav-toggle");
  var nav = document.getElementById("nav");
  if (toggle && nav) {
    toggle.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      toggle.setAttribute("aria-expanded", open ? "true" : "false");
      toggle.setAttribute("aria-label", open ? "Cerrar menú" : "Abrir menú");
    });
    nav.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        nav.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      });
    });
  }

  // 3. Barra de progreso de lectura
  var bar = document.getElementById("progress");
  if (bar) {
    var upd = function () {
      var h = document.documentElement;
      var max = h.scrollHeight - h.clientHeight;
      bar.style.width = (max > 0 ? (h.scrollTop / max) * 100 : 0) + "%";
    };
    window.addEventListener("scroll", upd, { passive: true });
    upd();
  }

  // 4. Consentimiento de cookies + AdSense
  var KEY = "olfatecho_consent";
  var banner = document.getElementById("cookie-banner");

  function pushAdUnits() {
    document.querySelectorAll("ins.adsbygoogle").forEach(function (el) {
      if (el.getAttribute("data-adsbygoogle-status")) return;
      try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) {}
    });
  }

  function loadAds() {
    var c = window.ADSENSE_CLIENT;
    if (!c) return;
    // El script ya va en el <head> (necesario para verificar el sitio).
    // Aqui solo pedimos los anuncios cuando el usuario acepta.
    var previo = document.getElementById("adsbygoogle-js");
    if (previo) {
      if (window.adsbygoogle) pushAdUnits();
      else previo.addEventListener("load", pushAdUnits);
      return;
    }
    var s = document.createElement("script");
    s.id = "adsbygoogle-js";
    s.async = true;
    s.crossOrigin = "anonymous";
    s.src = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=" +
      encodeURIComponent(c);
    s.addEventListener("load", pushAdUnits);
    document.head.appendChild(s);
  }

  function loadGA() {
    var id = window.GA4_ID;
    if (!id || document.getElementById("ga4-js")) return;
    var s = document.createElement("script");
    s.id = "ga4-js";
    s.async = true;
    s.src = "https://www.googletagmanager.com/gtag/js?id=" + encodeURIComponent(id);
    document.head.appendChild(s);
    window.dataLayer = window.dataLayer || [];
    window.gtag = function () { window.dataLayer.push(arguments); };
    window.gtag("js", new Date());
    window.gtag("config", id);
  }

  function apply(v) {
    if (v === "ads") {
      loadAds();
      loadGA();
    }
  }

  var saved = null;
  try { saved = localStorage.getItem(KEY); } catch (e) {}

  function mostrarMuro() {
    if (banner) {
      banner.hidden = false;
      document.body.classList.add("cookie-lock");
    }
  }
  function cerrarMuro() {
    if (banner) banner.hidden = true;
    document.body.classList.remove("cookie-lock");
  }

  if (saved) apply(saved);
  else mostrarMuro();

  if (banner) {
    var ok = document.getElementById("cookie-ok");
    var no = document.getElementById("cookie-no");
    if (ok) ok.addEventListener("click", function () {
      try { localStorage.setItem(KEY, "ads"); } catch (e) {}
      cerrarMuro();
      apply("ads");
    });
    if (no) no.addEventListener("click", function () {
      try { localStorage.setItem(KEY, "no"); } catch (e) {}
      cerrarMuro();
    });
  }

  window.olfatechoCookies = function () {
    mostrarMuro();
  };
  document.querySelectorAll("[data-cookie-settings]").forEach(function (a) {
    a.addEventListener("click", function (e) {
      e.preventDefault();
      window.olfatechoCookies();
    });
  });

  // 5. Copiar enlace
  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var url = b.getAttribute("data-copy");
      var done = function () {
        var old = b.textContent;
        b.textContent = "¡Copiado!";
        setTimeout(function () { b.textContent = old; }, 1800);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(done).catch(function () {});
      } else {
        var t = document.createElement("textarea");
        t.value = url;
        document.body.appendChild(t);
        t.select();
        try { document.execCommand("copy"); done(); } catch (e) {}
        document.body.removeChild(t);
      }
    });
  });
})();
