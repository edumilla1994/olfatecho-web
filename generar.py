# -*- coding: utf-8 -*-
"""Generador estático de la web de Olfatecho.

Lee las ediciones ya subidas a YouTube desde
../noticiasdiarias/storage/noticias_diarias y genera:

  site/index.html
  site/edicion/<fecha>-<edicion>.html
  site/noticia/<fecha>-<edicion>-<n>-<titulo>.html
  site/nosotros.html
  site/privacidad.html
  site/sitemap.xml
  site/rss.xml
  site/robots.txt

No copia los artículos: muestra titular + resumen corto + enlace al medio.
Uso:  python generar.py [--base https://...]
"""
import argparse
import html
import json
import os
import re
import shutil
import unicodedata
from datetime import datetime

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE = os.path.normpath(os.path.join(
    AQUI, "..", "noticiasdiarias", "storage", "noticias_diarias"))
SALIDA = os.path.join(AQUI, "site")
BASE_URL = os.getenv("OLFATECHO_BASE",
                     "https://edumilla1994.github.io/olfatecho-web").rstrip("/")
EMAIL = "edumilla1994@gmail.com"

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


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


def cargar_ediciones():
    eds = []
    if not os.path.isdir(FUENTE):
        return eds
    for d in sorted(os.listdir(FUENTE)):
        carpeta = os.path.join(FUENTE, d)
        nj = os.path.join(carpeta, "noticias.json")
        yj = os.path.join(carpeta, "subir_youtube.json")
        if not (os.path.isfile(nj) and os.path.isfile(yj)):
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
        eds.append({
            "folder": d, "dt": dt, "edicion": ed_txt,
            "num": int(j.get("edicion_num") or 0),
            "slug": slug, "video": vid,
            "url": (yt.get("url") or "").strip(),
            "titulo": (yt.get("titulo") or "").strip(),
            "stories": stories,
        })
    eds.sort(key=lambda e: e["dt"], reverse=True)
    return eds


def head(titulo, desc, canonical, root, og_image="", jsonld=""):
    img = og_image or (BASE_URL + "/assets/og-default.jpg")
    return """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{titulo}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{canonical}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Olfatecho Noticias">
<meta property="og:title" content="{titulo}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{img}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="{root}assets/style.css">
{jsonld}
</head>
<body>
""".format(titulo=esc(titulo), desc=esc(desc), canonical=esc(canonical),
           root=root, img=esc(img), jsonld=jsonld)


def cabecera(root):
    return """<div class="topbar"><div class="wrap">
<span>Perú y el mundo, contado rápido y claro</span>
<span>{fecha}</span>
</div></div>
<header class="site-header"><div class="wrap">
<a class="logo" href="{root}index.html">
  <span class="logo-mark">🐾</span>
  <span class="logo-text">OLFATECHO<small>NOTICIAS DEL PERÚ</small></span>
</a>
<nav class="nav">
  <a href="{root}index.html">Inicio</a>
  <a href="{root}index.html#ediciones">Ediciones</a>
  <a href="{root}nosotros.html">Nosotros</a>
  <a href="{root}privacidad.html">Privacidad</a>
</nav>
</div></header>
""".format(root=root, fecha=esc(fecha_larga(datetime.now())))


def pie(root):
    return """<footer class="site-footer"><div class="wrap">
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
    <p><a href="{root}privacidad.html">Privacidad</a></p>
  </div>
  <div>
    <h4>Contacto</h4>
    <p><a href="mailto:{email}">{email}</a></p>
    <p>YouTube: <a href="https://youtube.com/@Olfatecho" rel="noopener">@Olfatecho</a></p>
  </div>
</div>
<div class="copy"><span>© {anio} Olfatecho. Todos los derechos reservados.</span>
<span>Hecho en Perú 🇵🇪</span></div>
</div></footer>
</body></html>
""".format(root=root, email=EMAIL, anio=datetime.now().year)


def thumb(ed):
    return "https://i.ytimg.com/vi/%s/hqdefault.jpg" % ed["video"] if ed["video"] else ""


def tarjeta_edicion(ed, root):
    return """<a class="card" href="{root}edicion/{slug}.html">
<img src="{img}" alt="{alt}" loading="lazy">
<div class="card-body">
  <span class="tag">{tag}</span>
  <h3>{titulo}</h3>
  <span class="meta">{fecha} · {n} noticias</span>
</div></a>""".format(
        root=root, slug=ed["slug"], img=esc(thumb(ed)),
        alt=esc(ed["titulo"] or ed["edicion"]),
        tag=esc(ed["edicion"].capitalize()), titulo=esc(ed["titulo"] or "Olfatecho Noticias"),
        fecha=esc(fecha_corta(ed["dt"])), n=len(ed["stories"]))


