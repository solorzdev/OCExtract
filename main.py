import os  # Para manejar rutas, carpetas y archivos
import shutil  # Para mover archivos entre carpetas
import logging  # Para registrar eventos del sistema (información, errores, etc.)
from extractor import procesar_archivo  # Función que extrae datos desde PDFs o imágenes
from database import guardar_datos  # Función que guarda los datos extraídos en una base de datos

# Crear carpeta de logs si no existe
os.makedirs('logs', exist_ok=True)

# Configurar archivo de log para registrar el procesamiento
LOG_PATH = 'logs/procesamiento.log'
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Definición de rutas y extensiones válidas
RUTA_ENTRADA = 'pendientes'       # Carpeta de entrada con archivos por procesar
RUTA_PROCESADOS = 'procesados'    # Carpeta donde se moverán los archivos exitosamente procesados
RUTA_ERRORES = 'errores'          # Carpeta para archivos que fallaron
EXT_VALIDAS = {'.pdf', '.jpg', '.jpeg', '.png', '.tif', '.tiff'}  # Extensiones permitidas

# Mueve un archivo desde su ruta de origen a una carpeta de destino
def mover_archivo(origen, destino):
    os.makedirs(destino, exist_ok=True)  # Asegura que la carpeta destino exista
    shutil.move(origen, os.path.join(destino, os.path.basename(origen)))  # Mueve el archivo

# Función principal del procesamiento por lotes
def main():
    # Asegura que todas las carpetas necesarias existan
    for carpeta in [RUTA_ENTRADA, RUTA_PROCESADOS, RUTA_ERRORES, 'logs']:
        os.makedirs(carpeta, exist_ok=True)

    # Escanea la carpeta de entrada y filtra solo los archivos válidos
    archivos = [
        entry for entry in os.scandir(RUTA_ENTRADA)
        if entry.is_file() and entry.name.lower().endswith(tuple(EXT_VALIDAS))
    ]

    # Si no hay archivos válidos, registrar mensaje y finalizar
    if not archivos:
        logging.info("No hay archivos válidos para procesar.")
        return

    # Procesar cada archivo válido
    for entry in archivos:
        archivo = entry.name
        ruta_completa = entry.path
        try:
            # Intenta extraer los datos del archivo
            datos = procesar_archivo(ruta_completa)
            if datos:
                guardar_datos(datos)  # Guarda los datos en la base de datos
                mover_archivo(ruta_completa, RUTA_PROCESADOS)  # Mueve a carpeta de procesados
                logging.info(f"Procesado con éxito: {archivo}")
            else:
                mover_archivo(ruta_completa, RUTA_ERRORES)  # Si no se extrajeron datos, mover a errores
                logging.warning(f"No se extrajeron datos de: {archivo}")
        except Exception as e:
            # En caso de error crítico, mover a errores y registrar el mensaje
            mover_archivo(ruta_completa, RUTA_ERRORES)
            logging.error(f"Error crítico en {archivo}: {str(e)}")

# Punto de entrada del script
if __name__ == '__main__':
    main()
