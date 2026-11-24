# -*- coding: utf-8 -*-
"""Generador estático de la web de Olfatecho.

Lee las ediciones ya subidas a YouTube desde
../noticiasdiarias/storage/noticias_diarias y genera:

  docs/index.html
  docs/edicion/<fecha>-<edicion>.html
  docs/noticia/<fecha>-<edicion>-<n>-<titulo>.html
  docs/nosotros.html · docs/privacidad.html · docs/404.html
  docs/sitemap.xml · docs/rss.xml · docs/robots.txt · docs/ads.txt
  docs/CNAME (si hay dominio propio en dominio.txt)

No copia los artículos: titular + resumen corto + enlace al medio.
Uso:  python generar.py [--dominio olfatecho.com] [--base https://...]
"""
import argparse
import html
import json
import os
import re
import shutil
import unicodedata
from datetime import datetime, timedelta

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE = os.path.join(AQUI, "noticias")  # fuentes versionadas dentro del repo
SALIDA = os.path.join(AQUI, "docs")
RESUMEN_DIR = os.path.normpath(os.path.join(
    AQUI, "..", "noticiasdiarias", "storage", "horizontal"))
BASE_URL = os.getenv("OLFATECHO_BASE",
                     "https://edumilla1994.github.io/olfatecho-web").rstrip("/")
DOMINIO_FILE = os.path.join(AQUI, "dominio.txt")
EMAIL = "edumilla1994@gmail.com"
SITE_NAME = "Olfatecho Noticias"
DIAS_VENTANA = int(os.getenv("OLFATECHO_DIAS", "2"))

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _adsense_client():
    p = os.path.join(AQUI, "adsense.txt")
    try:
        if os.path.isfile(p):
            v = open(p, encoding="utf-8").read().strip().splitlines()[0].strip()
            v = v.lstrip("\ufeff").strip()
            if v.startswith("ca-pub-"):
                return v
    except OSError:
        pass
    return ""


ADSENSE_CLIENT = _adsense_client()


def _lineas_config(nombre):
    p = os.path.join(AQUI, nombre)
    out = []
    try:
        if os.path.isfile(p):
            for ln in open(p, encoding="utf-8"):
                ln = ln.strip().lstrip("\ufeff").strip()
                if ln and not ln.startswith("#"):
                    out.append(ln)
    except OSError:
        pass
    return out


ADSENSE_SLOTS = {}
for _ln in _lineas_config("adsense_slots.txt"):
    if "=" in _ln:
        _k, _v = _ln.split("=", 1)
        ADSENSE_SLOTS[_k.strip()] = _v.strip()
GA4_ID = (_lineas_config("ga4.txt") or [""])[0].strip()
GSC_TOKEN = (_lineas_config("google_site_verification.txt") or [""])[0].strip()


def ad_slot(key):
    """Banner manual de AdSense (solo si hay cliente y slot configurados)."""
    slot = ADSENSE_SLOTS.get(key, "")
    if not (ADSENSE_CLIENT and slot):
        return ""
    return ('<div class="ad-slot"><span class="ad-label">Publicidad</span>'
            '<ins class="adsbygoogle" style="display:block" '
            'data-ad-client="%s" data-ad-slot="%s" data-ad-format="auto" '
            'data-full-width-responsive="true"></ins></div>'
            % (esc(ADSENSE_CLIENT), esc(slot)))


def esc(s):
    return html.escape(str(s or ""), quote=True)


def slugify(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").lower()
    return s[:70].strip("-")


def fecha_larga(dt):
    return "%s, %d de %s de %d" % (DIAS[dt.weekday()], dt.day,
                                   MESES[dt.month - 1], dt.year)


def fecha_corta(dt):
    return "%d %s %d" % (dt.day, MESES[dt.month - 1][:3], dt.year)


def resumen(texto, titulo=""):
    t = re.sub(r"\s+", " ", (texto or "").strip())
    if not t:
        return ""
    if len(t) <= 340:
        return t
    cut = t[:340]
    p = cut.rfind(". ")
    if p >= 140:
        return cut[:p + 1]
    return cut.rsplit(" ", 1)[0].rstrip(".,;:") + "…"


def video_id(url):
    m = re.search(r"(?:youtu\.be/|v=)([A-Za-z0-9_-]{6,})", url or "")
    return m.group(1) if m else ""


def limpiar_titulo(t):
    """Quita emoji, prefijo de marca y '(primera edición)' para la web."""
    t = re.sub(r"^[^\wÁÉÍÓÚáéíóúÑñ]+", "", (t or "").strip())
    t = re.sub(r"^Olfatecho Noticias\s*[—–-]\s*", "", t, flags=re.I)
    t = re.sub(r"\s*\((primera|segunda|tercera|cuarta|quinta|sexta|séptima|"
               r"octava|novena|décima|undécima|duodécima|décima primera|"
               r"décima segunda|décima tercera|décima cuarta|décima quinta|"
               r"décima sexta|décima séptima|décima octava|décima novena|"
               r"vigésima)[^)]*edici[oó]n\)\s*$", "", t, flags=re.I)
    t = t.strip()
    return (t[:1].upper() + t[1:]) if t else t


def dominio_actual():
    try:
        if os.path.isfile(DOMINIO_FILE):
            d = open(DOMINIO_FILE, encoding="utf-8").read().strip()
            return d.replace("https://", "").replace("http://", "").strip("/")
    except OSError:
        pass
    return ""


def cargar_ediciones():
    eds = []
    if not os.path.isdir(FUENTE):
        return eds
    for d in sorted(os.listdir(FUENTE)):
        carpeta = os.path.join(FUENTE, d)
        nj = os.path.join(carpeta, "noticias.json")
        yj = os.path.join(carpeta, "subir_youtube.json")
        if not os.path.isfile(nj):
            continue
        # solo ediciones que ya tienen video en YouTube: la web nunca
        # muestra una edicion sin su video
        if not os.path.isfile(yj):
            continue
        try:
            j = json.load(open(nj, encoding="utf-8"))
            yt = json.load(open(yj, encoding="utf-8"))
        except Exception:
            continue
        noticias = [n for n in (j.get("noticias") or []) if n.get("title")]
        if not noticias:
            continue
        try:
            dt = datetime.strptime(j.get("fecha", "")[:19], "%Y-%m-%dT%H:%M:%S")
        except Exception:
            try:
                dt = datetime.strptime(d[:15], "%Y%m%d_%H%M%S")
            except Exception:
                continue
        ed_txt = (j.get("edicion") or "").strip() or "edición"
        slug = "%s-%s" % (dt.strftime("%Y-%m-%d"), slugify(ed_txt))
        vid = video_id(yt.get("url") or "")
        if not vid:
            continue
        titulo_yt = (yt.get("titulo") or "").strip()
        if not titulo_yt:
            titulo_yt = "Olfatecho Noticias — %s (%s)" % (fecha_larga(dt), ed_txt)
        stories = []
        for i, n in enumerate(noticias, 1):
            stories.append({
                "n": i,
                "title": (n.get("title") or "").strip(),
                "source": (n.get("source") or "").strip(),
                "link": (n.get("link") or "").strip(),
                "contexto": resumen(n.get("contexto"), n.get("title")),
                "cuerpo": (n.get("cuerpo") or "").strip(),
                "analisis": (n.get("analisis") or "").strip(),
                "genero": (n.get("genero") or "Actualidad").strip(),
                "ambito": (n.get("ambito") or "Perú").strip(),
                "published": (n.get("published") or "").strip(),
                "slug": "%s-%d-%s" % (slug, i, slugify(n.get("title"))[:60]),
            })
        img_src = ""
        fotos_dir = os.path.join(carpeta, "fotos")
        # 1) la foto de la PRIMERA historia (la del titular del hero)
        mat = os.path.join(carpeta, "material_manifest.json")
        if os.path.isfile(mat) and os.path.isdir(fotos_dir):
            try:
                manif = json.load(open(mat, encoding="utf-8"))
                for it in manif.get("items") or []:
                    if str(it.get("term")) != "0" or not it.get("selected", True):
                        continue
                    base = os.path.basename(it.get("path") or "")
                    stem = base.split("_540x960")[0].replace("webimg_", "")
                    for ext in (".jpg", ".jpeg", ".png", ".webp"):
                        p = os.path.join(fotos_dir, stem + ext)
                        if os.path.isfile(p):
                            img_src = p
                            break
                    if img_src:
                        break
            except Exception:
                pass
        # 2) respaldo: la foto más grande de la edición
        if not img_src and os.path.isdir(fotos_dir):
            imgs = [f for f in os.listdir(fotos_dir)
                    if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))]
            pref = [f for f in imgs if f.lower().startswith("story")]
            def _peso(f):
                n = f.lower()
                pri = 3 if "_a" in n else (2 if ("_du" in n or "_se" in n) else 1)
                try:
                    tam = os.path.getsize(os.path.join(fotos_dir, f))
                except OSError:
                    tam = 0
                return (pri, tam)
            cands = pref or imgs
            if cands:
                img_src = os.path.join(fotos_dir, max(cands, key=_peso))
        eds.append({
            "folder": d, "dt": dt, "edicion": ed_txt,
            "num": int(j.get("edicion_num") or 0),
            "slug": slug, "video": vid,
            "url": (yt.get("url") or "").strip(),
            "titulo": titulo_yt,
            "titulo_web": limpiar_titulo(titulo_yt),
            "img_src": img_src, "img": "",
            "stories": stories,
        })
    eds.sort(key=lambda e: e["dt"], reverse=True)
    # solo ediciones recientes: el archivo viejo no debe inundar la portada
    limite = datetime.now() - timedelta(days=DIAS_VENTANA)
    eds = [e for e in eds if e["dt"] >= limite]
    return eds


