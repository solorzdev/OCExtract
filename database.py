# db_conn.py robusto
import re
import logging
import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT

# Si ya tienes logger global, quita estas 3 líneas:
import os
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/db_ops.log", level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")

def conectar():
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, port=DB_PORT
    )

# ---------- Normalizadores ----------
_ALNUM_RFC = re.compile(r"[^A-Z0-9Ñ&]")
_ALNUM_CURP = re.compile(r"[^A-Z0-9]")

def norm_rfc(rfc: str | None) -> str | None:
    if not rfc: return None
    r = _ALNUM_RFC.sub("", rfc.strip().upper())
    return r or None

def norm_curp(curp: str | None) -> str | None:
    if not curp: return None
    c = _ALNUM_CURP.sub("", curp.strip().upper())
    return c or None

# ---------- Chequeos ----------
def existe_rfc(rfc):
    return existe_registro(rfc, None)

def existe_registro(rfc: str | None, curp: str | None) -> bool:
    """Devuelve True si existe un registro con ese RFC o (si hay) ese CURP."""
    rfc_n = norm_rfc(rfc)
    curp_n = norm_curp(curp)

    if not rfc_n and not curp_n:
        return False  # nada con qué comparar

    q = []
    vals = []
    if rfc_n:
        q.append("REPLACE(REPLACE(UPPER(rfc),' ',''),'-','') = %s")
        vals.append(rfc_n)
    if curp_n:
        q.append("REPLACE(REPLACE(UPPER(curp),' ',''),'-','') = %s")
        vals.append(curp_n)

    sql = f"SELECT 1 FROM constancias WHERE {' OR '.join(q)} LIMIT 1"

    con = conectar()
    cur = con.cursor()
    cur.execute(sql, tuple(vals))
    ok = cur.fetchone() is not None
    cur.close(); con.close()
    return ok

# ---------- Insert ----------
def guardar_datos(datos: dict) -> bool:
    """
    Inserta si NO existe por RFC/CURP. Devuelve True si insertó, False si fue duplicado.
    Normaliza RFC/CURP antes de insertar.
    """
    # Normalizar (y reescribir en el dict para que quede limpio en BD)
    datos = dict(datos)  # copia para no mutar el original
    datos['rfc'] = norm_rfc(datos.get('rfc'))
    datos['curp'] = norm_curp(datos.get('curp'))

    if not datos.get('rfc'):
        logging.warning("Intento de guardar sin RFC. archivo=%s", datos.get('archivo_origen'))
        return False

    # Dedupe por RFC o CURP
    if existe_registro(datos.get('rfc'), datos.get('curp')):
        logging.info("Duplicado detectado, no se inserta. RFC=%s CURP=%s archivo=%s",
                     datos.get('rfc'), datos.get('curp'), datos.get('archivo_origen'))
        return False

    con = conectar()
    cur = con.cursor()
    sql = """
        INSERT INTO constancias (
            tipo_contribuyente, rfc, curp, fecha_emision, razon_social,
            regimen_capital, nombre_comercial,
            nombre, apellido_paterno, apellido_materno,
            estatus_padron, codigo_postal,
            archivo_origen, fecha_procesado
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    vals = (
        datos.get('tipo_contribuyente'),
        datos.get('rfc'),
        datos.get('curp'),
        datos.get('fecha_emision'),
        datos.get('razon_social'),
        datos.get('regimen_capital'),
        datos.get('nombre_comercial'),
        datos.get('nombre'),
        datos.get('apellido_paterno'),
        datos.get('apellido_materno'),
        datos.get('estatus_padron'),
        datos.get('codigo_postal'),
        datos.get('archivo_origen'),
        datos.get('fecha_procesado'),
    )
    try:
        cur.execute(sql, vals)
        con.commit()
        logging.info("Insert OK. RFC=%s CURP=%s archivo=%s", datos.get('rfc'), datos.get('curp'), datos.get('archivo_origen'))
        return True
    except mysql.connector.IntegrityError as e:
        # Si tienes índices UNIQUE, caemos aquí también
        logging.warning("IntegrityError (probable duplicado). RFC=%s CURP=%s archivo=%s err=%s",
                        datos.get('rfc'), datos.get('curp'), datos.get('archivo_origen'), e)
        return False
    finally:
        cur.close()
        con.close()
