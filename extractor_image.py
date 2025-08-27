# -*- coding: utf-8 -*-
import os, shutil, logging
from PIL import Image
import pytesseract

from config import PENDIENTES_DIR, PROCESADOS_DIR, ERRORES_DIR, LOGS_DIR, TESS_LANG, ARCHIVO_ID_FROM_FILENAME
from database import update_archivo_opinion
from extractor_pdf import _parsear, _infer_modulo_y_archivo_id  # reusamos parser y helper

os.makedirs(LOGS_DIR, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(LOGS_DIR, "oc_img.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def procesar_imagen(path_img: str):
    archivo = os.path.basename(path_img)
    base, _ = os.path.splitext(archivo)
    logging.info(f"[OC-IMG] {archivo}")
    print(f"↪ [OC-IMG] {archivo}")

    try:
        txt = pytesseract.image_to_string(Image.open(path_img), lang=TESS_LANG)
        data = _parsear(txt)
        if not data:
            print("   ⚠️ No se pudieron extraer campos.")
            shutil.move(path_img, os.path.join(ERRORES_DIR, archivo))
            return

        modulo_id, archivo_id = _infer_modulo_y_archivo_id(archivo)
        if ARCHIVO_ID_FROM_FILENAME and archivo_id is not None:
            modulo_id = modulo_id if modulo_id is not None else 1017
            rows = update_archivo_opinion(archivo_id, modulo_id, data, marcar_procesado=True)
            if rows == 0:
                print(f"   ⚠️ No se encontró ArchivoID={archivo_id} AND ArchivoModuloID={modulo_id}.")
            else:
                print(f"   ✅ UPDATE OK → ArchivoID={archivo_id}, Modulo={modulo_id}")
        else:
            print("   ⚠️ No pude inferir ArchivoID desde el nombre. No se actualizó la DB.")

        with open(os.path.join(PROCESADOS_DIR, f"{base}_ocr.txt"), "w", encoding="utf-8") as f:
            f.write(txt)
        shutil.move(path_img, os.path.join(PROCESADOS_DIR, archivo))

        print(f"   ✅ Guardado: RFC={data.get('rfc') or '?'} | FOLIO={data.get('folio') or '?'} | SENTIDO={data.get('sentido') or '?'}")

    except Exception as e:
        print(f"   ❌ Error: {e}")
        logging.exception(f"[OC-IMG] Error con {archivo}: {e}")
        try:
            shutil.move(path_img, os.path.join(ERRORES_DIR, archivo))
        except Exception:
            pass