def cargar_resumenes():
    """Videos horizontales diarios subidos a YouTube (con miniatura y guion)."""
    out = []
    if not os.path.isdir(RESUMEN_DIR):
        return out
    for d in sorted(os.listdir(RESUMEN_DIR)):
        carpeta = os.path.join(RESUMEN_DIR, d)
        if not os.path.isdir(carpeta):
            continue
        yj = os.path.join(carpeta, "subir_youtube.json")
        tj = os.path.join(carpeta, "titulo_descripcion.txt")
        if not os.path.isfile(yj) or not os.path.isfile(tj):
            continue
        try:
            yt = json.load(open(yj, encoding="utf-8"))
        except Exception:
            continue
        vid = video_id(yt.get("url") or "")
        if not vid:
            continue
        chapters = []
        try:
            for ln in open(tj, encoding="utf-8"):
                m = re.match(r"^(\d{2}:\d{2})\s+(.+)$", ln.strip())
                if m:
                    chapters.append({"t": m.group(1), "title": m.group(2).strip()})
        except OSError:
            pass
        guiones = {}
        gj = os.path.join(carpeta, "guiones.json")
        if os.path.isfile(gj):
            try:
                guiones = json.load(open(gj, encoding="utf-8"))
            except Exception:
                pass
        mini = ""
        for name in ("miniatura_youtube_a.jpg", "miniatura.jpg"):
            p = os.path.join(carpeta, name)
            if os.path.isfile(p):
                mini = p
                break
        out.append({
            "folder": d, "video": vid, "url": (yt.get("url") or "").strip(),
            "titulo": (yt.get("titulo") or "Resumen diario").strip(),
            "fecha": (yt.get("fecha") or "")[:10],
            "chapters": chapters, "guiones": guiones, "miniatura": mini,
        })
    out.sort(key=lambda r: (r["fecha"], r["folder"]), reverse=True)
    return out


def thumb(ed):
    if ed.get("img"):
        return ed["img"]
    return "https://i.ytimg.com/vi/%s/hqdefault.jpg" % ed["video"] if ed["video"] else ""


def img_url(ed, root):
    u = thumb(ed)
    return u if u.startswith("http") else root + u


def og_abs(ed):
    u = thumb(ed)
    return u if u.startswith("http") else BASE_URL + "/" + u


def preparar_imagen(src, dst):
    try:
        from PIL import Image, ImageOps
        im = Image.open(src).convert("RGB")
        im = ImageOps.fit(im, (1280, 720), Image.LANCZOS, centering=(0.5, 0.42))
        im.save(dst, quality=84, optimize=True)
        return True
    except Exception:
        try:
            shutil.copyfile(src, dst)
            return True
        except Exception:
            return False


def head(titulo, desc, canonical, root, og_image="", jsonld=""):
    img = og_image or (BASE_URL + "/assets/og-default.jpg")
    ads = ""
    if ADSENSE_CLIENT:
        ads = ('<meta name="google-adsense-account" content="%s">\n'
               '<script>window.ADSENSE_CLIENT="%s";</script>\n'
               '<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=%s" crossorigin="anonymous"></script>\n'
               % (esc(ADSENSE_CLIENT), esc(ADSENSE_CLIENT), esc(ADSENSE_CLIENT)))
    extra = ""
    if GSC_TOKEN:
        extra += ('<meta name="google-site-verification" content="%s">\n'
                  % esc(GSC_TOKEN))
    if GA4_ID:
        extra += '<script>window.GA4_ID="%s";</script>\n' % esc(GA4_ID)
    return """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="{site}">
<meta property="og:title" content="{titulo}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{img}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{root}assets/favicon.png" type="image/png">
<link rel="apple-touch-icon" href="{root}assets/logo.png">
<meta name="theme-color" content="#b8431f">
<link rel="stylesheet" href="{root}assets/style.css">
{extra}{ads}{jsonld}
</head>
<body>
""".format(titulo=esc(titulo), desc=esc(desc), canonical=esc(canonical),
           site=esc(SITE_NAME), root=root, img=esc(img), ads=ads,
           extra=extra, jsonld=jsonld)


def cabecera(root):
    return """<div class="topbar"><div class="wrap">
<span>Perú y el mundo, en 2 minutos</span>
<span>{fecha}</span>
</div></div>
<header class="site-header"><div class="wrap">
<a class="logo" href="{root}index.html">
  <img class="logo-mark" src="{root}assets/logo.png" alt="Olfatecho">
  <span class="logo-text">OLFATECHO<small>NOTICIAS DEL PERÚ</small></span>
</a>
<button class="nav-toggle" aria-label="Abrir menú" aria-expanded="false">Menú</button>
<nav class="nav" id="nav">
  <a href="{root}index.html">Inicio</a>
  <a href="{root}index.html#ediciones">Ediciones</a>
  <a href="{root}resumen-diario.html">Resumen diario</a>
  <a href="{root}categoria/index.html">Categorías</a>
  <a href="{root}nosotros.html">Nosotros</a>
  <a href="{root}apoyanos.html">Apóyanos</a>
  <a href="https://youtube.com/@Olfatecho" target="_blank" rel="noopener">YouTube</a>
  <a href="{root}privacidad.html">Privacidad</a>
</nav>
</div></header>
""".format(root=root, fecha=esc(fecha_larga(datetime.now())))


