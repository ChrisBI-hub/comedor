"""
Impresión de tickets de comedor en la impresora térmica de red
(protocolo ESC/POS, la que hablan casi todas las impresoras de tickets:
Epson TM-T20/T88, Xprinter XP-58/XP-80, POS-58/80, etc.).

No requiere librerías adicionales: el ticket se arma como una cadena de
comandos ESC/POS y se envía por un socket TCP normal al puerto 9100
(puerto estándar "RAW/JetDirect" que usan estas impresoras).

Ajustar aquí si cambia el equipo o el ancho del rollo de papel.
"""

import socket
import unicodedata
from datetime import datetime

# ── Configuración ────────────────────────────────────────────────────────
IP_IMPRESORA = "10.10.10.128"
PUERTO_IMPRESORA = 9100
TIMEOUT_SEGUNDOS = 5

EMPRESA = "ABSOLUTE BROKERAGE CUSTOMS"

# Ancho del ticket en caracteres (fuente normal). 32 = rollo de 58mm
# (el más común para este tipo de impresora). Si el rollo es de 80mm,
# cambiar a 48.
ANCHO_TICKET = 32

# ── Comandos ESC/POS ─────────────────────────────────────────────────────
ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"                    # reinicia la impresora
ALINEAR_CENTRO = ESC + b"a" + b"\x01"
NEGRITA_ON = ESC + b"E" + b"\x01"
NEGRITA_OFF = ESC + b"E" + b"\x00"
TAMANO_NORMAL = GS + b"!" + b"\x00"
TAMANO_DOBLE = GS + b"!" + b"\x11"   # doble alto + doble ancho
CORTE_PAPEL = GS + b"V" + b"\x00"    # corte total


def _limpiar_texto(texto):
    """Quita acentos/ñ para evitar símbolos raros: muchas impresoras
    térmicas económicas no traen la tabla de caracteres en español."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return normalizado.encode("ascii", "ignore").decode("ascii")


def construir_ticket(nombre, ya_registrado_hoy, fecha_hora=None):
    """Arma los bytes ESC/POS del ticket de comedor.

    nombre: nombre del empleado que checó.
    ya_registrado_hoy: True si el empleado ya tiene una marcación previa
        el mismo día (en ese caso NO se le da servicio de comedor otra vez).
    fecha_hora: datetime del evento; si no se manda, usa el momento actual.
    """
    if fecha_hora is None:
        fecha_hora = datetime.now()

    nombre = _limpiar_texto(nombre.strip().upper())
    separador = ("-" * ANCHO_TICKET + "\n").encode("ascii")
    fecha_str = fecha_hora.strftime("%d/%m/%Y")
    hora_str = fecha_hora.strftime("%H:%M:%S")

    ticket = bytearray()
    ticket += INIT
    ticket += ALINEAR_CENTRO

    ticket += NEGRITA_ON
    ticket += (EMPRESA + "\n").encode("ascii")
    ticket += NEGRITA_OFF
    ticket += separador

    ticket += TAMANO_NORMAL
    ticket += (nombre + "\n").encode("ascii")
    ticket += separador

    ticket += TAMANO_DOBLE
    ticket += NEGRITA_ON
    if ya_registrado_hoy:
        mensaje = "YA TIENE UN\nREGISTRO EL\nDIA DE HOY\n"
    else:
        mensaje = "SERVICIO DE\nCOMEDOR\n"
    ticket += mensaje.encode("ascii")
    ticket += NEGRITA_OFF
    ticket += TAMANO_NORMAL

    ticket += separador
    ticket += (f"{fecha_str}   {hora_str}\n").encode("ascii")

    ticket += b"\n\n\n"
    ticket += CORTE_PAPEL
    return bytes(ticket)


def imprimir_ticket(nombre, ya_registrado_hoy, fecha_hora=None):
    """Envía el ticket a la impresora de red.

    Lanza la excepción tal cual si falla la conexión/envío (impresora
    apagada, sin papel, red caída, etc.) para que quien la llame decida
    cómo manejarlo (por ejemplo, solo loguear el error sin tumbar el
    programa que sigue escuchando el checador).
    """
    ticket = construir_ticket(nombre, ya_registrado_hoy, fecha_hora)
    with socket.create_connection(
        (IP_IMPRESORA, PUERTO_IMPRESORA), timeout=TIMEOUT_SEGUNDOS
    ) as sock:
        sock.sendall(ticket)


if __name__ == "__main__":
    # Prueba manual: corre este archivo directo para imprimir dos tickets
    # de ejemplo (uno normal y uno de "ya registrado") y confirmar que la
    # impresora en 10.10.10.128 responde bien.
    print(f"Enviando ticket de prueba a {IP_IMPRESORA}:{PUERTO_IMPRESORA}...")
    imprimir_ticket("Empleado De Prueba", ya_registrado_hoy=False)
    print("✅ Ticket normal enviado.")
    imprimir_ticket("Empleado De Prueba", ya_registrado_hoy=True)
    print("✅ Ticket de 'ya registrado' enviado.")