def item_noticia(ed, s, root, mostrar_num=True):
    num = '<div class="num">%02d</div>' % s["n"] if mostrar_num else ""
    return """<div class="news-item">
{num}
<div>
  <h3><a href="{root}noticia/{slug}.html">{titulo}</a></h3>
  <p>{resumen}</p>
  <p class="meta" style="margin-top:6px">{fuente} · {edicion}</p>
</div></div>""".format(
        num=num, root=root, slug=s["slug"], titulo=esc(s["title"]),
        resumen=esc(s["contexto"] or s["title"]),
        fuente=esc(s["source"]), edicion=esc(ed["edicion"].capitalize()))


def generar_inicio(eds):
    root = ""
    portada = eds[0] if eds else None
    if not portada:
        cuerpo = '<div class="empty">Todavía no hay ediciones publicadas.</div>'
        html_doc = head("Olfatecho Noticias", "Noticias del Perú y el mundo.",
                        BASE_URL + "/", root) + cabecera(root) + \
            '<main class="wrap">' + cuerpo + "</main>" + pie(root)
        return html_doc
    hero = """<section class="hero"><div class="wrap"><div class="hero-grid">
<div class="hero-media">
  <a href="{root}edicion/{slug}.html"><img src="{img}" alt="{alt}">
  <span class="play"><span>▶</span></span></a>
</div>
<div>
  <span class="kicker">Última edición · {fecha}</span>
  <h1>{titulo}</h1>
  <p>{resumen}</p>
  <a class="btn" href="{root}edicion/{slug}.html">Ver la edición completa →</a>
</div>
</div></div></section>""".format(
        root=root, slug=portada["slug"], img=esc(thumb(portada)),
        alt=esc(portada["titulo"]), fecha=esc(fecha_corta(portada["dt"])),
        titulo=esc(portada["titulo"] or "Olfatecho Noticias"),
        resumen=esc(portada["stories"][0]["contexto"] if portada["stories"] else ""))

    grid = "".join(tarjeta_edicion(e, root) for e in eds[1:13])
    ultimas = ""
    for e in eds[:3]:
        for s in e["stories"][:3]:
            ultimas += item_noticia(e, s, root)
    side = """<div class="side-box">
<h3>La noticia, completa</h3>
<p>Cada edición dura menos de dos minutos. En la web tienes el resumen de cada historia y el enlace directo al medio original para leerla completa.</p>
<a class="btn" href="{root}nosotros.html">Conoce Olfatecho →</a>
</div>""".format(root=root)

    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "WebSite",
        "name": "Olfatecho Noticias", "url": BASE_URL + "/",
        "potentialAction": {"@type": "SearchAction",
                            "target": BASE_URL + "/?q={search_term_string}",
                            "query-input": "required name=search_term_string"},
    }, ensure_ascii=False)

    doc = head("Olfatecho Noticias — Perú y el mundo, en 2 minutos",
               "Ediciones cortas de noticias del Perú y el mundo, con enlaces a las fuentes originales.",
               BASE_URL + "/", root, og_image=thumb(portada),
               jsonld='<script type="application/ld+json">%s</script>' % jsonld)
    doc += cabecera(root)
    doc += hero
    doc += """<section class="section" id="ediciones"><div class="wrap">
<div class="section-head"><h2>Ediciones recientes</h2><span>Una mirada rápida, todos los días</span></div>
<div class="grid-3">%s</div></div></section>""" % grid
    doc += """<section class="section"><div class="wrap"><div class="news-list">
<div><div class="section-head"><h2>Últimas noticias</h2><span>Lo que está pasando</span></div>%s</div>
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
    for s in ed["stories"]:
        stories += """<article class="story-card">
<div class="story-index">{n:02d}</div>
<div>
  <span class="tag" style="color:var(--terra);font-size:10.5px;font-weight:800;letter-spacing:.14em;text-transform:uppercase">{genero}</span>
  <h2><a href="{root}noticia/{slug}.html">{titulo}</a></h2>
  <p>{resumen}</p>
  <div class="story-links">
    <a href="{root}noticia/{slug}.html">Leer el resumen →</a>
    {fuente_link}
  </div>
