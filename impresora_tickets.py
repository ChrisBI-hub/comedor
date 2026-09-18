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
IP_IMPRESORA = "10.10.13.190"
PUERTO_IMPRESORA = 9100
TIMEOUT_SEGUNDOS = 5

EMPRESA_POR_DEFECTO = "ABSOLUTE BROKERAGE CUSTOMS"

# Ancho del ticket en caracteres (fuente normal). 32 = rollo de 58mm
# (el más común para este tipo de impresora). Si el rollo es de 80mm,
# cambiar a 48.
ANCHO_TICKET = 32

# Líneas en blanco que se avanzan antes de cortar el papel, para que la
# guillotina no corte pegado al texto. Subir este número si sigue
# quedando muy justo.
ESPACIO_ANTES_DE_CORTE = 6

# ── Comandos ESC/POS ─────────────────────────────────────────────────────
ESC = b"\x1b"
GS = b"\x1d"

INIT = ESC + b"@"                    # reinicia la impresora
ALINEAR_CENTRO = ESC + b"a" + b"\x01"
NEGRITA_ON = ESC + b"E" + b"\x01"
NEGRITA_OFF = ESC + b"E" + b"\x00"
TAMANO_NORMAL = GS + b"!" + b"\x00"
TAMANO_DOBLE = GS + b"!" + b"\x11"   # doble alto + doble ancho
CORTE_PAPEL = ESC + b"i"             # corte de papel (confirmado con esta impresora)

# Pulso hacia el puerto de cajón de dinero (DK) de la impresora: ESC p m t1 t2.
# Es el mecanismo estándar de las impresoras de tickets para "hacer ruido":
# no tienen bocina propia, pero casi todas traen ese puerto, y ahí es donde
# normalmente se conecta un chicharra/timbre de 12V para avisos. Si tu
# impresora tiene una chicharra conectada en ese puerto (como las que se usan
# para abrir cajón registrador), esto la hace sonar.
PULSO_ALARMA = ESC + b"p" + bytes([0, 120, 120])
REPETICIONES_ALARMA = 5


def _limpiar_texto(texto):
    """Quita acentos/ñ para evitar símbolos raros: muchas impresoras
    térmicas económicas no traen la tabla de caracteres en español."""
    normalizado = unicodedata.normalize("NFKD", texto)
    return normalizado.encode("ascii", "ignore").decode("ascii")


def construir_ticket(nombre, ya_registrado_hoy, fecha_hora=None, empresa=None):
    """Arma los bytes ESC/POS del ticket de comedor.

    nombre: nombre del empleado que checó.
    ya_registrado_hoy: True si el empleado ya tiene una marcación previa
        el mismo día (en ese caso NO se le da servicio de comedor otra vez).
    fecha_hora: datetime del evento; si no se manda, usa el momento actual.
    empresa: empresa a la que pertenece el empleado (para grupos con varias
        razones sociales). Si no se manda o viene vacía, usa EMPRESA_POR_DEFECTO.
    """
    if fecha_hora is None:
        fecha_hora = datetime.now()

    nombre = _limpiar_texto(nombre.strip().upper())
    empresa = _limpiar_texto((empresa or EMPRESA_POR_DEFECTO).strip().upper())
    separador = ("-" * ANCHO_TICKET + "\n").encode("ascii")
    fecha_str = fecha_hora.strftime("%d/%m/%Y")
    hora_str = fecha_hora.strftime("%H:%M:%S")

    ticket = bytearray()
    ticket += INIT
    ticket += ALINEAR_CENTRO

    ticket += NEGRITA_ON
    ticket += (empresa + "\n").encode("ascii")
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

    ticket += b"\n" * ESPACIO_ANTES_DE_CORTE
    ticket += CORTE_PAPEL
    return bytes(ticket)


def imprimir_ticket(nombre, ya_registrado_hoy, fecha_hora=None, empresa=None):
    """Envía el ticket a la impresora de red.

    Lanza la excepción tal cual si falla la conexión/envío (impresora
    apagada, sin papel, red caída, etc.) para que quien la llame decida
    cómo manejarlo (por ejemplo, solo loguear el error sin tumbar el
    programa que sigue escuchando el checador).
    """
    ticket = construir_ticket(nombre, ya_registrado_hoy, fecha_hora, empresa)
    with socket.create_connection(
        (IP_IMPRESORA, PUERTO_IMPRESORA), timeout=TIMEOUT_SEGUNDOS
    ) as sock:
        sock.sendall(ticket)


def sonar_alarma():
    """Hace sonar la chicharra conectada al puerto de cajón (DK) de la
    impresora, sin imprimir nada en papel.

    Requiere que haya una chicharra/timbre de 12V conectado físicamente a
    ese puerto (el mismo que se usa para abrir cajones de dinero en cajas
    registradoras); si no hay nada conectado ahí, este comando no hace
    nada visible. Lanza la excepción tal cual si falla la conexión, igual
    que imprimir_ticket.
    """
    pulsos = PULSO_ALARMA * REPETICIONES_ALARMA
    with socket.create_connection(
        (IP_IMPRESORA, PUERTO_IMPRESORA), timeout=TIMEOUT_SEGUNDOS
    ) as sock:
        sock.sendall(pulsos)


if __name__ == "__main__":
    # Prueba manual: corre este archivo directo para imprimir dos tickets
    # de ejemplo (uno normal y uno de "ya registrado") y probar la alarma,
    # y confirmar que la impresora responde bien.
    print(f"Enviando ticket de prueba a {IP_IMPRESORA}:{PUERTO_IMPRESORA}...")
    imprimir_ticket("Empleado De Prueba", ya_registrado_hoy=False)
    print("✅ Ticket normal enviado.")
    imprimir_ticket("Empleado De Prueba", ya_registrado_hoy=True)
    print("✅ Ticket de 'ya registrado' enviado.")
    sonar_alarma()
    print("✅ Pulso de alarma enviado (solo se oye si hay una chicharra conectada al puerto DK).")
