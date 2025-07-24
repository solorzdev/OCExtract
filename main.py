import os
import shutil
import logging
from extractor import procesar_archivo
from database import guardar_datos

os.makedirs('logs', exist_ok=True) 
LOG_PATH = 'logs/procesamiento.log'
logging.basicConfig(filename=LOG_PATH, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')



RUTA_ENTRADA = 'pendientes'
RUTA_PROCESADOS = 'procesados'
RUTA_ERRORES = 'errores'
EXT_VALIDAS = {'.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff'}

def mover_archivo(origen, destino):
    os.makedirs(destino, exist_ok=True)
    shutil.move(origen, os.path.join(destino, os.path.basename(origen)))

def main():
    for carpeta in [RUTA_ENTRADA, RUTA_PROCESADOS, RUTA_ERRORES, 'logs']:
        os.makedirs(carpeta, exist_ok=True)

    archivos = [entry for entry in os.scandir(RUTA_ENTRADA) if entry.is_file() and entry.name.lower().endswith(tuple(EXT_VALIDAS))]
    if not archivos:
        logging.info("No hay archivos válidos para procesar.")
        return

    for entry in archivos:
        archivo = entry.name
        ruta_completa = entry.path
        try:
            datos = procesar_archivo(ruta_completa)
            if datos:
                guardar_datos(datos)
                mover_archivo(ruta_completa, RUTA_PROCESADOS)
                logging.info(f"Procesado con éxito: {archivo}")
            else:
                mover_archivo(ruta_completa, RUTA_ERRORES)
                logging.warning(f"No se extrajeron datos de: {archivo}")
        except Exception as e:
            mover_archivo(ruta_completa, RUTA_ERRORES)
            logging.error(f"Error crítico en {archivo}: {str(e)}")

if __name__ == '__main__':
    main()
