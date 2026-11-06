# Olfatecho Web

Web estática de **Olfatecho Noticias**. Cada edición de YouTube tiene su página
con el resumen de las noticias y el enlace al medio original.

## Estructura

- `generar.py` — lee las ediciones subidas desde
  `../noticiasdiarias/storage/noticias_diarias` y genera `docs/`.
- `docs/` — sitio publicado en GitHub Pages
  (`https://edumilla1994.github.io/olfatecho-web/`).
- `publicar_web.py` — regenera y hace `git commit` + `git push` si hay cambios.
- `publicar_web_oculto.vbs` — lanzador sin ventana (histórico).
- `adsense.txt` — aquí va tu ID de AdSense (`ca-pub-...`).
- `dominio.txt` — aquí va el dominio propio (`olfatecho.com`) cuando lo compres.

## Uso manual

```powershell
python generar.py
python generar.py --dominio olfatecho.com
python publicar_web.py
```

## Automatización

1. La tarea **Olfatecho WEB** ejecuta `publicar_web.py` cada 30 minutos.
2. Además, `subir_youtube.py` (noticiasdiarias) dispara `publicar_web.py`
   inmediatamente después de cada subida exitosa.
3. GitHub Actions despliega `docs/` en Pages.

## AdSense

1. Crea la cuenta en <https://adsense.google.com>.
2. Copia tu ID (`ca-pub-XXXXXXXXXXXXXXXX`) en la primera línea de `adsense.txt`.
3. Ejecuta `python generar.py`: agrega el meta de AdSense y genera `ads.txt`.
4. El script de AdSense **solo se carga si el visitante acepta** el aviso de
   cookies; si rechaza, no se carga publicidad.
5. En AdSense activa **Auto Ads** para que Google coloque los anuncios.

## Dominio propio

1. Compra el dominio y apunta el DNS a GitHub Pages (A/AAAA + CNAME `www`).
2. `python generar.py --dominio tudominio.com` (crea `dominio.txt` y `docs/CNAME`).
3. En GitHub → Settings → Pages → Custom domain, pon el dominio y activa HTTPS.

## Contenido

No se copian artículos completos: titular, resumen corto (contexto de la
noticia) y botón para leer la nota completa en el medio original.
