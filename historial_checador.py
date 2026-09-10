"""
Extracción de registros de asistencia almacenados en el checador ZKTeco (K40).

Útil para:
  1. Respaldo/auditoría del historial que trae el equipo de su uso anterior
     como checador de asistencia de personal.
  2. Reconciliación periódica: correrlo de vez en cuando y comparar contra
     registros_comedor.csv para recuperar marcaciones que el script en
     tiempo real haya podido perder (ej. si se cayó la conexión un rato).

Requiere: pyzk2  (pip install pyzk2)
"""

import csv
from pyzk2 import ZK

IP = "10.10.10.126"       # ⚠️ CONFIRMAR: verificar si es .124 o .126
PORT = 4370
ARCHIVO_SALIDA = "historial_checador_respaldo.csv"


def exportar_historial():
    zk = ZK(IP, port=PORT, timeout=15, password=0, force_udp=False)
    conn = None

    try:
        print(f"Conectando a {IP}:{PORT}...")
        conn = zk.connect()
        print("✅ Conectado\n")

        print("Consultando usuarios para mapear nombres...")
        usuarios = {
            u.user_id: (u.name.strip() if u.name else f"ID {u.user_id}")
            for u in conn.get_users()
        }

        print("Consultando registros de asistencia...")
        attendance = conn.get_attendance()
        print(f"Registros encontrados: {len(attendance)}\n")

        with open(ARCHIVO_SALIDA, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["fecha_hora", "user_id", "nombre", "status", "punch"])
            for r in attendance:
                writer.writerow([
                    r.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    r.user_id,
                    usuarios.get(r.user_id, "Desconocido"),
                    r.status,
                    r.punch,
                ])

        print(f"💾 Respaldo guardado en: {ARCHIVO_SALIDA}")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        if conn:
            conn.disconnect()
            print("\n🔌 Desconectado")


if __name__ == "__main__":
    exportar_historial()