def pie(root):
    cookie = """<div class="cookie-wall" id="cookie-banner" hidden>
<div class="cookie-card">
<h2>Antes de seguir</h2>
<p>Usamos cookies propias y de terceros (Google AdSense y analítica) para mostrar anuncios y medir el tráfico. Puedes aceptar o rechazar; si rechazas, no cargamos publicidad ni analítica.</p>
<div class="cookie-actions"><button class="no" id="cookie-no">Rechazar</button><button class="ok" id="cookie-ok">Aceptar</button></div>
<p class="cookie-note"><a href="{root}privacidad.html">Política de privacidad</a></p>
</div></div>""".format(root=root)
    return cookie + """<footer class="site-footer"><div class="wrap">
<div class="footer-grid">
  <div>
    <h4>Olfatecho</h4>
    <p>Noticias del Perú y el mundo en ediciones cortas, con enlaces a las fuentes originales para que puedas leer la nota completa.</p>
  </div>
  <div>
    <h4>Secciones</h4>
    <p><a href="{root}index.html">Inicio</a></p>
    <p><a href="{root}index.html#ediciones">Ediciones</a></p>
    <p><a href="{root}nosotros.html">Nosotros</a></p>
    <p><a href="{root}apoyanos.html">Apóyanos</a></p>
    <p><a href="{root}privacidad.html">Privacidad</a></p>
    <p><a href="#" data-cookie-settings>Cookies</a></p>
  </div>
  <div>
    <h4>Contacto</h4>
    <p><a href="mailto:{email}">{email}</a></p>
    <p>YouTube: <a href="https://youtube.com/@Olfatecho" rel="noopener">@Olfatecho</a></p>
  </div>
</div>
<div class="copy"><span>© {anio} Olfatecho. Todos los derechos reservados.</span>
<span>Hecho en Perú</span></div>
</div></footer>
<script src="{root}assets/app.js" defer></script>
</body></html>
""".format(root=root, email=EMAIL, anio=datetime.now().year)


def titular_edicion(ed):
    """Titular de la noticia principal de la edición (para las tarjetas)."""
    if ed.get("stories"):
        t = ed["stories"][0]["title"]
        src = ed["stories"][0].get("source") or ""
        if src:
            t = re.sub(r"\s*[-–—]\s*" + re.escape(src) + r"\s*$", "",
                       t, flags=re.I).strip()
        return t or ed["titulo_web"]
    return ed["titulo_web"] or "Olfatecho Noticias"


def tarjeta_edicion(ed, root, i=0):
    tit = titular_edicion(ed)
    play = ('<span class="card-play" aria-hidden="true">▶</span>'
            if ed.get("video") else "")
    return """<a class="card reveal" href="{root}edicion/{slug}.html" style="--d:{d}s">
<div class="card-media"><img src="{img}" alt="{alt}" loading="lazy">{play}</div>
<div class="card-body">
  <span class="card-genre">{edicion}</span>
  <h3>{titulo}</h3>
  <span class="meta">{fecha} · {n} noticias</span>
</div></a>""".format(
        root=root, slug=ed["slug"], img=esc(img_url(ed, root)),
        alt=esc(tit), edicion=esc(ed["edicion"].capitalize()),
        titulo=esc(tit), fecha=esc(fecha_corta(ed["dt"])),
        n=len(ed["stories"]), d=(i % 3) * 0.08, play=play)


def item_noticia(ed, s, root, i=0):
    return """<a class="news-item reveal" href="{root}noticia/{slug}.html" style="--d:{d}s">
<div class="genre">{genero}</div>
<h3>{titulo}</h3>
<p>{resumen}</p>
<div class="meta">{fuente} · {edicion}</div>
</a>""".format(
        root=root, slug=s["slug"], genero=esc(s["genero"]),
        titulo=esc(s["title"]), resumen=esc(s["contexto"] or s["title"]),
        fuente=esc(s["source"]), edicion=esc(ed["edicion"].capitalize()),
        d=(i % 3) * 0.08)


def seccion_resumen(resumenes, root):
    if not resumenes:
        return ""
    r = resumenes[0]
    fecha = r["guiones"].get("fecha") or r["fecha"]
    return """<section class="section" id="resumen-diario"><div class="wrap">
<div class="section-head"><h2>Resumen diario</h2><a class="more-link" href="{root}resumen-diario.html">Capítulos y transcripción →</a></div>
<div class="video-frame"><iframe src="https://www.youtube-nocookie.com/embed/{vid}" title="{titulo}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>
<div class="hero-actions" style="margin-top:14px">
<a class="btn" href="{url}" target="_blank" rel="noopener">▶ Ver en YouTube</a>
<a class="btn btn-ghost" href="{root}resumen-diario.html">Ver capítulos y transcripción</a>
<span class="hero-edition">Resumen completo · {fecha}</span>
</div></div></section>""".format(
        root=root, vid=r["video"], titulo=esc(r["titulo"]),
        url=esc(r["url"]), fecha=esc(fecha))


def generar_resumen_diario(resumenes):
    root = ""
    if not resumenes:
        return generar_pagina(
            "Resumen diario", "El resumen completo del día.",
            "resumen-diario",
            "<h1>Resumen diario</h1><p>Aún no hay un resumen diario "
            "publicado. Vuelve más tarde.</p>")
    r = resumenes[0]
    fecha = r["guiones"].get("fecha") or r["fecha"]
    caps = ""
    for c in r["chapters"]:
        caps += "<li><strong>%s</strong> %s</li>" % (
            esc(c["t"]), esc(c["title"]))
    if caps:
        caps = '<h2>Capítulos</h2><ol class="chapters">%s</ol>' % caps
    trans = ""
    g = r["guiones"]
    if g.get("historias"):
        trans = '<h2>Transcripción del resumen</h2><div class="transcript">'
        if g.get("intro"):
            trans += "<p>%s</p>" % esc(g["intro"])
        for h in g["historias"]:
            trans += "<h3>%s</h3>" % esc(h.get("title") or "")
            for p in re.split(r"\n\s*\n", h.get("guion") or ""):
                if p.strip():
                    trans += "<p>%s</p>" % esc(p.strip())
            if h.get("source"):
                trans += ('<p class="source-mini">Fuente: %s</p>'
                          % esc(h["source"]))
        trans += "</div>"
    arch = ""
    if len(resumenes) > 1:
        items = "".join(
            '<li><a href="%s" target="_blank" rel="noopener">%s</a> '
            '<span>%s</span></li>' % (esc(x["url"]), esc(x["titulo"]),
                                      esc(x["fecha"]))
            for x in resumenes[1:12])
        arch = ('<h2>Resúmenes anteriores</h2><ul class="archive">%s</ul>'
                % items)
    doc = head("Resumen diario — Olfatecho",
               "El resumen completo del día en video, con capítulos y "
               "transcripción.",
               BASE_URL + "/resumen-diario.html", root,
               og_image="https://i.ytimg.com/vi/%s/maxresdefault.jpg"
                        % r["video"])
    doc += cabecera(root)
    doc += """<main class="wrap"><div class="page">
<span class="genre">Resumen diario</span>
<h1>Las noticias del día, completas</h1>
<div class="meta" style="color:var(--muted);font-size:var(--fs-small);padding:0 0 18px">%s · Olfatecho Noticias</div>
<div class="video-frame"><iframe src="https://www.youtube-nocookie.com/embed/%s" title="%s" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>
<div class="video-actions">
<a class="btn" href="%s" target="_blank" rel="noopener">▶ Abrir en YouTube</a>
<a class="btn btn-ghost" href="https://youtube.com/@Olfatecho" target="_blank" rel="noopener">Suscríbete a Olfatecho</a>
</div>
%s
%s
%s
<p style="margin-top:34px"><a class="btn btn-ghost" href="index.html">← Volver al inicio</a></p>
</div></main>""" % (esc(fecha), r["video"], esc(r["titulo"]), esc(r["url"]),
                     caps, trans, arch)
    doc += pie(root)
    return doc


