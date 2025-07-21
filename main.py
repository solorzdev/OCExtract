import os
import shutil
import logging
from extractor import procesar_archivo
from database import guardar_datos

# Configuración de rutas
RUTA_ENTRADA = 'pendientes'
RUTA_PROCESADOS = 'procesados'
RUTA_ERRORES = 'errores'
LOG_PATH = 'logs/procesamiento.log'

# Configuración de logging
logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def mover_archivo(origen, destino):
    os.makedirs(destino, exist_ok=True)
    shutil.move(origen, os.path.join(destino, os.path.basename(origen)))

def main():
    os.makedirs(RUTA_ENTRADA, exist_ok=True)
    os.makedirs(RUTA_PROCESADOS, exist_ok=True)
    os.makedirs(RUTA_ERRORES, exist_ok=True)
    os.makedirs('logs', exist_ok=True)

    archivos = os.listdir(RUTA_ENTRADA)
    if not archivos:
        logging.info("No hay archivos pendientes para procesar.")
        return

    for archivo in archivos:
        ruta_completa = os.path.join(RUTA_ENTRADA, archivo)
        try:
            datos = procesar_archivo(ruta_completa)
            if datos:
                guardar_datos(datos)
                mover_archivo(ruta_completa, RUTA_PROCESADOS)
                logging.info(f"Procesado con éxito: {archivo}")
            else:
                mover_archivo(ruta_completa, RUTA_ERRORES)
                logging.error(f"Error de extracción: {archivo}")
        except Exception as e:
            mover_archivo(ruta_completa, RUTA_ERRORES)
            logging.error(f"Error crítico en {archivo}: {str(e)}")

if __name__ == '__main__':
    main()
