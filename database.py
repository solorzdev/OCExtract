# -*- coding: utf-8 -*-
import pyodbc
from config import DB_SERVER, DB_DATABASE, DB_USER, DB_PASSWORD, DB_DRIVER, TABLE_ARCHIVO

def conectar():
    conn_str = (
        f"DRIVER={{{DB_DRIVER}}};SERVER={DB_SERVER};DATABASE={DB_DATABASE};"
        f"UID={DB_USER};PWD={DB_PASSWORD}"
    )
    return pyodbc.connect(conn_str)

def update_archivo_opinion(archivo_id: int, modulo_id: int, datos: dict, marcar_procesado: bool = True) -> int:
    """
    Actualiza campos de Opinión de Cumplimiento en [dbo].[Archivo]
    usando ArchivoID + ArchivoModuloID (1017 para OC).

    datos = {
        'rfc', 'razon_social', 'folio', 'sentido',
        'fecha_emision'(date), 'hora_emision'(time),
        'cadena_original'(str)
    }
    Devuelve número de filas afectadas.
    """
    sets, vals = [], []

    # Reutilizados
    if datos.get('rfc') is not None:
        sets.append("RFC = ?");                 vals.append(datos['rfc'])
    if datos.get('razon_social') is not None:
        sets.append("RazonSocial = ?");         vals.append(datos['razon_social'])
    if datos.get('fecha_emision') is not None:
        sets.append("FechaEmision = ?");        vals.append(datos['fecha_emision'])

    # Nuevos de OC
    if datos.get('folio') is not None:
        sets.append("OpinionFolio = ?");        vals.append(datos['folio'])
    if datos.get('sentido') is not None:
        sets.append("OpinionSentido = ?");      vals.append(datos['sentido'])
    if datos.get('hora_emision') is not None:
        sets.append("OpinionHoraEmision = ?");  vals.append(datos['hora_emision'])
    if datos.get('cadena_original') is not None:
        sets.append("OpinionCadenaOriginal = ?"); vals.append(datos['cadena_original'])

    if marcar_procesado:
        sets.append("Procesado = 1")
        sets.append("FechaProcesado = SYSDATETIME()")

    if not sets:
        return 0  # nada que actualizar

    sql = f"""
        UPDATE [dbo].[{TABLE_ARCHIVO}]
        SET {", ".join(sets)}
        WHERE ArchivoID = ? AND ArchivoModuloID = ?
    """
    vals.extend([archivo_id, modulo_id])

    with conectar() as cn, cn.cursor() as cur:
        cur.execute(sql, tuple(vals))
        rows = cur.rowcount or 0
        cn.commit()
        return rows
