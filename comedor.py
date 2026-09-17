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

from impresora_tickets import imprimir_ticket

# ── Configuración ────────────────────────────────────────────────────────
IP = "10.10.10.126"       # ⚠️ CONFIRMAR: verificar si es .124 o .126
PORT = 4370
PASSWORD = 0               # el K40 no pidió clave de comunicación
ARCHIVO_LOG = "registros_comedor.csv"
ARCHIVO_EMPRESAS = "empresas_empleados.csv"
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


def cargar_empresas():
    """Devuelve {user_id: empresa} a partir de empresas_empleados.csv.

    Ese CSV se genera cruzando los usuarios del checador con el listado de
    colaboradores (columna "Empresa"); las filas cuya coincidencia no fue
    confiable se dejan con la empresa en blanco para revisión manual, y
    aquí simplemente se ignoran (se usa el valor por defecto del ticket).
    """
    empresas = {}
    if not os.path.exists(ARCHIVO_EMPRESAS):
        print(f"⚠️  No se encontró {ARCHIVO_EMPRESAS}; los tickets usarán la empresa por defecto.")
        return empresas
    with open(ARCHIVO_EMPRESAS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            if fila.get("user_id") and fila.get("empresa"):
                empresas[fila["user_id"]] = fila["empresa"]
    return empresas


def asegurar_encabezado_csv():
    """Crea el CSV con encabezado si todavía no existe."""
    if not os.path.exists(ARCHIVO_LOG):
        with open(ARCHIVO_LOG, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["fecha_hora", "user_id", "nombre", "status", "punch"])


def ya_checo_hoy(user_id, fecha):
    """True si user_id ya tiene un registro guardado con esa fecha (YYYY-MM-DD).

    Se usa para no dar servicio de comedor dos veces el mismo día a la
    misma persona: se revisa el CSV ANTES de agregar la marcación actual.
    """
    if not os.path.exists(ARCHIVO_LOG):
        return False
    with open(ARCHIVO_LOG, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # saltar encabezado
        for fila in reader:
            if len(fila) < 2:
                continue
            fecha_hora_fila, user_id_fila = fila[0], fila[1]
            if user_id_fila == str(user_id) and fecha_hora_fila.startswith(fecha):
                return True
    return False


def escuchar_eventos():
    zk = ZK(IP, port=PORT, timeout=30, password=PASSWORD, force_udp=False)
    conn = None
    try:
        print(f"Conectando a {IP}:{PORT}...")
        conn = zk.connect()
        print("✅ Conexión establecida\n")

        usuarios = cargar_usuarios(conn)
        empresas = cargar_empresas()
        print(f"👥 Usuarios cargados: {len(usuarios)}")
        print(f"🏢 Empresas mapeadas: {len(empresas)}")
        print("🍽️  Esperando marcaciones del comedor (Ctrl+C para salir)...\n")

        for evento in conn.live_capture():
            if evento is None:
                # timeout interno sin eventos nuevos; seguimos esperando
                continue

            hora = evento.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            fecha = evento.timestamp.strftime("%Y-%m-%d")
            nombre = usuarios.get(evento.user_id, "Desconocido")

            duplicado = ya_checo_hoy(evento.user_id, fecha)
            empresa = empresas.get(str(evento.user_id))
            etiqueta = "⚠️  YA REGISTRADO HOY" if duplicado else "🍽️  SERVICIO DE COMEDOR"

            print(f"🟢 {hora}  |  {evento.user_id} - {nombre}  "
                  f"(status={evento.status}, punch={evento.punch})  {etiqueta}")

            with open(ARCHIVO_LOG, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([hora, evento.user_id, nombre, evento.status, evento.punch])

            try:
                imprimir_ticket(
                    nombre,
                    ya_registrado_hoy=duplicado,
                    fecha_hora=evento.timestamp,
                    empresa=empresa,
                )
            except Exception as e:
                print(f"❌ No se pudo imprimir el ticket: {e}")

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
