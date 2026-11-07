# Olfatecho Web

Web estática de **Olfatecho Noticias**. Cada edición de YouTube tiene su página
con el resumen de las noticias y el enlace al medio original.

## Estructura

- `generar.py` — lee las ediciones desde
  `../noticiasdiarias/storage/noticias_diarias` y genera `docs/`.
- `docs/` — sitio publicado en GitHub Pages.
- `publicar_web.py` — regenera y hace `git commit` + `git push` si hay cambios.
- `dominio.txt` — dominio propio (`olfatecho.com`).
- `adsense.txt` — ID de AdSense (`ca-pub-...`).
- `adsense_slots.txt` — IDs de las unidades manuales (opcional).
- `ga4.txt` — ID de Google Analytics 4 (`G-...`).
- `google_site_verification.txt` — token de Search Console.

## Uso

```powershell
python generar.py
python generar.py --dominio olfatecho.com
python publicar_web.py
```

## Automatización

1. Tarea **Olfatecho WEB** cada 30 minutos.
2. `subir_youtube.py` dispara `publicar_web.py` al subir una edición.
3. GitHub Actions despliega `docs/` en Pages.

## Dominio (GoDaddy → GitHub Pages)

En GoDaddy: **Mis productos → olfatecho.com → DNS**. Borra el aparcamiento por
defecto y crea:

| Tipo | Nombre | Valor |
|---|---|---|
| A | @ | 185.199.108.153 |
| A | @ | 185.199.109.153 |
| A | @ | 185.199.110.153 |
| A | @ | 185.199.111.153 |
| AAAA | @ | 2606:50c0:8000::153 |
| AAAA | @ | 2606:50c0:8001::153 |
| AAAA | @ | 2606:50c0:8002::153 |
| AAAA | @ | 2606:50c0:8003::153 |
| CNAME | www | edumilla1994.github.io |

Luego en GitHub → Settings → Pages → Custom domain: `olfatecho.com` → Save →
**Enforce HTTPS**. Después: `python generar.py --dominio olfatecho.com`.

## AdSense

1. Crea la cuenta en <https://adsense.google.com> y añade `olfatecho.com`.
2. Pega tu ID en `adsense.txt` (`ca-pub-...`).
3. Ejecuta `python generar.py`: añade el meta, el script (solo tras aceptar
   cookies), `ads.txt` y los huecos de anuncios.
4. Activa **Auto Ads** en AdSense.
5. Para banners manuales, crea unidades en AdSense y pega sus IDs en
   `adsense_slots.txt` (`home_top`, `home_mid`, `edition_top`,
   `edition_bottom`, `story_top`, `story_bottom`).

## Google

- **Search Console**: verifica `olfatecho.com` (DNS TXT o el token en
  `google_site_verification.txt`) y envía `https://olfatecho.com/sitemap.xml`.
- **Analytics 4**: crea la propiedad y pega `G-...` en `ga4.txt`.

## Contenido

No se copian artículos completos: titular, resumen corto (contexto de la
noticia) y botón para leer la nota completa en el medio original.