def generar_inicio(eds, resumenes=None):
    root = ""
    if not eds:
        doc = head(SITE_NAME, "Noticias del Perú y el mundo.", BASE_URL + "/", root)
        doc += cabecera(root) + '<main class="wrap"><div class="empty">Todavía no hay ediciones publicadas.</div></main>' + pie(root)
        return doc
    portada = eds[0]
    lead_story = portada["stories"][0] if portada["stories"] else None
    titular = (lead_story["title"] if lead_story else
               (portada["titulo_web"] or "Olfatecho Noticias"))
    if lead_story and lead_story.get("source"):
        titular = re.sub(r"\s*[-–—]\s*" + re.escape(lead_story["source"]) + r"\s*$",
                         "", titular, flags=re.I).strip()
    hero = """<section class="hero"><div class="wrap"><div class="hero-grid">
<div class="hero-copy">
  <h1>{titular}</h1>
  <p class="hero-lead">{lead}</p>
  <div class="hero-actions">
    <a class="btn" href="{root}edicion/{slug}.html">Ver la edición completa →</a>
    <span class="hero-edition">Última edición · {fecha} · {edicion}</span>
  </div>
</div>
<div class="hero-media">
  <a href="{root}edicion/{slug}.html"><img src="{img}" alt="{alt}">
  {play}</a>
</div>
</div></div></section>""".format(
        root=root, slug=portada["slug"], img=esc(img_url(portada, root)),
        alt=esc(portada["titulo_web"]), titular=esc(titular),
        play=('<span class="play"><span>▶</span></span>'
              if portada.get("video") else ""),
        lead=esc(portada["stories"][0]["contexto"] if portada["stories"] else ""),
        fecha=esc(fecha_corta(portada["dt"])),
        edicion=esc(portada["edicion"].capitalize()))

    grid = "".join(tarjeta_edicion(e, root, i) for i, e in enumerate(eds[1:13]))
    ultimas = ""
    k = 0
    for e in eds[:3]:
        for s in e["stories"][:3]:
            ultimas += item_noticia(e, s, root, k)
            k += 1
    side = """<div class="side-box reveal">
<h3>La noticia, completa</h3>
<p>Cada edición dura menos de dos minutos. En la web tienes el resumen de cada historia y el enlace directo al medio original para leerla completa.</p>
<a class="btn" href="{root}nosotros.html">Conoce Olfatecho →</a>
<p style="margin:14px 0 0"><a href="{root}apoyanos.html" style="color:#f6efe3;text-decoration:underline">Apóyanos con un Yape o BIM →</a></p>
</div>""".format(root=root)

    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "WebSite",
        "name": SITE_NAME, "url": BASE_URL + "/",
    }, ensure_ascii=False)

    doc = head("Olfatecho Noticias — Perú y el mundo, en 2 minutos",
               "Ediciones cortas de noticias del Perú y el mundo, con enlaces a las fuentes originales.",
               BASE_URL + "/", root, og_image=og_abs(portada),
               jsonld='<script type="application/ld+json">%s</script>' % jsonld)
    doc += cabecera(root)
    doc += hero
    doc += ad_slot("home_top")
    doc += seccion_resumen(resumenes or [], root)
    doc += """<section class="section" id="ediciones"><div class="wrap">
<div class="section-head"><h2>Ediciones recientes</h2><a class="more-link" href="#ediciones">Una mirada rápida, todos los días</a></div>
<div class="grid-3">%s</div></div></section>""" % grid
    doc += ad_slot("home_mid")
    doc += """<section class="section"><div class="wrap"><div class="news-list">
<div><div class="section-head"><h2>Últimas noticias</h2></div>%s</div>
<div>%s</div>
</div></div></section>""" % (ultimas, side)
    doc += pie(root)
    return doc


def generar_edicion(ed, eds):
    root = "../"
    idx = eds.index(ed)
    prev_ed = eds[idx + 1] if idx + 1 < len(eds) else None
    next_ed = eds[idx - 1] if idx > 0 else None
    stories = ""
    for i, s in enumerate(ed["stories"]):
        _an = (s.get("analisis") or "").strip()
        _an_html = ('<p class="why-mini"><strong>Por qu? importa:</strong> %s</p>'
                    % esc(_an)) if _an else ""
        stories += """<article class="story-card reveal" style="--d:{d}s">
<div class="genre">{genero}</div>
<h2><a href="{root}noticia/{slug}.html">{titulo}</a></h2>
<p>{resumen}</p>
{an_html}
<div class="story-links">
  <a href="{root}noticia/{slug}.html">Leer el resumen →</a>
  {fuente_link}
</div></article>""".format(
            d=(i % 3) * 0.08, genero=esc(s["genero"]), root=root, slug=s["slug"],
            titulo=esc(s["title"]), resumen=esc(s["contexto"] or s["title"]),
            an_html=_an_html,
            fuente_link=('<a href="%s" target="_blank" rel="noopener nofollow">'
                         'Nota completa en %s ↗</a>' % (esc(s["link"]), esc(s["source"])))
            if s["link"] else "")
    nav = ""
    if prev_ed:
        nav += '<a class="btn btn-ghost" href="%s.html">← %s</a>' % (prev_ed["slug"], esc(prev_ed["edicion"].capitalize()))
    if next_ed:
        nav += '<a class="btn btn-ghost" href="%s.html" style="margin-left:8px">%s →</a>' % (next_ed["slug"], esc(next_ed["edicion"].capitalize()))

    video = ""
    if ed["video"]:
        video = """<div class="video-frame"><iframe src="https://www.youtube-nocookie.com/embed/{vid}" title="{titulo}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>
<div class="video-actions">
<a class="btn" href="{url}" target="_blank" rel="noopener">▶ Abrir en YouTube</a>
<a class="btn btn-ghost" href="https://youtube.com/@Olfatecho" target="_blank" rel="noopener">Suscríbete a Olfatecho</a>
</div>""".format(vid=ed["video"], titulo=esc(ed["titulo_web"]),
                 url=esc(ed["url"]))

    doc = head("%s — %s" % (ed["titulo_web"] or ed["edicion"], SITE_NAME),
               "Edición del %s con %d noticias del Perú y el mundo." % (fecha_larga(ed["dt"]), len(ed["stories"])),
               "%s/edicion/%s.html" % (BASE_URL, ed["slug"]), root,
               og_image=og_abs(ed))
    doc += cabecera(root)
    doc += """<div class="progress" id="progress"></div>
<main class="wrap"><div class="edition-head">
<div class="breadcrumb"><a href="{root}index.html">Inicio</a> / Ediciones</div>
<h1>{titulo}</h1>
<div class="edition-meta"><span>{edicion}</span><span>·</span><span>{fecha}</span><span>·</span><span>{n} noticias</span></div>
</div>
{video}
{ad_top}
<section class="section" style="padding-top:22px">{stories}</section>
{ad_bottom}
<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:10px 0 30px">{nav}</div>
</main>""".format(root=root, titulo=esc(ed["titulo_web"] or "Olfatecho Noticias"),
                 edicion=esc(ed["edicion"].capitalize()),
                 fecha=esc(fecha_larga(ed["dt"])), n=len(ed["stories"]),
                 video=video, stories=stories, nav=nav,
                 ad_top=ad_slot("edition_top"),
                 ad_bottom=ad_slot("edition_bottom"))
    doc += pie(root)
    return doc