</div></article>""".format(
            n=s["n"], genero=esc(s["genero"]), root=root, slug=s["slug"],
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
            vid=ed["video"], titulo=esc(ed["titulo"]))

    doc = head("%s — Olfatecho Noticias" % (ed["titulo"] or ed["edicion"]),
               "Edición del %s con %d noticias del Perú y el mundo." % (fecha_larga(ed["dt"]), len(ed["stories"])),
               "%s/edicion/%s.html" % (BASE_URL, ed["slug"]), root,
               og_image=thumb(ed))
    doc += cabecera(root)
    doc += """<main class="wrap"><div class="edition-head">
<div class="breadcrumb"><a href="{root}index.html">Inicio</a> / Ediciones</div>
<span class="kicker">{edicion}</span>
<h1>{titulo}</h1>
<div class="edition-meta"><span>{fecha}</span><span>·</span><span>{n} noticias</span><span>·</span><span>Video: 2 minutos</span></div>
</div>
{video}
<section class="section" style="padding-top:18px">{stories}</section>
<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:10px 0 30px">{nav}</div>
</main>""".format(root=root, edicion=esc(ed["edicion"].capitalize()),
                 titulo=esc(ed["titulo"] or "Olfatecho Noticias"),
                 fecha=esc(fecha_larga(ed["dt"])), n=len(ed["stories"]),
                 video=video, stories=stories, nav=nav)
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
        video = """<p style="margin:18px 0"><a class="btn" href="{url}" target="_blank" rel="noopener">▶ Ver esta noticia en el video</a></p>""".format(url=esc(ed["url"]))

    jsonld = json.dumps({
        "@context": "https://schema.org",
        "@type": "NewsArticle",
        "headline": s["title"],
        "description": s["contexto"],
        "datePublished": ed["dt"].isoformat(),
        "author": {"@type": "Organization", "name": "Olfatecho Noticias"},
        "publisher": {"@type": "Organization", "name": "Olfatecho Noticias"},
        "mainEntityOfPage": "%s/noticia/%s.html" % (BASE_URL, s["slug"]),
        "isBasedOn": s["link"] or "",
    }, ensure_ascii=False)

    doc = head("%s — Olfatecho" % s["title"],
               s["contexto"] or s["title"],
               "%s/noticia/%s.html" % (BASE_URL, s["slug"]), root,
               og_image=thumb(ed),
               jsonld='<script type="application/ld+json">%s</script>' % jsonld)
    doc += cabecera(root)
    doc += """<main class="wrap"><article class="article" style="padding:36px 0 10px">
<div class="breadcrumb"><a href="{root}index.html">Inicio</a> / <a href="{root}edicion/{eslug}.html">{edicion}</a></div>
<span class="tag" style="color:var(--terra);font-size:11px;font-weight:800;letter-spacing:.14em;text-transform:uppercase">{genero}</span>
<h1>{titulo}</h1>
<div class="meta"><span>{fuente}</span><span>·</span><span>{fecha}</span><span>·</span><span>{ambito}</span></div>
<p class="lede">{resumen}</p>
<div class="body">
<p>{cuerpo}</p>
</div>
{fuente_box}
{video}
<div class="more"><h3>Más de esta edición</h3>{mas}</div>
</article></main>""".format(
        root=root, eslug=ed["slug"], edicion=esc(ed["edicion"].capitalize()),
        genero=esc(s["genero"]), titulo=esc(s["title"]), fuente=esc(s["source"]),
        fecha=esc(fecha_larga(ed["dt"])), ambito=esc(s["ambito"]),
        resumen=esc(s["contexto"] or s["title"]),
        cuerpo=esc(s["contexto"] or "Lee la nota completa en el medio original."),
        fuente_box=fuente, video=video, mas=mas)
    doc += pie(root)
    return doc


def generar_pagina(titulo, desc, slug, contenido):
    root = ""
    doc = head("%s — Olfatecho" % titulo, desc, "%s/%s.html" % (BASE_URL, slug), root)
    doc += cabecera(root)
    doc += '<main class="wrap"><div class="page">%s</div></main>' % contenido
    doc += pie(root)
    return doc


def nosotros():
    return """<h1>¿Qué es Olfatecho?</h1>
<p>Olfatecho es un noticiero peruano que resume las noticias más importantes del día en ediciones de menos de dos minutos. Cada historia tiene su espacio en esta web con un resumen claro y el enlace directo al medio que la publicó.</p>
<h2>Nuestro compromiso</h2>
<p>No inventamos ni copiamos artículos: contamos lo esencial y te llevamos a la fuente original para que puedas leer la nota completa y sacar tus conclusiones.</p>
<h2>¿Cómo funciona?</h2>
<ul>
<li>Revisamos medios peruanos e internacionales durante el día.</li>
<li>Elegimos las historias más relevantes y las narramos en video.</li>
<li>Publicamos la edición en YouTube y aquí encuentras el resumen y las fuentes.</li>
</ul>
<p>¿Tienes un dato, una corrección o una sugerencia? Escríbenos a <a href="mailto:%s">%s</a>.</p>""" % (EMAIL, EMAIL)


def privacidad():
    return """<h1>Política de privacidad</h1>
