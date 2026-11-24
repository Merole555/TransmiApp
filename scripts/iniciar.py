"""Comando único de arranque de TransmiApp (miembro 4).

    python scripts/iniciar.py            (macOS / Linux, con el .venv del proyecto)
    .\\.venv\\Scripts\\python.exe scripts/iniciar.py   (Windows PowerShell)

Comprueba los tres CSV, las dependencias y los puertos; arranca FastAPI
(Uvicorn, un worker, sin recarga) en 127.0.0.1:8000 y Vite en
127.0.0.1:5173, que reenvía /api al backend. Ctrl+C detiene ambos.
Solo usa la biblioteca estándar.
"""

import importlib.util
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FRONTEND = RAIZ / "frontend"
DATOS = RAIZ / "datos"
CSV_REQUERIDOS = ("estaciones.csv", "rutas.csv", "horarios.csv")
HOST = "127.0.0.1"
PUERTO_API = 8000
PUERTO_WEB = 5173


def fallar(mensaje):
    print(f"[iniciar] ERROR: {mensaje}", file=sys.stderr)
    return 1


def puerto_libre(puerto):
    """Libre si nadie acepta conexiones en él (tolera conexiones en TIME_WAIT)."""
    try:
        with socket.create_connection((HOST, puerto), timeout=0.5):
            return False
    except OSError:
        return True


def esperar_puerto(puerto, proceso, segundos=30):
    """Espera a que el proceso escuche en el puerto o termine."""
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if proceso.poll() is not None:
            return False
        try:
            with socket.create_connection((HOST, puerto), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.25)
    return False


def comprobar():
    faltan = [nombre for nombre in CSV_REQUERIDOS if not (DATOS / nombre).is_file()]
    if faltan:
        return f"faltan CSV en {DATOS}: {', '.join(faltan)}. Genera los datos con scripts/convertir_gtfs.py."
    for modulo in ("fastapi", "uvicorn"):
        if importlib.util.find_spec(modulo) is None:
            return (f"falta el paquete '{modulo}' en {sys.executable}. "
                    "Instala con: python -m pip install -r backend/requirements.txt")
    if shutil.which("node") is None:
        return "no se encontró Node.js en el PATH (se requiere Node 22)."
    vite = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite.is_file():
        return "faltan las dependencias del frontend. Ejecuta: npm --prefix frontend ci"
    for puerto in (PUERTO_API, PUERTO_WEB):
        if not puerto_libre(puerto):
            return f"el puerto {puerto} está ocupado. Cierra la otra instancia e inténtalo de nuevo."
    return None


def detener(procesos):
    for proceso in procesos:
        if proceso.poll() is None:
            try:
                if os.name == "nt":
                    proceso.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    proceso.terminate()
            except OSError:
                pass
    limite = time.monotonic() + 5
    for proceso in procesos:
        restante = max(0.1, limite - time.monotonic())
        try:
            proceso.wait(timeout=restante)
        except subprocess.TimeoutExpired:
            proceso.kill()
            proceso.wait()


def _interrumpir(_senal, _marco):
    raise KeyboardInterrupt


def main():
    # Trata la terminación como Ctrl+C para cerrar también a los hijos.
    signal.signal(signal.SIGTERM, _interrumpir)
    problema = comprobar()
    if problema:
        return fallar(problema)

    # En Windows cada hijo va en su propio grupo para poder enviarle Ctrl+Break.
    extra = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {}
    procesos = []
    codigo = 0
    try:
        print(f"[iniciar] Backend en http://{HOST}:{PUERTO_API} (documentación en /docs)")
        api = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app",
             "--host", HOST, "--port", str(PUERTO_API), "--workers", "1"],
            cwd=RAIZ, **extra,
        )
        procesos.append(api)
        if not esperar_puerto(PUERTO_API, api):
            return fallar("el backend no arrancó; revisa el registro de arriba (¿CSV válidos? ¿motor integrado?).")

        print(f"[iniciar] Frontend en http://{HOST}:{PUERTO_WEB}")
        web = subprocess.Popen(
            ["node", str(Path("node_modules") / "vite" / "bin" / "vite.js"),
             "--host", HOST, "--port", str(PUERTO_WEB), "--strictPort"],
            cwd=FRONTEND, **extra,
        )
        procesos.append(web)
        if not esperar_puerto(PUERTO_WEB, web):
            return fallar("Vite no arrancó; revisa el registro de arriba.")

        print(f"[iniciar] Listo. Abre http://{HOST}:{PUERTO_WEB} — Ctrl+C para detener.")
        while True:
            for proceso in procesos:
                if proceso.poll() is not None:
                    codigo = fallar(f"un proceso terminó inesperadamente (código {proceso.returncode}).")
                    return codigo
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[iniciar] Deteniendo…")
        return 0
    finally:
        detener(procesos)
        libres = puerto_libre(PUERTO_API) and puerto_libre(PUERTO_WEB)
        print("[iniciar] Procesos detenidos." + ("" if libres else " Aviso: algún puerto sigue ocupado."))


if __name__ == "__main__":
    sys.exit(main())
