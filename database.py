import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT

def conectar():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
    )

def guardar_datos(datos):
    conexion = conectar()
    cursor = conexion.cursor()

    sql = """
        INSERT INTO constancias (tipo_contribuyente, rfc, fecha_emision, razon_social,
                                 regimen_capital, nombre_comercial,
                                 nombre, apellido_paterno, apellido_materno,
                                 estatus_padron, codigo_postal)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    valores = (
        datos['tipo_contribuyente'],
        datos['rfc'],
        datos['fecha_emision'],
        datos.get('razon_social'),
        datos.get('regimen_capital'),
        datos.get('nombre_comercial'),
        datos.get('nombre'),
        datos.get('apellido_paterno'),
        datos.get('apellido_materno'),
        datos['estatus_padron'],
        datos['codigo_postal']
    )

    cursor.execute(sql, valores)
    conexion.commit()
    cursor.close()
    conexion.close()
