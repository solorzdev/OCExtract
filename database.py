import pyodbc

# Configuración de conexión local a SQL Server
def conectar():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"
        "DATABASE=extractinfo;"
        "Trusted_Connection=yes;"
    )

# Guardar datos extraídos en SQL Server
def guardar_datos(datos):
    conn = conectar()
    cursor = conn.cursor()

    sql = """
        INSERT INTO constancias (
            tipo_contribuyente, rfc, curp, fecha_emision, razon_social,
            regimen_capital, nombre_comercial,
            nombre, apellido_paterno, apellido_materno,
            estatus_padron, codigo_postal,
            archivo_origen, fecha_procesado
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
    conn.commit()
    cursor.close()
    conn.close()

def existe_rfc(rfc: str) -> bool:
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM constancias WHERE rfc = ?", (rfc,))
    resultado = cursor.fetchone()[0]

    cursor.close()
    conn.close()
    return resultado > 0