def generar_noticia(ed, s, eds):
    root = "../"
    otras = [x for x in ed["stories"] if x["slug"] != s["slug"]]
    mas = "".join('<a href="%s.html">%s</a>' % (x["slug"], esc(x["title"])) for x in otras)
    fuente = ""
    if s["link"]:
        fuente = """<div class="source-box">
<span>Este es un resumen. La nota completa es de <strong>{fuente}</strong>.</span>
<a href="{link}" target="_blank" rel="noopener nofollow">Leer en {fuente} ↗</a>
</div>""".format(fuente=esc(s["source"]), link=esc(s["link"]))
    video = ""
    if ed["video"]:
        video = """<div class="video-frame"><iframe src="https://www.youtube-nocookie.com/embed/{vid}" title="{titulo}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>
<div class="video-cta">
<div class="video-cta-copy"><strong>Esta noticia está en el video de hoy</strong>
<span>Mira la edición completa, con las demás noticias y sus fuentes.</span></div>
<div class="video-cta-actions">
<a class="btn" href="{url}" target="_blank" rel="noopener">▶ Ver el video en YouTube</a>
<a class="btn btn-ghost" href="{root}edicion/{eslug}.html">Ver la edición</a>
<a class="btn btn-ghost" href="https://youtube.com/@Olfatecho" target="_blank" rel="noopener">Suscríbete</a>
</div></div>""".format(vid=ed["video"], titulo=esc(ed["titulo_web"]),
                            url=esc(ed["url"]), root=root, eslug=ed["slug"])

    texto = (s["contexto"] or "").strip()
    titulo_plano = re.sub(r"\s+", " ", s["title"]).strip()
    if texto and titulo_plano and texto.lower().startswith(titulo_plano.lower()[:60]):
        texto = texto[len(titulo_plano):].lstrip(" .:-–—")
    partes = re.split(r"(?<=[.!?])\s+", texto.strip()) if texto else []
    lede = partes[0] if partes else (s["contexto"] or s["title"])
    cuerpo = " ".join(partes[1:]).strip() if len(partes) > 1 else ""
    largo = (s.get("cuerpo") or "").strip()
    if largo:
        parrafos = [x.strip() for x in re.split(r"\n\s*\n", largo) if x.strip()]
        if len(parrafos) < 2:
            parrafos = [x.strip() for x in largo.split("\n") if x.strip()]
        body_block = ('<div class="body">' +
                      "".join("<p>%s</p>" % esc(x) for x in parrafos) +
                      "</div>") if parrafos else ""
    else:
        body_block = ('<div class="body"><p>%s</p></div>' % esc(cuerpo)) if cuerpo else ""
    analisis_txt = (s.get("analisis") or "").strip()
    analisis_box = ('<div class="why-box"><span class="why-label">Por qué importa</span>'
                    '<p>%s</p></div>' % esc(analisis_txt)) if analisis_txt else ""

    canonical = "%s/noticia/%s.html" % (BASE_URL, s["slug"])
    share = """<div class="share">
<a href="https://wa.me/?text={wa}" target="_blank" rel="noopener">WhatsApp</a>
<a href="https://twitter.com/intent/tweet?text={tw}&url={url}" target="_blank" rel="noopener">X</a>
<button type="button" data-copy="{url}">Copiar enlace</button>
</div>""".format(wa=esc(s["title"] + " " + canonical), tw=esc(s["title"]), url=esc(canonical))

    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": s["title"], "description": s["contexto"],
        "datePublished": ed["dt"].isoformat(),
        "author": {"@type": "Organization", "name": SITE_NAME},
        "publisher": {"@type": "Organization", "name": SITE_NAME},
        "mainEntityOfPage": canonical, "isBasedOn": s["link"] or "",
    }, ensure_ascii=False)

    doc = head("%s — %s" % (s["title"], SITE_NAME), s["contexto"] or s["title"],
               canonical, root, og_image=og_abs(ed),
               jsonld='<script type="application/ld+json">%s</script>' % jsonld)
    doc += cabecera(root)
    doc += """<div class="progress" id="progress"></div>
<main class="wrap"><article class="article">
<div class="breadcrumb"><a href="{root}index.html">Inicio</a> / <a href="{root}edicion/{eslug}.html">{edicion}</a></div>
<span class="genre" style="color:var(--terra);font-size:var(--fs-small);font-weight:700">{genero}</span>
<h1>{titulo}</h1>
<div class="meta"><span>{fuente}</span><span>·</span><span>{fecha}</span><span>·</span><span>{ambito}</span></div>
<p class="lede">{resumen}</p>
{share}
{ad_top}
{body_block}
{analisis_box}
{fuente_box}
{video}
{ad_bottom}
<div class="more"><h3>Más de esta edición</h3>{mas}</div>
</article></main>""".format(
        root=root, eslug=ed["slug"], edicion=esc(ed["edicion"].capitalize()),
        genero=esc(s["genero"]), titulo=esc(s["title"]), fuente=esc(s["source"]),
        fecha=esc(fecha_larga(ed["dt"])), ambito=esc(s["ambito"]),
        resumen=esc(lede), share=share, body_block=body_block,
        analisis_box=analisis_box,
        fuente_box=fuente, video=video, mas=mas,
        ad_top=ad_slot("story_top"),
        ad_bottom=ad_slot("story_bottom"))
    doc += pie(root)
    return doc


CATEGORIAS = [
    ("politica", "Política",
     "El Congreso, el Gobierno, las elecciones, los partidos y las decisiones "
     "que cambian el país. Reunimos lo más importante del día y lo explicamos "
     "con contexto para entenderlo sin ruido."),
    ("economia", "Economía",
     "Precios, empleo, empresas, inversiones y la economía peruana con datos. "
     "Lo que afecta a tu bolsillo y al país, en lenguaje claro."),
    ("seguridad", "Seguridad",
     "Delincuencia, extorsión, minería ilegal, cárceles y el trabajo de la "
     "policía y la justicia. Los hechos, las cifras y las respuestas del Estado."),
    ("regiones", "Regiones",
     "Lo que pasa fuera de Lima: gobiernos regionales, municipalidades, "
     "sequías, lluvias, obras y la vida en los departamentos del Perú."),
    ("mundo", "Mundo",
     "Las noticias internacionales que importan para el Perú: América Latina, "
     "Estados Unidos, Europa y el resto del mundo."),
    ("salud", "Salud",
     "Hospitales, EsSalud, campañas de vacunación, enfermedades y todo lo que "
     "afecta la salud de las personas en el Perú."),
    ("sociedad", "Sociedad",
     "Historias de personas, cultura, educación y la vida cotidiana del país, "
     "contadas con respeto y sin sensacionalismo."),
    ("gastronomia", "Gastronomía",
     "La cocina peruana en el mundo, restaurantes, chefs y todo lo que pone "
     "al Perú en la mesa internacional."),
    ("sucesos", "Sucesos",
     "Accidentes, emergencias y hechos policiales reportados por los medios "
     "locales, con los datos verificados."),
]


