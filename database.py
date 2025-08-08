# Importación para conexión con la base de datos
import mysql.connector
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME, DB_PORT

# Configuración de la conexión 
def conectar():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT
    )

def existe_rfc(rfc):
    conexion = conectar()
    cursor = conexion.cursor()
    cursor.execute("SELECT 1 FROM constancias WHERE rfc = %s LIMIT 1", (rfc,))
    existe = cursor.fetchone() is not None
    cursor.close()
    conexion.close()
    return existe

# Configuración para guardar los datos 
def guardar_datos(datos):
    conexion = conectar()
    cursor = conexion.cursor()

    sql = """
        INSERT INTO constancias (
            tipo_contribuyente, rfc, curp, fecha_emision, razon_social,
            regimen_capital, nombre_comercial,
            nombre, apellido_paterno, apellido_materno,
            estatus_padron, codigo_postal,
            archivo_origen, fecha_procesado
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    valores = (
        datos['tipo_contribuyente'],
        datos['rfc'],
        datos.get('curp'),
        datos['fecha_emision'],
        datos.get('razon_social'),
        datos.get('regimen_capital'),
        datos.get('nombre_comercial'),
        datos.get('nombre'),
        datos.get('apellido_paterno'),
        datos.get('apellido_materno'),
        datos['estatus_padron'],
        datos['codigo_postal'],
        datos.get('archivo_origen'),
        datos.get('fecha_procesado')
    )

    cursor.execute(sql, valores)
    conexion.commit()
    cursor.close()
    conexion.close()
