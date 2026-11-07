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
FUENTE = os.path.normpath(os.path.join(
    AQUI, "..", "noticiasdiarias", "storage", "noticias_diarias"))
SALIDA = os.path.join(AQUI, "docs")
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
                ln = ln.strip()
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
        fin = os.path.join(carpeta, "final-es.mp4")
        if not os.path.isfile(nj):
            continue
        # incluir tambien las ediciones con video listo aunque YouTube aun
        # no las haya subido: la web no debe quedarse atras
        if not os.path.isfile(yj) and not os.path.isfile(fin):
            continue
        try:
            j = json.load(open(nj, encoding="utf-8"))
            yt = json.load(open(yj, encoding="utf-8")) if os.path.isfile(yj) else {}
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
               '<script async id="adsbygoogle-js" crossorigin="anonymous" '
               'src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=%s">'
               '</script>\n'
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
  <a href="{root}nosotros.html">Nosotros</a>
  <a href="{root}apoyanos.html">Apóyanos</a>
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
    return """<a class="card reveal" href="{root}edicion/{slug}.html" style="--d:{d}s">
<div class="card-media"><img src="{img}" alt="{alt}" loading="lazy"></div>
<div class="card-body">
  <span class="card-genre">{edicion}</span>
  <h3>{titulo}</h3>
  <span class="meta">{fecha} · {n} noticias</span>
</div></a>""".format(
        root=root, slug=ed["slug"], img=esc(img_url(ed, root)),
        alt=esc(tit), edicion=esc(ed["edicion"].capitalize()),
        titulo=esc(tit), fecha=esc(fecha_corta(ed["dt"])),
        n=len(ed["stories"]), d=(i % 3) * 0.08)


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


def generar_inicio(eds):
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
        stories += """<article class="story-card reveal" style="--d:{d}s">
<div class="genre">{genero}</div>
<h2><a href="{root}noticia/{slug}.html">{titulo}</a></h2>
<p>{resumen}</p>
<div class="story-links">
  <a href="{root}noticia/{slug}.html">Leer el resumen →</a>
  {fuente_link}
</div></article>""".format(
            d=(i % 3) * 0.08, genero=esc(s["genero"]), root=root, slug=s["slug"],
            titulo=esc(s["title"]), resumen=esc(s["contexto"] or s["title"]),
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
        video = """<div class="video-frame"><iframe src="https://www.youtube-nocookie.com/embed/{vid}" title="{titulo}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>""".format(
            vid=ed["video"], titulo=esc(ed["titulo_web"]))

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
        video = """<p style="margin:22px 0"><a class="btn" href="{url}" target="_blank" rel="noopener">▶ Ver esta noticia en el video</a></p>""".format(url=esc(ed["url"]))

    texto = (s["contexto"] or "").strip()
    titulo_plano = re.sub(r"\s+", " ", s["title"]).strip()
    if texto and titulo_plano and texto.lower().startswith(titulo_plano.lower()[:60]):
        texto = texto[len(titulo_plano):].lstrip(" .:-–—")
    partes = re.split(r"(?<=[.!?])\s+", texto.strip()) if texto else []
    lede = partes[0] if partes else (s["contexto"] or s["title"])
    cuerpo = " ".join(partes[1:]).strip() if len(partes) > 1 else ""
    body_block = ('<div class="body"><p>%s</p></div>' % esc(cuerpo)) if cuerpo else ""

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
{fuente_box}
{video}
{ad_bottom}
<div class="more"><h3>Más de esta edición</h3>{mas}</div>
</article></main>""".format(
        root=root, eslug=ed["slug"], edicion=esc(ed["edicion"].capitalize()),
        genero=esc(s["genero"]), titulo=esc(s["title"]), fuente=esc(s["source"]),
        fecha=esc(fecha_larga(ed["dt"])), ambito=esc(s["ambito"]),
        resumen=esc(lede), share=share, body_block=body_block,
        fuente_box=fuente, video=video, mas=mas,
        ad_top=ad_slot("story_top"),
        ad_bottom=ad_slot("story_bottom"))
    doc += pie(root)
    return doc


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


def sitemap(eds):
    urls = [BASE_URL + "/", BASE_URL + "/nosotros.html",
            BASE_URL + "/apoyanos.html", BASE_URL + "/privacidad.html"]
    for e in eds:
        urls.append("%s/edicion/%s.html" % (BASE_URL, e["slug"]))
        for s in e["stories"]:
            urls.append("%s/noticia/%s.html" % (BASE_URL, s["slug"]))
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

    open(os.path.join(SALIDA, "index.html"), "w", encoding="utf-8").write(generar_inicio(eds))
    for ed in eds:
        open(os.path.join(SALIDA, "edicion", ed["slug"] + ".html"), "w",
             encoding="utf-8").write(generar_edicion(ed, eds))
        for s in ed["stories"]:
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
    open(os.path.join(SALIDA, "sitemap.xml"), "w", encoding="utf-8").write(sitemap(eds))
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