def generar_categoria(nombre, slug, intro, historias):
    root = "../"
    hist = sorted(historias, key=lambda x: x[0]["dt"], reverse=True)[:30]
    filas = ""
    for ed, s in hist:
        filas += """<article class="story-card">
<div class="genre">{genero}</div>
<h2><a href="{root}noticia/{slug}.html">{titulo}</a></h2>
<p>{resumen}</p>
<div class="story-links"><a href="{root}noticia/{slug}.html">Leer la noticia →</a>
<span class="meta">{fecha} · {edicion}</span></div>
</article>""".format(genero=esc(s["genero"]), root=root, slug=s["slug"],
                    titulo=esc(s["title"]),
                    resumen=esc(s["contexto"] or s["title"]),
                    fecha=esc(fecha_corta(ed["dt"])),
                    edicion=esc(ed["edicion"].capitalize()))
    if not filas:
        filas = "<p>Todavía no hay noticias en esta sección.</p>"
    doc = head("%s — Olfatecho" % nombre,
               intro[:160],
               "%s/categoria/%s.html" % (BASE_URL, slug), root)
    doc += cabecera(root)
    doc += """<main class="wrap"><div class="page">
<div class="breadcrumb"><a href="{root}index.html">Inicio</a> / <a href="{root}categoria/index.html">Categorías</a></div>
<h1>{nombre}</h1>
<p class="intro">{intro}</p>
<div class="story-list">{filas}</div>
<p style="margin-top:30px"><a class="btn btn-ghost" href="{root}categoria/index.html">← Todas las categorías</a></p>
</div></main>""".format(root=root, nombre=esc(nombre), intro=esc(intro),
                       filas=filas)
    doc += pie(root)
    return doc


def generar_categoria_index(por_cat):
    root = ""
    cards = ""
    for slug, nombre, intro in CATEGORIAS:
        n = len(por_cat.get(nombre, []))
        cards += """<a class="cat-card" href="{root}categoria/{slug}.html">
<h2>{nombre}</h2><p>{intro}</p><span class="meta">{n} noticias</span></a>""".format(
            root=root, slug=slug, nombre=esc(nombre), intro=esc(intro), n=n)
    doc = head("Categorías — Olfatecho",
               "Todas las secciones de Olfatecho: política, economía, "
               "seguridad, regiones, mundo, salud, sociedad, gastronomía y sucesos.",
               BASE_URL + "/categoria/index.html", root)
    doc += cabecera(root)
    doc += """<main class="wrap"><div class="page">
<div class="breadcrumb"><a href="{root}index.html">Inicio</a> / Categorías</div>
<h1>Categorías</h1>
<p class="intro">Elige la sección que te interese. Cada noticia incluye el
resumen, el análisis de por qué importa y el enlace al medio original.</p>
<div class="cat-grid">{cards}</div>
</div></main>""".format(root=root, cards=cards)
    doc += pie(root)
    return doc


def metodologia():
    return """<h1>Cómo trabajamos</h1>
<p class="intro">Olfatecho Noticias es un proyecto peruano de información
rápida y verificada. Esto es exactamente cómo hacemos cada edición.</p>
<h2>1. Seleccionamos</h2>
<p>Revisamos los medios peruanos y las fuentes oficiales durante todo el día.
Elegimos las noticias que explican qué pasó, por qué importa y qué puede
pasar después. No copiamos notas: resumimos y enlazamos a la fuente original
para que puedas leerla completa.</p>
<h2>2. Verificamos</h2>
<p>Cada dato, cifra, nombre y fecha se comprueba con la fuente original o con
una segunda fuente. Si algo no está confirmado, se dice que está por
confirmarse. No publicamos rumores.</p>
<h2>3. Escribimos y narramos</h2>
<p>El texto de cada noticia es nuestro: está parafraseado y explicado con
contexto. El video se produce con voz, imágenes de la noticia y subtítulos.
También incluimos un análisis breve de por qué importa cada noticia.</p>
<h2>4. Publicamos y corregimos</h2>
<p>Las ediciones se publican durante el día y el resumen completo cada
tarde. Si detectamos un error, lo corregimos en el video, en la web y
lo señalamos.</p>
<h2>5. Independencia</h2>
<p>Olfatecho no pertenece a ningún partido, empresa o medio. El proyecto se
financia con la publicidad y el apoyo de sus lectores (Yape y BIM).</p>
<p><strong>Transparencia:</strong> los videos y textos de Olfatecho se
generan con herramientas de inteligencia artificial supervisadas por el
equipo editorial. La responsabilidad del contenido es de Olfatecho.</p>
<p style="margin-top:26px"><a class="btn" href="apoyanos.html">Apóyanos →</a></p>"""


def fuentes():
    return """<h1>Fuentes y verificación</h1>
<p class="intro">Trabajamos con información pública y con los medios de
comunicación del Perú. Estas son las fuentes que más usamos y cómo las
utilizamos.</p>
<h2>Medios de comunicación</h2>
<p>El Comercio, Gestión, RPP, La República, Correo, Andina, Infobae, Trome,
Ojo, Exitosa, Radio Programas, América TV, Canal N, TV Perú, Latina,
Panamericana, entre otros. Siempre enlazamos la nota original para que
puedas leerla completa.</p>
<h2>Fuentes oficiales</h2>
<p>Instituto Nacional de Estadística e Informática (INEI), Banco Central de
Reserva (BCRP), Ministerio de Economía y Finanzas (MEF), Presidencia del
Consejo de Ministros (PCM), Congreso de la República, Jurado Nacional de
Elecciones (JNE), Oficina Nacional de Procesos Electorales (ONPE), Reniec,
Poder Judicial, Ministerio Público, Policía Nacional del Perú, Ministerio del
Interior, Ministerio de Defensa, Ministerio de Salud, EsSalud, Senamhi,
Defensoría del Pueblo, gobiernos regionales y municipalidades.</p>
<h2>Cómo verificamos</h2>
<p>1) Confirmamos el dato en la fuente original. 2) Si es posible, lo
contrastamos con una segunda fuente. 3) Separamos los hechos de las opiniones.
4) Si algo no está claro, lo señalamos en el texto.</p>
<h2>Correcciones</h2>
<p>Si encuentras un error, escríbenos. Corregimos el texto en la web y, si el
error está en un video, lo corregimos en la descripción y en la web.</p>
<p style="margin-top:26px"><a class="btn" href="metodologia.html">Cómo trabajamos →</a></p>"""


