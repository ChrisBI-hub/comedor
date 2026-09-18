"""
Sube al checador ZKTeco los nombres que RRHH corrigió en
empresas_empleados.csv (columna "nombre_checador"), para que el equipo
deje de mostrar/reportar los nombres recortados o mal escritos.

⚠️ Este mismo equipo funciona como checador de asistencia. Cambiar el
nombre aquí lo cambia para TODO lo que use ese equipo (no solo para el
ticket de comedor). Además, el campo de nombre del equipo:
  - tiene un límite de 24 caracteres, y
  - normalmente no admite acentos/eñes (por eso ya se ven recortados/sin
    acentos hoy en día),
así que el nombre corregido se le quitan los acentos y se recorta a 24
caracteres antes de subirlo, para no arriesgarnos a guardar basura.

Por seguridad, este script por default solo SIMULA (dry-run): muestra
qué nombres cambiarían sin tocar el equipo. Para aplicar los cambios de
verdad hay que correrlo con --aplicar y confirmar escribiendo "SI".

Uso:
    python3 actualizar_nombres_checador.py            # solo muestra qué cambiaría
    python3 actualizar_nombres_checador.py --aplicar  # sube los cambios (pide confirmación)

Requiere: pyzk2  (pip install pyzk2)
"""

import csv
import sys
import unicodedata

from pyzk2 import ZK

IP = "10.10.10.126"       # ⚠️ CONFIRMAR: verificar si es .124 o .126
PORT = 4370
PASSWORD = 0
ARCHIVO_EMPRESAS = "empresas_empleados.csv"


def _preparar_nombre(nombre):
    """Quita acentos/ñ y recorta a 24 caracteres, como lo guarda el equipo."""
    normalizado = unicodedata.normalize("NFKD", nombre.strip())
    normalizado = normalizado.encode("ascii", "ignore").decode("ascii")
    return normalizado[:24].strip()


def cargar_correcciones():
    correcciones = {}
    with open(ARCHIVO_EMPRESAS, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            if fila.get("user_id") and fila.get("nombre_checador"):
                correcciones[fila["user_id"]] = fila["nombre_checador"]
    return correcciones


def main():
    aplicar = "--aplicar" in sys.argv
    correcciones = cargar_correcciones()

    zk = ZK(IP, port=PORT, timeout=15, password=PASSWORD, force_udp=False)
    conn = None
    try:
        print(f"Conectando a {IP}:{PORT}...")
        conn = zk.connect()
        print("✅ Conectado\n")

        usuarios = conn.get_users()
        cambios = []
        for u in usuarios:
            nombre_actual = (u.name or "").strip()
            nombre_nuevo = correcciones.get(u.user_id)
            if not nombre_nuevo:
                continue
            nombre_preparado = _preparar_nombre(nombre_nuevo)
            if nombre_preparado and nombre_preparado != nombre_actual:
                cambios.append((u, nombre_actual, nombre_preparado))

        if not cambios:
            print("No hay nombres por actualizar (todo coincide ya con el CSV).")
            return

        print(f"{'user_id':<8} {'ACTUAL EN EL EQUIPO':<25} -> {'NUEVO (24 car., sin acentos)':<25}")
        for u, actual, nuevo in cambios:
            print(f"{u.user_id:<8} {actual:<25} -> {nuevo:<25}")
        print(f"\nTotal a actualizar: {len(cambios)}")

        if not aplicar:
            print("\n(Simulación: no se cambió nada en el equipo. Corre con --aplicar para subir los cambios.)")
            return

        respuesta = input(f"\n¿Confirmas subir estos {len(cambios)} cambios al checador? (escribe SI): ")
        if respuesta.strip().upper() != "SI":
            print("Cancelado, no se hizo ningún cambio.")
            return

        conn.disable_device()  # evita marcaciones a medio proceso de escritura
        ok, con_error = 0, 0
        for u, actual, nuevo in cambios:
            try:
                conn.set_user(
                    uid=u.uid,
                    name=nuevo,
                    privilege=u.privilege,
                    password=u.password,
                    group_id=u.group_id,
                    user_id=u.user_id,
                    card=u.card,
                )
                print(f"✅ {u.user_id}: {actual!r} -> {nuevo!r}")
                ok += 1
            except Exception as e:
                print(f"❌ {u.user_id}: error al actualizar ({e})")
                con_error += 1
        conn.enable_device()

        print(f"\nListo. Actualizados: {ok}  Con error: {con_error}")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        if conn:
            conn.disconnect()
            print("\n🔌 Desconectado")


if __name__ == "__main__":
    main()
