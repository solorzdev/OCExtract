# -*- coding: utf-8 -*-
import os

BASE_DIR        = os.path.abspath(os.path.dirname(__file__))
PENDIENTES_DIR  = os.path.join(BASE_DIR, "pendientes")
PROCESADOS_DIR  = os.path.join(BASE_DIR, "procesados")
ERRORES_DIR     = os.path.join(BASE_DIR, "errores")
LOGS_DIR        = os.path.join(BASE_DIR, "logs")
for d in (PENDIENTES_DIR, PROCESADOS_DIR, ERRORES_DIR, LOGS_DIR):
    os.makedirs(d, exist_ok=True)

# SQL Server
DB_SERVER   = os.getenv("DB_SERVER",   "201.156.35.6")
DB_DATABASE = os.getenv("DB_DATABASE", "ARCHIVOS")
DB_USER     = os.getenv("DB_USER",     "usrar08837a")
DB_PASSWORD = os.getenv("DB_PASSWORD", "uU62$gstcCd129$")
DB_DRIVER   = os.getenv("DB_DRIVER",   "ODBC Driver 17 for SQL Server")

# OCR
TESS_LANG = os.getenv("TESS_LANG", "spa")
OCR_DPI   = int(os.getenv("OCR_DPI", "300"))

# Tabla a actualizar
TABLE_ARCHIVO = os.getenv("TABLE_ARCHIVO", "Archivo")

# El nombre del archivo trae IDs (p.ej. 1017_242784.pdf)
ARCHIVO_ID_FROM_FILENAME = True
