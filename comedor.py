"""
Captura en tiempo real del checador ZKTeco (K40) para registro de comedor.

Cada vez que alguien marca (huella/tarjeta), el equipo emite un evento que
este script captura al vuelo y guarda en un CSV. Pensado para dejarse
corriendo de forma continua (ej. como tarea programada / servicio).

Requiere: pyzk2  (pip install pyzk2)
"""

import csv
import os
import time
from datetime import datetime

from pyzk2 import ZK

# ── Configuración ────────────────────────────────────────────────────────
IP = "10.10.10.126"       # ⚠️ CONFIRMAR: verificar si es .124 o .126
PORT = 4370
PASSWORD = 0               # el K40 no pidió clave de comunicación
ARCHIVO_LOG = "registros_comedor.csv"
REINTENTO_SEGUNDOS = 10     # espera antes de reintentar si se pierde la conexión


def cargar_usuarios(conn):
    """Devuelve {user_id: nombre} para mostrar nombres en vez de solo IDs."""
    usuarios = {}
    try:
        for u in conn.get_users():
            usuarios[u.user_id] = u.name.strip() if u.name else f"ID {u.user_id}"
    except Exception as e:
        print(f"⚠️  No se pudo cargar la lista de usuarios: {e}")
    return usuarios


def asegurar_encabezado_csv():
    """Crea el CSV con encabezado si todavía no existe."""
    if not os.path.exists(ARCHIVO_LOG):
        with open(ARCHIVO_LOG, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["fecha_hora", "user_id", "nombre", "status", "punch"])


def escuchar_eventos():
    zk = ZK(IP, port=PORT, timeout=30, password=PASSWORD, force_udp=False)
    conn = None
    try:
        print(f"Conectando a {IP}:{PORT}...")
        conn = zk.connect()
        print("✅ Conexión establecida\n")

        usuarios = cargar_usuarios(conn)
        print(f"👥 Usuarios cargados: {len(usuarios)}")
        print("🍽️  Esperando marcaciones del comedor (Ctrl+C para salir)...\n")

        for evento in conn.live_capture():
            if evento is None:
                # timeout interno sin eventos nuevos; seguimos esperando
                continue

            hora = evento.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            nombre = usuarios.get(evento.user_id, "Desconocido")

            print(f"🟢 {hora}  |  {evento.user_id} - {nombre}  "
                  f"(status={evento.status}, punch={evento.punch})")

            with open(ARCHIVO_LOG, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([hora, evento.user_id, nombre, evento.status, evento.punch])

    except KeyboardInterrupt:
        print("\n⏹️  Captura detenida manualmente.")
        raise
    except Exception as e:
        print(f"❌ Error de conexión/captura: {e}")
    finally:
        if conn:
            try:
                conn.disconnect()
                print("🔌 Desconectado del equipo.")
            except Exception:
                pass


if __name__ == "__main__":
    asegurar_encabezado_csv()
    while True:
        try:
            escuchar_eventos()
        except KeyboardInterrupt:
            break
        print(f"↻ Reintentando conexión en {REINTENTO_SEGUNDOS}s...\n")
        time.sleep(REINTENTO_SEGUNDOS)
