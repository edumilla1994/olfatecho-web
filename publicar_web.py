# -*- coding: utf-8 -*-
"""Regenera la web de Olfatecho y la publica en GitHub.

Se ejecuta solo (tarea programada) después de cada edición. Si no hay
cambios, no hace commit. Log: web.log
"""
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(AQUI, "web.log")
MAIL = "246847380+edumilla1994@users.noreply.github.com"


def log(msg):
    try:
        with open(LOG, "a", encoding="utf-8") as fh:
            fh.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), msg))
    except OSError:
        pass


def run(args):
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    r = subprocess.run(args, cwd=AQUI, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    return r.returncode, ((r.stdout or "") + (r.stderr or "")).strip()


def main():
    # 1) notas largas y parafraseadas para las noticias nuevas
    base_noti = os.path.join(AQUI, "..", "noticiasdiarias")
    paraf = os.path.join(base_noti, "parafrasear_notas.py")
    if os.path.isfile(paraf):
        py = os.path.join(os.path.dirname(sys.executable), "python.exe")
        if not os.path.isfile(py):
            py = sys.executable
        rc, out = run([py, "-X", "utf8", paraf,
                       "--solo-subidos", "--limite", "8"])
        log("parafrasis: " + (out.splitlines()[-1] if out else "sin salida")[:300])

    rc, out = run([sys.executable, "-X", "utf8", "generar.py"])
    if rc != 0:
        log("ERROR generar: " + out[-900:])
        return 1
    log(out.splitlines()[0] if out else "generado")

    run(["git", "add", "-A"])
    rc, _ = run(["git", "diff", "--cached", "--quiet"])
    if rc == 0:
        log("sin cambios")
        return 0

    msg = "Web: nueva edicion " + time.strftime("%Y-%m-%d %H:%M")
    rc, out = run(["git", "-c", "user.name=edumilla1994",
                   "-c", "user.email=" + MAIL, "commit", "-m", msg])
    if rc != 0:
        log("ERROR commit: " + out[-900:])
        return 1

    rc, out = run(["git", "push"])
    if rc != 0:
        log("ERROR push: " + out[-900:])
        return 1
    log("OK publicado: " + msg)
    return 0


if __name__ == "__main__":
    sys.exit(main())
