"""
Diagnóstico de memoria del checador ZKTeco y limpieza de usuarios
inactivos, para el equipo que estuvo mucho tiempo sin usarse.

Hace dos cosas:
  1. Reporte de uso de memoria: usuarios, huellas, registros de
     asistencia y tarjetas usados vs. la capacidad máxima del equipo.
  2. Detecta usuarios sin ninguna marcación en los últimos N años
     (por default 2) y, si se confirma, los borra del equipo.

La "última marcación" se calcula cruzando TRES fuentes, por si el
equipo ya rotó/perdió registros viejos de su propia memoria interna:
  - los registros de asistencia que el equipo todavía tiene en memoria,
  - registros_comedor.csv (lo que ha capturado este proyecto),
  - historial_checador_respaldo.csv (respaldo hecho con historial_checador.py).
Un usuario solo se marca como candidato a borrar si NINGUNA de esas tres
fuentes tiene una marcación suya dentro de los últimos N años.

⚠️ Borrar un usuario del checador borra también su huella/plantilla
enrolada — si esa persona sigue trabajando ahí, tendría que volver a
registrar su huella desde cero. Por eso, por default este script SOLO
hace un reporte (dry-run) y guarda los candidatos en un CSV para que los
revises; para borrar de verdad hay que correrlo con --aplicar y
confirmar escribiendo "SI".

Uso:
    python3 limpieza_checador.py                # solo diagnóstico + candidatos
    python3 limpieza_checador.py --anios 3      # cambiar el umbral de inactividad
    python3 limpieza_checador.py --aplicar      # borra los candidatos (pide confirmar)

Requiere: pyzk2  (pip install pyzk2)
"""

import argparse
import csv
import os
from datetime import datetime, timedelta

from pyzk2 import ZK

IP = "10.10.10.126"       # ⚠️ CONFIRMAR: verificar si es .124 o .126
PORT = 4370
PASSWORD = 0
ARCHIVO_CANDIDATOS = "usuarios_inactivos_candidatos.csv"
ARCHIVOS_HISTORIAL_LOCAL = ["registros_comedor.csv", "historial_checador_respaldo.csv"]


def imprimir_uso_memoria(conn):
    conn.read_sizes()

    def linea(nombre, usados, capacidad):
        if capacidad:
            libres = capacidad - usados
            pct = f"{usados / capacidad * 100:.1f}%"
        else:
            libres, pct = "?", "?"
        print(f"  {nombre:<12} usados: {usados:<6} capacidad: {capacidad:<6} libres: {libres!s:<6} ({pct} usado)")

    print("📊 Uso de memoria del checador:")
    linea("Usuarios", conn.users, conn.users_cap)
    linea("Huellas", conn.fingers, conn.fingers_cap)
    linea("Registros", conn.records, conn.rec_cap)
    print(f"  Tarjetas registradas: {conn.cards}")
    if getattr(conn, "faces_cap", 0):
        linea("Rostros", conn.faces, conn.faces_cap)
    print()


def ultima_marca_en_csvs_locales():
    """Devuelve {user_id: datetime} con la marcación más reciente que
    tengamos en los CSV locales del proyecto (además de la memoria del
    equipo), por si el equipo ya no tiene todo su historial."""
    ultima = {}
    for archivo in ARCHIVOS_HISTORIAL_LOCAL:
        if not os.path.exists(archivo):
            continue
        with open(archivo, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for fila in reader:
                user_id = fila.get("user_id")
                fecha_hora = fila.get("fecha_hora")
                if not user_id or not fecha_hora:
                    continue
                try:
                    ts = datetime.strptime(fecha_hora, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    continue
                if user_id not in ultima or ts > ultima[user_id]:
                    ultima[user_id] = ts
    return ultima


def encontrar_inactivos(usuarios, asistencias_equipo, anios):
    limite = datetime.now() - timedelta(days=365 * anios)

    ultima_marca = ultima_marca_en_csvs_locales()
    for r in asistencias_equipo:
        actual = ultima_marca.get(r.user_id)
        if actual is None or r.timestamp > actual:
            ultima_marca[r.user_id] = r.timestamp

    candidatos = []
    for u in usuarios:
        ultima = ultima_marca.get(u.user_id)
        if ultima is None or ultima < limite:
            candidatos.append((u, ultima))
    return candidatos


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--anios", type=float, default=2, help="umbral de inactividad en años (default 2)")
    parser.add_argument("--aplicar", action="store_true", help="borra de verdad los candidatos del equipo")
    args = parser.parse_args()

    zk = ZK(IP, port=PORT, timeout=30, password=PASSWORD, force_udp=False)
    conn = None
    try:
        print(f"Conectando a {IP}:{PORT}...")
        conn = zk.connect()
        print("✅ Conectado\n")

        imprimir_uso_memoria(conn)

        print("Consultando usuarios y registros de asistencia (puede tardar unos minutos)...")
        usuarios = conn.get_users()
        asistencias = conn.get_attendance()
        print(f"Usuarios: {len(usuarios)}  |  Registros en el equipo: {len(asistencias)}\n")

        candidatos = encontrar_inactivos(usuarios, asistencias, args.anios)
        candidatos.sort(key=lambda c: c[1] or datetime.min)

        with open(ARCHIVO_CANDIDATOS, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "nombre", "ultima_marcacion"])
            for u, ultima in candidatos:
                writer.writerow([
                    u.user_id,
                    u.name.strip() if u.name else "",
                    ultima.strftime("%Y-%m-%d") if ultima else "NUNCA",
                ])

        print(f"🕵️  Usuarios sin marcaciones en los últimos {args.anios} años: {len(candidatos)}")
        print(f"    (lista completa guardada en {ARCHIVO_CANDIDATOS} para revisar antes de borrar)\n")
        for u, ultima in candidatos[:20]:
            f_ult = ultima.strftime("%Y-%m-%d") if ultima else "NUNCA"
            nombre = u.name.strip() if u.name else ""
            print(f"  user_id={u.user_id:<6} {nombre:<26} última marcación: {f_ult}")
        if len(candidatos) > 20:
            print(f"  ... y {len(candidatos) - 20} más (ver {ARCHIVO_CANDIDATOS})")

        if not args.aplicar:
            print(f"\n(Simulación: no se borró nada. Revisa {ARCHIVO_CANDIDATOS} y corre con --aplicar para borrarlos del equipo.)")
            return

        if not candidatos:
            print("\nNo hay candidatos que borrar.")
            return

        respuesta = input(
            f"\n⚠️  Vas a BORRAR {len(candidatos)} usuarios del checador (se pierde su huella también). "
            f"Revisa antes {ARCHIVO_CANDIDATOS}. ¿Confirmas? (escribe SI): "
        )
        if respuesta.strip().upper() != "SI":
            print("Cancelado, no se borró nada.")
            return

        ok, con_error = 0, 0
        for u, _ in candidatos:
            try:
                conn.delete_user(uid=u.uid)
                print(f"🗑️  Borrado user_id={u.user_id} ({u.name.strip() if u.name else ''})")
                ok += 1
            except Exception as e:
                print(f"❌ Error al borrar user_id={u.user_id}: {e}")
                con_error += 1

        print(f"\nListo. Borrados: {ok}  Con error: {con_error}")
        print("\n📊 Uso de memoria después de borrar:")
        imprimir_uso_memoria(conn)

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        if conn:
            conn.disconnect()
            print("\n🔌 Desconectado")


if __name__ == "__main__":
    main()
