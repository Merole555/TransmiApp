"""Arranca el backend (FastAPI) y el frontend (Vite) con un solo comando.

    python scripts/iniciar.py

Ctrl+C detiene los dos.
"""

import importlib.util
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
FRONTEND = RAIZ / "frontend"


def puerto_ocupado(puerto):
    try:
        with socket.create_connection(("127.0.0.1", puerto), timeout=0.5):
            return True
    except OSError:
        return False


def esperar(puerto, proceso):
    """Espera hasta 30 segundos a que el proceso abra el puerto."""
    for _ in range(120):
        if proceso.poll() is not None:
            return False
        if puerto_ocupado(puerto):
            return True
        time.sleep(0.25)
    return False


def revisar():
    """Devuelve un mensaje de error o None si todo está listo."""
    for archivo in ("estaciones.csv", "rutas.csv", "horarios.csv"):
        if not (RAIZ / "datos" / archivo).exists():
            return f"Falta datos/{archivo}"
    if importlib.util.find_spec("fastapi") is None or importlib.util.find_spec("uvicorn") is None:
        return "Faltan dependencias: python -m pip install -r backend/requirements.txt"
    if shutil.which("node") is None:
        return "No se encontró Node.js"
    if not (FRONTEND / "node_modules" / "vite").exists():
        return "Faltan dependencias del frontend: npm --prefix frontend ci"
    for puerto in (8000, 5173):
        if puerto_ocupado(puerto):
            return f"El puerto {puerto} ya está en uso"
    return None


def detener(procesos):
    for proceso in procesos:
        if proceso.poll() is None:
            proceso.terminate()
    for proceso in procesos:
        try:
            proceso.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proceso.kill()


def al_cerrar(senal, marco):
    # cerrar la terminal funciona igual que Ctrl+C
    raise KeyboardInterrupt


def main():
    error = revisar()
    if error:
        print("ERROR:", error)
        return 1

    signal.signal(signal.SIGTERM, al_cerrar)
    procesos = []
    try:
        backend = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "backend.main:app",
             "--host", "127.0.0.1", "--port", "8000", "--workers", "1"],
            cwd=RAIZ,
        )
        procesos.append(backend)
        if not esperar(8000, backend):
            print("ERROR: el backend no arrancó")
            return 1

        frontend = subprocess.Popen(
            ["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
            cwd=FRONTEND,
        )
        procesos.append(frontend)
        if not esperar(5173, frontend):
            print("ERROR: el frontend no arrancó")
            return 1

        print("Listo: abre http://127.0.0.1:5173 (Ctrl+C para salir)")
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(0.5)
        print("ERROR: uno de los procesos se cerró")
        return 1
    except KeyboardInterrupt:
        print("\nDeteniendo...")
        return 0
    finally:
        detener(procesos)


if __name__ == "__main__":
    sys.exit(main())