<p>Última actualización: %s.</p>
<p>Olfatecho Noticias es un sitio informativo. Esta política explica qué datos se usan cuando visitas la web o ves nuestros videos.</p>
<h2>Datos que recopilamos</h2>
<p>No pedimos registro ni datos personales para leer las noticias. El sitio es estático y no tiene formularios de usuario.</p>
<h2>Cookies y terceros</h2>
<p>Los videos se muestran con el reproductor de YouTube (modo privacidad mejorada). YouTube y Google pueden usar cookies propias según sus políticas. No controlamos esas cookies.</p>
<h2>Enlaces a otros medios</h2>
<p>Cada noticia enlaza al artículo original de su medio. Al hacer clic saldrás de Olfatecho y se aplicarán las políticas del sitio de destino.</p>
<h2>Contacto</h2>
<p>Para consultas sobre privacidad escribe a <a href="mailto:%s">%s</a>.</p>""" % (fecha_larga(datetime.now()), EMAIL, EMAIL)


def sitemap(eds):
    urls = [BASE_URL + "/", BASE_URL + "/nosotros.html", BASE_URL + "/privacidad.html"]
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
            esc(e["titulo"]), esc(link), esc(link),
            e["dt"].strftime("%a, %d %b %Y %H:%M:%S -0500"),
            esc(desc))
    return """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Olfatecho Noticias</title><link>%s/</link>
<description>Noticias del Perú y el mundo en ediciones cortas.</description><language>es-PE</language>
%s</channel></rss>""" % (BASE_URL, items)


def favicon():
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
<circle cx="32" cy="32" r="32" fill="#b8431f"/>
<text x="32" y="42" font-size="30" text-anchor="middle" fill="#fff" font-family="Georgia,serif">O</text>
</svg>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="")
    args = ap.parse_args()
    global BASE_URL
    if args.base:
        BASE_URL = args.base.rstrip("/")

    eds = cargar_ediciones()
    if os.path.isdir(SALIDA):
        shutil.rmtree(SALIDA)
    os.makedirs(os.path.join(SALIDA, "edicion"), exist_ok=True)
    os.makedirs(os.path.join(SALIDA, "noticia"), exist_ok=True)
    os.makedirs(os.path.join(SALIDA, "assets"), exist_ok=True)

    shutil.copyfile(os.path.join(AQUI, "assets", "style.css"),
                    os.path.join(SALIDA, "assets", "style.css"))
    open(os.path.join(SALIDA, "assets", "favicon.svg"), "w", encoding="utf-8").write(favicon())

    open(os.path.join(SALIDA, "index.html"), "w", encoding="utf-8").write(generar_inicio(eds))
    for ed in eds:
        open(os.path.join(SALIDA, "edicion", ed["slug"] + ".html"), "w",
             encoding="utf-8").write(generar_edicion(ed, eds))
        for s in ed["stories"]:
            open(os.path.join(SALIDA, "noticia", s["slug"] + ".html"), "w",
                 encoding="utf-8").write(generar_noticia(ed, s, eds))

    open(os.path.join(SALIDA, "nosotros.html"), "w", encoding="utf-8").write(
        generar_pagina("Nosotros", "Qué es Olfatecho y cómo trabaja.", "nosotros", nosotros()))
    open(os.path.join(SALIDA, "privacidad.html"), "w", encoding="utf-8").write(
        generar_pagina("Privacidad", "Política de privacidad de Olfatecho Noticias.",
                       "privacidad", privacidad()))
    open(os.path.join(SALIDA, "sitemap.xml"), "w", encoding="utf-8").write(sitemap(eds))
    open(os.path.join(SALIDA, "rss.xml"), "w", encoding="utf-8").write(rss(eds))
    open(os.path.join(SALIDA, "robots.txt"), "w", encoding="utf-8").write(
        "User-agent: *\nAllow: /\nSitemap: %s/sitemap.xml\n" % BASE_URL)

    print("OK: %d ediciones, %d noticias" % (len(eds), sum(len(e["stories"]) for e in eds)))
    print("Salida:", SALIDA)


if __name__ == "__main__":
    main()
