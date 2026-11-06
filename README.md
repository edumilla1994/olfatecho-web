# Olfatecho Web

Web estática de **Olfatecho Noticias**: cada edición de YouTube tiene su
página con el resumen de las noticias y el enlace al medio original.

## Estructura

- `generar.py` — lee las ediciones ya subidas desde
  `../noticiasdiarias/storage/noticias_diarias` y genera `docs/`.
- `docs/` — sitio publicado en GitHub Pages
  (`https://edumilla1994.github.io/olfatecho-web/`).
- `publicar_web.py` — regenera y hace `git commit` + `git push` si hay cambios.
- `publicar_web_oculto.vbs` — lanza `publicar_web.py` sin ventana (tarea programada).

## Uso manual

```powershell
python generar.py
# o:
python publicar_web.py
```

## Automatización

La tarea programada **Olfatecho WEB** ejecuta el `.vbs` cada 30 minutos:
regenera el sitio, y si hay una edición nueva la publica en GitHub. GitHub
Actions despliega `docs/` en Pages.

## Contenido

No se copian artículos completos: se muestra el titular, un resumen corto
(extraído del contexto de la noticia) y un botón para leer la nota completa
en el medio original.
