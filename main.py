import os
from extractor_pdf import procesar_archivo as procesar_pdf
import subprocess

RUTA_ENTRADA = 'pendientes'
EXT_PDF = ('.pdf',)
EXT_IMG = ('.jpg', '.jpeg', '.png', '.tif', '.tiff')

def main():
    archivos = [
        os.path.join(RUTA_ENTRADA, f)
        for f in os.listdir(RUTA_ENTRADA)
        if os.path.isfile(os.path.join(RUTA_ENTRADA, f))
    ]

    # PDFs primero
    pdfs = [a for a in archivos if a.lower().endswith(EXT_PDF)]
    if pdfs:
        for pdf in pdfs:
            procesar_pdf(pdf)  # Usa el flujo PDF normal

    # Luego imágenes
    imagenes = [a for a in archivos if a.lower().endswith(EXT_IMG)]
    if imagenes:
        # Llama al script de imágenes y le pasa las rutas como argumentos
        subprocess.run(["python", "extractor_image.py", *imagenes])

if __name__ == '__main__':
    main()