def glosario():
    return """<h1>Glosario</h1>
<p class="intro">Estos son los términos que más se repiten en las noticias
peruanas, explicados de forma sencilla.</p>
<h2>Economía y finanzas</h2>
<p><strong>BCRP:</strong> Banco Central de Reserva del Perú; cuida la moneda
y la estabilidad de precios. <strong>MEF:</strong> Ministerio de Economía y
Finanzas; administra el presupuesto del país. <strong>PBI:</strong> Producto
Interno Bruto; mide todo lo que produce la economía. <strong>Inflación:</strong>
el aumento general de precios. <strong>S/.:</strong> el sol, la moneda peruana.</p>
<h2>Política e instituciones</h2>
<p><strong>Congreso:</strong> el Poder Legislativo; hace las leyes.
<strong>JNE:</strong> Jurado Nacional de Elecciones; organiza y fiscaliza las
elecciones. <strong>ONPE:</strong> Oficina Nacional de Procesos Electorales;
ejecuta los procesos electorales. <strong>PCM:</strong> Presidencia del Consejo
de Ministros; coordina el trabajo del gobierno. <strong>GORE:</strong> gobierno
regional. <strong>TC:</strong> Tribunal Constitucional.</p>
<h2>Seguridad y justicia</h2>
<p><strong>Extorsión:</strong> exigir dinero bajo amenazas. <strong>Sicariato:</strong>
asesinatos pagados. <strong>Minería ilegal:</strong> extracción de minerales
sin autorización. <strong>INPE:</strong> Instituto Nacional Penitenciario;
administra los penales. <strong>Ministerio Público:</strong> la fiscalía;
investiga y acusa. <strong>Poder Judicial:</strong> los jueces.</p>
<h2>Clima y ambiente</h2>
<p><strong>El Niño:</strong> fenómeno climático que calienta el mar y cambia
las lluvias. <strong>Senamhi:</strong> Servicio Nacional de Meteorología e
Hidrología. <strong>Coastal El Niño:</strong> variante costera del fenómeno.
<strong>Sequía:</strong> falta prolongada de lluvias.</p>
<h2>Sociedad</h2>
<p><strong>EsSalud:</strong> seguro social de salud. <strong>Reniec:</strong>
registro de identidad y estado civil. <strong>Fieles:</strong> personas que
participan de una celebración religiosa.</p>
<p style="margin-top:26px"><a class="btn" href="index.html">Volver al inicio →</a></p>"""


def generar_pagina(titulo, desc, slug, contenido):
    root = ""
    doc = head("%s — %s" % (titulo, SITE_NAME), desc, "%s/%s.html" % (BASE_URL, slug), root)
    doc += cabecera(root)
    doc += '<main class="wrap"><div class="page">%s</div></main>' % contenido
    doc += pie(root)
    return doc


def nosotros():
    return """<h1>¿Qué es Olfatecho?</h1>
<p>Olfatecho es un noticiero peruano que resume las noticias más importantes del día en ediciones de menos de dos minutos. Cada historia tiene su espacio en esta web con un resumen claro y el enlace directo al medio que la publicó.</p>
<p>Lo hace <strong>Eduardo Milla</strong>, con la idea de que enterarse de las noticias no tiene que tomar media hora.</p>
<h2>Nuestro compromiso</h2>
<p>No inventamos ni copiamos artículos: contamos lo esencial y te llevamos a la fuente original para que puedas leer la nota completa y sacar tus conclusiones.</p>
<h2>¿Cómo funciona?</h2>
<ul>
<li>Revisamos medios peruanos e internacionales durante el día.</li>
<li>Elegimos las historias más relevantes y las narramos en video.</li>
<li>Publicamos la edición en YouTube y aquí encuentras el resumen y las fuentes.</li>
</ul>
<p>¿Tienes un dato, una corrección o una sugerencia? Escríbenos a <a href="mailto:%s">%s</a>.</p>""" % (EMAIL, EMAIL)


def apoyanos():
    return """<div class="support-intro">
  <div class="avatar">EM</div>
  <div><p class="support-name">Eduardo Milla</p><p class="support-role">Editor de Olfatecho</p></div>
</div>
<h1>Apóyanos</h1>
<p>Olfatecho es un noticiero independiente que hago yo, todos los días, con feeds, café y muchas ganas. No hay una redacción enorme detrás ni un presupuesto que lo sostenga: solo este proyecto y tú del otro lado.</p>
<p>Si te sirve para enterarte rápido de lo que pasa en el Perú y el mundo, puedes invitarme un café con Yape o BIM. Cada aporte ayuda a pagar el internet, la luz y las horas de edición para que las ediciones sigan saliendo.</p>
<div class="qr-grid">
  <div class="qr-card"><img src="assets/yape.jpg" alt="Código QR de Yape de Eduardo Milla"><h2>Yape</h2><p class="qr-name">Eduardo Milla</p><p>Escanea el QR desde tu app Yape.</p></div>
  <div class="qr-card"><img src="assets/bim.jpg" alt="Código QR de BIM de Eduardo Milla"><h2>BIM</h2><p class="qr-name">Eduardo Milla</p><p>Escanea el QR desde tu app BIM.</p></div>
</div>
<p class="qr-note">Gracias por el apoyo. Si no puedes aportar, compartir la web o un video también ayuda un montón.</p>
<p class="support-sign">— Eduardo Milla</p>"""


def privacidad():
    return """<h1>Política de privacidad</h1>
<p>Última actualización: %s.</p>
<p>Olfatecho Noticias es un sitio informativo. Esta política explica qué datos se usan cuando visitas la web o ves nuestros videos.</p>
<h2>Datos que recopilamos</h2>
<p>No pedimos registro ni datos personales para leer las noticias. El sitio es estático y no tiene formularios de usuario.</p>
<h2>Cookies y publicidad</h2>
<p>Usamos cookies propias y de terceros para mostrar anuncios y medir el tráfico. El proveedor de publicidad es <strong>Google AdSense</strong>, que puede usar cookies para mostrarte anuncios según tus visitas a este y otros sitios. Puedes aceptar o rechazar estas cookies en el aviso que aparece al entrar; si rechazas, no cargamos el script de publicidad.</p>
<p>Más información: <a href="https://policies.google.com/technologies/ads" target="_blank" rel="noopener">Cómo usa Google las cookies en publicidad</a>.</p>
<h2>Videos</h2>
<p>Los videos se muestran con el reproductor de YouTube (modo privacidad mejorada). YouTube y Google pueden usar cookies propias según sus políticas.</p>
<h2>Enlaces a otros medios</h2>
<p>Cada noticia enlaza al artículo original de su medio. Al hacer clic saldrás de Olfatecho y se aplicarán las políticas del sitio de destino.</p>
<h2>Contacto</h2>
<p>Para consultas sobre privacidad escribe a <a href="mailto:%s">%s</a>.</p>""" % (fecha_larga(datetime.now()), EMAIL, EMAIL)


def sitemap(eds, resumenes=None):
    urls = [BASE_URL + "/", BASE_URL + "/nosotros.html",
            BASE_URL + "/apoyanos.html", BASE_URL + "/privacidad.html",
            BASE_URL + "/resumen-diario.html", BASE_URL + "/metodologia.html",
            BASE_URL + "/fuentes.html", BASE_URL + "/glosario.html",
            BASE_URL + "/categoria/index.html"]
    for slug, _n, _i in CATEGORIAS:
        urls.append("%s/categoria/%s.html" % (BASE_URL, slug))
    vistos = set(urls)
    for e in eds:
        u = "%s/edicion/%s.html" % (BASE_URL, e["slug"])
        if u not in vistos:
            vistos.add(u)
            urls.append(u)
        for s in e["stories"]:
            u = "%s/noticia/%s.html" % (BASE_URL, s["slug"])
            if u not in vistos:
                vistos.add(u)
                urls.append(u)
    body = "".join("<url><loc>%s</loc></url>" % esc(u) for u in urls)
    return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">%s</urlset>' % body


