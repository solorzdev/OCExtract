# -*- coding: utf-8 -*-
import os
from config import PENDIENTES_DIR
from extractor_pdf import procesar_archivo as procesar_pdf
from extractor_image import procesar_imagen

EXT_PDF = ('.pdf',)
EXT_IMG = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp')

def main():
    os.makedirs(PENDIENTES_DIR, exist_ok=True)
    archivos = [
        os.path.join(PENDIENTES_DIR, f)
        for f in os.listdir(PENDIENTES_DIR)
        if os.path.isfile(os.path.join(PENDIENTES_DIR, f))
    ]

    for pdf in [a for a in archivos if a.lower().endswith(EXT_PDF)]:
        procesar_pdf(pdf)

    for img in [a for a in archivos if a.lower().endswith(EXT_IMG)]:
        procesar_imagen(img)

if __name__ == '__main__':
    main()
