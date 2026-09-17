"""
Extrae la lista de usuarios registrados en el checador ZKTeco (K40) y la
guarda en un CSV. Útil para tener un padrón de quién debería poder
checar/comer, o para cruzar contra registros_comedor.csv y detectar
huellas registradas en el equipo que no están en ninguna lista de nómina.

Requiere: pyzk2  (pip install pyzk2)
"""

import csv

from pyzk2 import ZK

IP = "10.10.10.126"       # ⚠️ CONFIRMAR: verificar si es .124 o .126
PORT = 4370
PASSWORD = 0
ARCHIVO_SALIDA = "usuarios_checador.csv"


def exportar_usuarios():
    zk = ZK(IP, port=PORT, timeout=15, password=PASSWORD, force_udp=False)
    conn = None

    try:
        print(f"Conectando a {IP}:{PORT}...")
        conn = zk.connect()
        print("✅ Conectado\n")

        print("Consultando usuarios registrados...")
        usuarios = conn.get_users()
        print(f"Usuarios encontrados: {len(usuarios)}\n")

        with open(ARCHIVO_SALIDA, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "nombre", "privilegio", "tarjeta", "grupo"])
            for u in usuarios:
                writer.writerow([
                    u.user_id,
                    u.name.strip() if u.name else "",
                    u.privilege,
                    u.card,
                    u.group_id,
                ])

        print(f"💾 Lista guardada en: {ARCHIVO_SALIDA}")

    except Exception as e:
        print(f"❌ Error: {e}")

    finally:
        if conn:
            conn.disconnect()
            print("\n🔌 Desconectado")


if __name__ == "__main__":
    exportar_usuarios()