def rss(eds):
    items = ""
    for e in eds[:20]:
        link = "%s/edicion/%s.html" % (BASE_URL, e["slug"])
        desc = e["stories"][0]["contexto"] if e["stories"] else ""
        items += """<item><title>%s</title><link>%s</link><guid>%s</guid><pubDate>%s</pubDate><description>%s</description></item>""" % (
            esc(e["titulo_web"]), esc(link), esc(link),
            e["dt"].strftime("%a, %d %b %Y %H:%M:%S -0500"), esc(desc))
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>%s</title><link>%s/</link>
<description>Noticias del Perú y el mundo en ediciones cortas.</description><language>es-PE</language>
%s</channel></rss>""" % (SITE_NAME, BASE_URL, items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="")
    ap.add_argument("--dominio", default="", help="dominio propio, ej. olfatecho.com")
    args = ap.parse_args()
    global BASE_URL
    if args.base:
        BASE_URL = args.base.rstrip("/")
    elif args.dominio:
        dom = args.dominio.replace("https://", "").replace("http://", "").strip("/")
        open(DOMINIO_FILE, "w", encoding="utf-8").write(dom + "\n")
        BASE_URL = "https://" + dom
    else:
        dom = dominio_actual()
        if dom:
            BASE_URL = "https://" + dom

    eds = cargar_ediciones()
    resumenes = cargar_resumenes()
    # Blindaje: nunca se borra el sitio publicado si no hay ediciones fuente
    if not eds:
        print("No hay ediciones recientes en FUENTE; docs/ queda intacto.")
        return 0
    if os.path.isdir(SALIDA):
        shutil.rmtree(SALIDA)
    for sub in ("edicion", "noticia", "assets"):
        os.makedirs(os.path.join(SALIDA, sub), exist_ok=True)

    shutil.copyfile(os.path.join(AQUI, "assets", "style.css"),
                    os.path.join(SALIDA, "assets", "style.css"))
    shutil.copyfile(os.path.join(AQUI, "assets", "app.js"),
                    os.path.join(SALIDA, "assets", "app.js"))
    for extra in ("logo.png", "favicon.png", "logo-512.png", "og-default.jpg",
                  "yape.jpg", "bim.jpg"):
        src = os.path.join(AQUI, "assets", extra)
        if os.path.isfile(src):
            shutil.copyfile(src, os.path.join(SALIDA, "assets", extra))

    os.makedirs(os.path.join(SALIDA, "assets", "ediciones"), exist_ok=True)
    for ed in eds:
        if ed.get("img_src") and os.path.isfile(ed["img_src"]):
            dst = os.path.join(SALIDA, "assets", "ediciones", ed["slug"] + ".jpg")
            if preparar_imagen(ed["img_src"], dst):
                ed["img"] = "assets/ediciones/%s.jpg" % ed["slug"]

    # deduplicar: una noticia repetida = una sola pagina
    vistos = {}
    for ed in eds:
        for s in ed["stories"]:
            k = re.sub(r"\s+", " ", s["title"].lower()).strip()
            if k in vistos:
                s["slug"] = vistos[k]
            else:
                vistos[k] = s["slug"]

    open(os.path.join(SALIDA, "index.html"), "w", encoding="utf-8").write(generar_inicio(eds, resumenes))
    escritas = set()
    for ed in eds:
        open(os.path.join(SALIDA, "edicion", ed["slug"] + ".html"), "w",
             encoding="utf-8").write(generar_edicion(ed, eds))
        for s in ed["stories"]:
            if s["slug"] in escritas:
                continue
            escritas.add(s["slug"])
            open(os.path.join(SALIDA, "noticia", s["slug"] + ".html"), "w",
                 encoding="utf-8").write(generar_noticia(ed, s, eds))

    open(os.path.join(SALIDA, "nosotros.html"), "w", encoding="utf-8").write(
        generar_pagina("Nosotros", "Qué es Olfatecho y cómo trabaja.", "nosotros", nosotros()))
    open(os.path.join(SALIDA, "apoyanos.html"), "w", encoding="utf-8").write(
        generar_pagina("Apóyanos", "Apoya a Olfatecho con Yape o BIM. Eduardo Milla, editor.",
                       "apoyanos", apoyanos()))
    open(os.path.join(SALIDA, "privacidad.html"), "w", encoding="utf-8").write(
        generar_pagina("Privacidad", "Política de privacidad de Olfatecho Noticias.",
                       "privacidad", privacidad()))
    open(os.path.join(SALIDA, "resumen-diario.html"), "w",
         encoding="utf-8").write(generar_resumen_diario(resumenes))
    open(os.path.join(SALIDA, "metodologia.html"), "w", encoding="utf-8").write(
        generar_pagina("Cómo trabajamos",
                       "Cómo seleccionamos, verificamos y producimos las noticias de Olfatecho.",
                       "metodologia", metodologia()))
    open(os.path.join(SALIDA, "fuentes.html"), "w", encoding="utf-8").write(
        generar_pagina("Fuentes y verificación",
                       "Los medios y organismos oficiales que usamos y cómo verificamos la información.",
                       "fuentes", fuentes()))
    open(os.path.join(SALIDA, "glosario.html"), "w", encoding="utf-8").write(
        generar_pagina("Glosario",
                       "Significado de los términos que más se repiten en las noticias peruanas.",
                       "glosario", glosario()))
    por_cat = {}
    for ed in eds:
        for s in ed["stories"]:
            por_cat.setdefault(s["genero"], []).append((ed, s))
    os.makedirs(os.path.join(SALIDA, "categoria"), exist_ok=True)
    for slug, nombre, intro in CATEGORIAS:
        open(os.path.join(SALIDA, "categoria", slug + ".html"), "w",
             encoding="utf-8").write(generar_categoria(nombre, slug, intro,
                                                       por_cat.get(nombre, [])))
    open(os.path.join(SALIDA, "categoria", "index.html"), "w",
         encoding="utf-8").write(generar_categoria_index(por_cat))
    open(os.path.join(SALIDA, "sitemap.xml"), "w", encoding="utf-8").write(sitemap(eds, resumenes))
    open(os.path.join(SALIDA, "rss.xml"), "w", encoding="utf-8").write(rss(eds))
    open(os.path.join(SALIDA, "robots.txt"), "w", encoding="utf-8").write(
        "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % BASE_URL)
    open(os.path.join(SALIDA, "404.html"), "w", encoding="utf-8").write(
        generar_pagina("Página no encontrada", "La página que buscas no existe.", "404",
                       '<h1>Página no encontrada</h1>'
                       '<p>La página que buscas no existe o cambió de dirección.</p>'
                       '<p><a class="btn" href="index.html">Volver al inicio →</a></p>'))
    if ADSENSE_CLIENT:
        pub = ADSENSE_CLIENT.replace("ca-", "")
        open(os.path.join(SALIDA, "ads.txt"), "w", encoding="utf-8").write(
            "google.com, %s, DIRECT, f08c47fec0942fa0\n" % pub)
    else:
        open(os.path.join(SALIDA, "ads.txt"), "w", encoding="utf-8").write(
            "# ads.txt: agrega tu linea de AdSense (google.com, pub-XXXX, DIRECT, f08c47fec0942fa0)\n")
    dom = dominio_actual()
    if dom:
        open(os.path.join(SALIDA, "CNAME"), "w", encoding="utf-8").write(dom + "\n")

    print("OK: %d ediciones, %d noticias" % (len(eds), sum(len(e["stories"]) for e in eds)))
    print("Salida:", SALIDA)


if __name__ == "__main__":
    main()
